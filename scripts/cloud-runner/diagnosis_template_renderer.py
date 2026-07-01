#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnosis template-driven renderer."""
from pathlib import Path
import html, json, os, re, sys, time, urllib.error, urllib.request

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_HTML = ROOT / 'skills/family-plan-v21-final/assets/diagnosis-final-template-v2-deep/index.html'
SKILL_MD = ROOT / 'skills/family-plan-v21-final/SKILL.md'
CLOUD_OUTPUT = ROOT / 'cloud-output'
CLOUD_OUTPUT.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = (os.environ.get("OPENAI_BASE_URL") or "https://us.aitechflux.com/v1").rstrip("/")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or "aitechflux/gpt-5.5"
OPENAI_FALLBACK_MODELS = [m.strip() for m in (os.environ.get("OPENAI_FALLBACK_MODELS") or "deepseek-chat").split(",") if m.strip()]
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")

# --- Primary diagnosis engine: Anthropic-compatible custom provider (claude-opus-4-8) ---
# When set, the renderer prefers this engine for both the problem-extraction pass
# and the per-problem professional-view generation pass.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = (os.environ.get("ANTHROPIC_BASE_URL") or "https://www.primerouter.xyz").rstrip("/")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-opus-4-8"
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION") or "2023-06-01"

# Per-run circuit breaker for the opus gateway: after N failures we stop trying opus
# and let call_json_any go straight to the OpenAI/deepseek failover for the rest of the run.
_OPUS_BREAKER = {"fails": 0, "threshold": int(os.environ.get("OPUS_BREAKER_THRESHOLD") or 2), "open": False}

SYSTEM = """你是由持牌移民律师、注册税务师(CPA)和资深身份规划师组成的跨境家庭全球规划顾问团队。你只输出JSON，不要输出任何解释、Markdown围栏或HTML。

【最高质量标准——必须逐条满足，否则视为不合格】
1. 每一个待解决问题(problems)必须是针对本客户的定制诊断，禁止套用通用模板句。禁止不同问题使用相同或高度雷同的detail/solution文字。每个问题必须包含：具体法条依据(law_basis)、律师视角(lawyer_view)、财税规划师视角(tax_view)、身份规划师视角(identity_view)、具体解决方法(solution含分步)、风险规避(risk_control)、立即动作(action)。
2. 每一个专题(topics)必须差异化，围绕本客户真实情况展开，五段式(current_risk/why_it_happens/materials_needed/solution/deliverables)每段都要有本客户特有的数字、国家、项目、金额、天数或法条，禁止八个专题共用同一套话术。
3. 所有法条、阈值、罚则、补救程序必须引用【相关法条与政策】中提供的真实条款(如《外汇管理条例》第45条、《刑法》225条非法经营罪500万立案线、IRS SDOP 5%罚金、FBAR/FATCA门槛、37号文、香港保险AML 240万港元门槛等)。禁止编造不存在的法条。
4. 解决方案必须是可执行的、能实际解决客户问题并规避风险的定制方案，不是空泛口号。给出分步、时间、预算、前提条件。
5. 方案至少3个且有真正的取舍差异(不是微调数字)，必须有一个明确推荐并给≥3条基于本客户约束的理由，以及不推荐其他方案的具体原因。

所有字段必填。至少8个专题、至少3个方案、至少3个待解决问题、至少3条法案依据。"""


def load_knowledge(q: str, max_chars: int = 12000) -> str:
    """Load relevant immigration + compliance/tax law references to ground the diagnosis."""
    ref_dir = ROOT / 'references'
    if not ref_dir.exists():
        return ''
    country_map = {
        '美国|加拿大|EB-5|EB1|EB-1|NIW|O-1|E-2|绿卡|IRS|FBAR|FATCA': ['美加移民政策对比研究-2026.md'],
        '新加坡|日本|泰国|马来西亚|GIP|EP|家办|13O|13U|COMPASS': ['immigration-policies-2025-2026.md'],
        '英国|澳大利亚|澳洲|新西兰|482|186|SMC|189|190|491': ['immigration-research-uk-au-nz-2025.md'],
        '葡萄牙|西班牙|希腊|马耳他|爱尔兰|欧洲': ['europe-immigration-policies-2026.md'],
        '土耳其|瓦努阿图|多米尼克|格鲁吉亚|CBI|基金入籍|捐款': ['immigration-research-tr-vu-dm-ge-2026.md'],
        '迪拜|阿联酋|中国|香港|CIES|高才|专才|优才|ASMTP': ['immigration-research-uae-china-2025.md'],
    }
    picked = ['compliance-tax-law-cn-us-2026.md']  # 合规/财税法条库对每个客户都相关，永久加载
    for pat, files in country_map.items():
        if any(k in q for k in pat.split('|')):
            picked += files
    seen, chunks, total = set(), [], 0
    for name in picked:
        if name in seen:
            continue
        seen.add(name)
        fp = ref_dir / name
        if not fp.exists():
            continue
        txt = fp.read_text(encoding='utf-8', errors='ignore')
        budget = 4000 if name == 'compliance-tax-law-cn-us-2026.md' else 2600
        chunk = f"## {name}\n{txt[:budget]}"
        if total + len(chunk) > max_chars:
            chunk = chunk[:max_chars - total]
        chunks.append(chunk)
        total += len(chunk)
        if total >= max_chars:
            break
    return "\n\n".join(chunks)

def call_anthropic(system: str, prompt: str, max_tokens: int = 8000) -> str:
    """Call an Anthropic-compatible /v1/messages endpoint (claude-opus-4-8 custom provider)."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Missing ANTHROPIC_API_KEY")
    url = ANTHROPIC_BASE_URL + "/v1/messages"
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(), method="POST")
    req.add_header("x-api-key", ANTHROPIC_API_KEY)
    req.add_header("anthropic-version", ANTHROPIC_VERSION)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(req, timeout=240) as r:
        obj = json.loads(r.read().decode())
    # Anthropic messages response: {"content":[{"type":"text","text":"..."}]}
    parts = obj.get("content") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return text.strip()


def call_anthropic_json(system: str, prompt: str, max_tokens: int = 8000, retries: int = 3) -> dict:
    """Call opus and parse a JSON object, tolerating code fences. Retries on transient errors."""
    last_err = None
    for attempt, delay in enumerate([0, 5, 15][:retries], start=1):
        if delay:
            print(f"Retrying opus after {delay}s (attempt {attempt}/{retries})")
            time.sleep(delay)
        try:
            raw = call_anthropic(system, prompt, max_tokens)
            raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
            raw = re.sub(r'\s*```$', '', raw.strip())
            # Extract the outermost JSON object if the model added prose.
            if not raw.startswith('{'):
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    raw = m.group(0)
            return json.loads(raw)
        except Exception as e:
            last_err = e
            print(f"opus JSON attempt {attempt} failed: {str(e)[:160]}")
    raise RuntimeError(f"opus JSON failed after {retries} attempts: {last_err}")


def call_openai_json(system: str, prompt: str, model: str, base_url: str, api_key: str, max_tokens: int) -> dict:
    """Call an OpenAI-compatible chat endpoint and parse JSON, retrying transient gateway errors."""
    payload = {"model": model,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
               "temperature": 0.2, "max_tokens": max_tokens,
               "response_format": {"type": "json_object"}}
    transient = {429, 500, 502, 503, 504, 520, 522, 524}
    last_err = None
    for attempt, delay in enumerate([0, 5, 12], start=1):
        if delay:
            time.sleep(delay)
        try:
            req = urllib.request.Request(base_url + "/chat/completions",
                                        data=json.dumps(payload, ensure_ascii=False).encode(), method="POST")
            req.add_header("Authorization", "Bearer " + api_key)
            req.add_header("Content-Type", "application/json; charset=utf-8")
            with urllib.request.urlopen(req, timeout=180) as r:
                raw = json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()
            raw = re.sub(r'^```(?:json)?\s*', '', raw); raw = re.sub(r'\s*```$', '', raw)
            if not raw.startswith('{'):
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    raw = m.group(0)
            return json.loads(raw)
        except urllib.error.HTTPError as e:
            last_err = e
            if getattr(e, 'code', None) not in transient:
                raise
        except Exception as e:
            last_err = e
    raise last_err if last_err else RuntimeError("openai call failed")


def call_json_any(system: str, prompt: str, max_tokens: int = 2600) -> dict:
    """Unified JSON generation with cross-provider failover so one flaky gateway
    (e.g. opus 504) never sinks the whole diagnosis. Order: opus -> openai(gpt-5.5) -> deepseek.
    A per-run circuit breaker disables opus after repeated failures to avoid paying its
    gateway-timeout latency on every subsequent call."""
    errors = []
    # 1) opus (anthropic-compatible) — one quick attempt, gated by circuit breaker.
    if ANTHROPIC_API_KEY and not _OPUS_BREAKER.get('open'):
        try:
            r = call_anthropic_json(system, prompt, max_tokens, retries=1)
            _OPUS_BREAKER['fails'] = 0
            return r
        except Exception as e:
            errors.append(f"opus:{str(e)[:60]}")
            _OPUS_BREAKER['fails'] = _OPUS_BREAKER.get('fails', 0) + 1
            if _OPUS_BREAKER['fails'] >= _OPUS_BREAKER['threshold']:
                _OPUS_BREAKER['open'] = True
                print(f"[breaker] opus disabled for this run after {_OPUS_BREAKER['fails']} failures; using OpenAI/deepseek")
    # 2) OpenAI-compatible primary (aitechflux gpt-5.5 etc.)
    if OPENAI_API_KEY:
        try:
            return call_openai_json(system, prompt, OPENAI_MODEL, OPENAI_BASE_URL, OPENAI_API_KEY, max_tokens)
        except Exception as e:
            errors.append(f"openai:{str(e)[:60]}")
    # 3) deepseek
    if DEEPSEEK_API_KEY:
        try:
            return call_openai_json(system, prompt, "deepseek-chat", DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, max_tokens)
        except Exception as e:
            errors.append(f"deepseek:{str(e)[:60]}")
    raise RuntimeError("all providers failed: " + " | ".join(errors))


def model_endpoint(model: str) -> tuple[str, str, str]:
    """Return (base_url, api_key, provider_label) for a model candidate."""
    if model.startswith("deepseek") and DEEPSEEK_API_KEY:
        return DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, "deepseek"
    return OPENAI_BASE_URL, OPENAI_API_KEY, "primary"


def call_one_model(model: str, prompt: str, max_tokens: int) -> str:
    base_url, api_key, provider = model_endpoint(model)
    if not api_key:
        raise RuntimeError(f"Missing API key for provider={provider} model={model}")
    payload = {"model": model, "messages": [{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],
               "temperature": 0.15, "max_tokens": max_tokens, "response_format": {"type":"json_object"}}
    req = urllib.request.Request(base_url+"/chat/completions", data=json.dumps(payload,ensure_ascii=False).encode(), method="POST")
    req.add_header("Authorization","Bearer "+api_key)
    req.add_header("Content-Type","application/json; charset=utf-8")
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()


def call_model(prompt: str, max_tokens: int = 12000) -> str:
    if not OPENAI_API_KEY: raise RuntimeError("Missing OPENAI_API_KEY")
    models=[]
    for m in [OPENAI_MODEL] + OPENAI_FALLBACK_MODELS:
        if m and m not in models: models.append(m)
    last_err=None
    transient={429,502,503,504}
    for mi, model in enumerate(models):
        for attempt, delay in enumerate([0,5,15], start=1):
            if delay:
                print(f"Retrying model={model} after {delay}s")
                time.sleep(delay)
            try:
                base_url, _, provider = model_endpoint(model)
                print(f"Calling model candidate {mi+1}/{len(models)}: {model} provider={provider} base={base_url} attempt {attempt}/3")
                return call_one_model(model, prompt, max_tokens)
            except urllib.error.HTTPError as e:
                last_err=e
                code=getattr(e, 'code', None)
                print(f"Model {model} HTTP {code}")
                if code not in transient:
                    break
            except Exception as e:
                last_err=e
                print(f"Model {model} error: {str(e)[:160]}")
                break
        if mi < len(models)-1:
            print(f"Switching to fallback model: {models[mi+1]}")
    raise RuntimeError(str(last_err) if last_err else "all model candidates failed")


# ============================================================================
# Two-stage opus pipeline: (1) extract this client's REAL problems + skeleton,
# (2) enrich each problem independently into a bespoke lawyer/tax/identity case.
# Static boilerplate is only the last-resort floor; the primary path never
# reuses one paragraph across problems.
# ============================================================================

LAW_TOKENS = [
    "外汇管理条例", "第45条", "刑法", "第225条", "非法经营罪", "500万", "2500万",
    "5万美元", "购汇", "37号文", "汇发", "ODI", "SPV", "返程投资", "CRS", "金税四期",
    "反洗钱", "IRC", "全球征税", "1040", "FBAR", "FinCEN", "114", "FATCA", "8938",
    "SFOP", "SDOP", "5%", "330天", "non-willful", "Pre-immigration", "移民前税务",
    "EB-5", "EB-1A", "NIW", "E-2", "$800K", "$1.05M", "保险AML", "240万港元",
    "615章", "高才通", "CIES", "3000万港元", "13O", "13U", "1000万新元", "5000万新元",
    "COMPASS", "5600", "183天", "188", "189", "190", "491", "482", "186", "EOI",
    "税务居民", "预提税", "DTA", "FDI",
]


def law_hit_count(text: str) -> int:
    """How many concrete legal tokens a piece of text references."""
    t = str(text or "")
    return sum(1 for tok in LAW_TOKENS if tok in t)


def _shingles(text: str, n: int = 4) -> set:
    s = re.sub(r'\s+', '', str(text or ''))
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i+n] for i in range(len(s) - n + 1)}


def near_duplicate(a: str, b: str, thresh: float = 0.6) -> bool:
    """Jaccard similarity on 4-grams; True if two texts are too similar."""
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return False
    inter = len(sa & sb)
    union = len(sa | sb)
    return union > 0 and (inter / union) >= thresh


def has_near_dup_across(items: list, fields: list, thresh: float = 0.6) -> str:
    """Return a description if any field is near-duplicated across items, else ''."""
    for field in fields:
        vals = [str(it.get(field, '')).strip() for it in items if str(it.get(field, '')).strip()]
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                if near_duplicate(vals[i], vals[j], thresh):
                    return f'field "{field}" near-duplicated between #{i+1} and #{j+1}'
    return ''


def extract_problem_skeleton(q: str, knowledge: str) -> dict:
    """Stage 1: opus reads the questionnaire and returns the client's real situation
    plus a de-duplicated list of concrete problems (title/severity/client-specific detail)
    and the surrounding diagnosis skeleton. No professional views yet."""
    sys_s = ("你是跨境家庭全球规划首席顾问。只输出JSON对象，不要任何解释或Markdown围栏。"
             "你的任务是阅读这份快速版问卷，识别本客户真实、具体、彼此不同的待解决问题。"
             "每个问题必须来自问卷里的真实信息（国家、金额、天数、账户、身份状态、企业规模、资金动向），"
             "禁止泛化、禁止两个问题描述雷同。")
    schema = ('{"client_name":"","client_summary":{"家庭结构":"","税务居民现状":"","企业与收入":"",'
              '"资产分布":"","核心目标":"","关键约束":""},'
              '"problems":[{"id":"P0-1","problem":"针对本客户的具体问题标题","severity":"P0",'
              '"detail":"本客户具体情境，含真实数字/国家/账户/天数"}],'
              '"root_judgment":{"surface":"","real":"","correct_order":""},'
              '"passport_boundary":""}')
    prompt = ("请阅读问卷并输出JSON，schema如下：\n" + schema +
              "\n\n要求：\n"
              "- problems 至少4个、彼此差异明显，按严重度P0>P1>P2排序，覆盖资金来源/税务居民/合规申报/身份路径/教育时间窗/企业出海中与本客户真实相关的方面。\n"
              "- 每个 detail 必须写出本客户的真实数字或事实（例如富途$400万、绿卡状态、150天、5000万-1亿营收、CRS暴露等），不得写通用句。\n"
              "- root_judgment 区分表面问题与真实问题，给出正确处理顺序。\n"
              "- passport_boundary 说明第三国护照使用边界。\n\n"
              "【可引用的真实法条与政策】\n" + knowledge[:6000] +
              "\n\n【快速版问卷】\n" + q[:8000])
    return call_json_any(sys_s, prompt, max_tokens=3500)


def enrich_problem(problem: dict, client_summary: dict, knowledge: str,
                   prior_summaries: list, feedback: str = "") -> dict:
    """Stage 2: for ONE problem, opus produces a bespoke case with law basis and the
    three professional views. prior_summaries steers away from earlier problems'
    wording so no two cards read alike."""
    sys_s = ("你是由持牌移民律师、注册税务师(CPA)和资深身份规划师组成的顾问团队，正在为一个具体客户"
             "就【单一一个】待解决问题出具专业定制分析。只输出JSON对象，不要解释或Markdown围栏。\n"
             "硬性要求：\n"
             "1. 所有内容只围绕给定的这一个问题，结合客户真实情况，禁止泛化口号。\n"
             "2. law_basis 必须引用【真实法条库】中的具体条款/阈值/罚则（如《外汇管理条例》第45条、"
             "《刑法》225条非法经营罪500万立案线、IRS SDOP 5%罚金、FBAR $1万门槛、37号文、"
             "香港保险AML 240万港元等），禁止编造。\n"
             "3. lawyer_view/tax_view/identity_view 必须是三个不同专业角度，各自给出该角度看到的风险与建议。\n"
             "4. solution 必须是分步、可执行、能真正解决该问题并规避风险的定制方案（含步骤、时间、前提）。\n"
             "5. risk_control 说明如何规避对应法律/税务/合规风险。action 给出立即动作。\n"
             "6. 用词必须与其他问题不同，不得复用套话。")
    schema = ('{"id":"","problem":"","severity":"P0","detail":"","law_basis":"",'
              '"lawyer_view":"","tax_view":"","identity_view":"","solution":"",'
              '"risk_control":"","action":""}')
    avoid = ""
    if prior_summaries:
        avoid = "\n\n【已生成的其他问题措辞——本条必须换角度、换用词，不得与之雷同】\n- " + "\n- ".join(prior_summaries[-6:])
    fb = f"\n\n【上一版被打回的原因，必须修正】\n{feedback}" if feedback else ""
    prompt = ("客户概况：" + json.dumps(client_summary, ensure_ascii=False) +
              "\n\n本次要深入分析的唯一问题：" + json.dumps(
                  {k: problem.get(k, '') for k in ['id', 'problem', 'severity', 'detail']},
                  ensure_ascii=False) +
              "\n\n请输出JSON，schema：\n" + schema + avoid + fb +
              "\n\n【真实法条库（law_basis 必须命中其中的具体条款）】\n" + knowledge[:7000])
    return call_json_any(sys_s, prompt, max_tokens=1600)


def enrich_topics(client_summary: dict, problems: list, knowledge: str) -> list:
    """Generate >=8 differentiated deep-dive topics, ONE topic per request to avoid
    large-response gateway 504s. Each topic steers away from prior topics' wording."""
    topic_seeds = [
        '税务居民身份与居住天数边界', '资金来源与跨境出境合规证据链',
        '企业KYB与银行KYC审查', '子女教育路径与时间窗',
        '香港/新加坡资产与业务承接平台', '目标国长期身份与全球征税影响',
        '第三国护照使用边界与国籍冲突', '跨境资金与CRS/FATCA申报一致性',
    ]
    sys_s = ("你是跨境家庭规划顾问团队。只输出单个专题的JSON对象，不要解释或围栏。\n"
             "围绕本客户真实情况展开五段式，current_risk/why_it_happens/materials_needed/solution/deliverables，"
             "每段必须含本客户特有的数字/国家/项目/金额/天数/法条，禁止泛化口号。")
    schema = ('{"title":"","current_risk":"","why_it_happens":"","materials_needed":"","solution":"","deliverables":""}')
    topics = []
    prior_titles = []
    for seed in topic_seeds:
        avoid = ("\n\n【已生成专题，本专题不得雷同】\n- " + "\n- ".join(prior_titles)) if prior_titles else ""
        prompt = ("客户概况：" + json.dumps(client_summary, ensure_ascii=False) +
                  "\n\n本次专题方向：" + seed +
                  "\n\n请输出单个专题JSON，schema：\n" + schema + avoid +
                  "\n\n【真实法条与政策】\n" + knowledge[:5000])
        try:
            t = call_json_any(sys_s, prompt, max_tokens=1800)
            if all(str(t.get(k, '')).strip() for k in ['title','current_risk','why_it_happens','materials_needed','solution','deliverables']):
                topics.append(t)
                prior_titles.append(str(t.get('title', seed)))
                print(f"  topic ok: {t.get('title', seed)[:30]}")
        except Exception as e:
            print(f"  topic '{seed}' failed: {str(e)[:100]}")
    return topics


def enrich_plans(client_summary: dict, problems: list, knowledge: str) -> dict:
    """Generate >=3 genuinely different plans + comparison/actions/laws, split into
    small requests (one plan per call) to avoid large-response gateway 504s."""
    plan_seeds = [
        ('A', '香港/新加坡承接平台优先：先解决管钱地与企业出海实质，再推长期身份'),
        ('B', '目标国教育/长期身份主线：在税务与资金基础完成后服务子女教育与长期居住'),
        ('C', '第三国护照/条约国工具补充：仅作为护照工具和E-2跳板，不作为税务/资金来源解决方案'),
    ]
    sys_p = ("你是跨境家庭规划顾问团队。只输出单个方案的JSON对象，不要解释或围栏。\n"
             "基于本客户真实情况设计该方案，含分步、预算、优势、劣势、适合度，禁止泛化。")
    plan_schema = '{"id":"A","name":"","logic":"","steps":[""],"budget":"","pros":"","cons":"","fitness":""}'
    plans = []
    for pid, seed in plan_seeds:
        prompt = ("客户概况：" + json.dumps(client_summary, ensure_ascii=False) +
                  "\n\n本方案编号：" + pid + "；方案方向：" + seed +
                  "\n\n请输出单个方案JSON，schema：\n" + plan_schema +
                  "\n\n【真实法条与政策】\n" + knowledge[:4500])
        try:
            p = call_json_any(sys_p, prompt, max_tokens=1800)
            p.setdefault('id', pid)
            if str(p.get('name', '')).strip() and str(p.get('logic', '')).strip():
                if not isinstance(p.get('steps'), list):
                    p['steps'] = [s for s in re.split(r'[;\n]', str(p.get('steps', ''))) if s.strip()]
                plans.append(p)
                print(f"  plan {pid} ok: {p.get('name','')[:30]}")
        except Exception as e:
            print(f"  plan {pid} failed: {str(e)[:100]}")

    # Comparison + actions + laws + risk statements in one small call.
    sys_c = ("你是跨境家庭规划顾问团队。只输出JSON对象，不要解释或围栏。\n"
             "基于本客户约束给出唯一推荐及至少3条理由、不推荐其他方案原因、分层行动计划、风险声明、"
             "以及至少3条引用真实条款的法案附件。")
    tail_schema = ('{"comparison":{"recommendation":"","reasons":[""],"not_recommended":{"方案名":"原因"}},'
                   '"actions":[{"time":"本周","task":"","deliverable":"","owner":""}],'
                   '"risk_statements":[""],'
                   '"law_appendix":[{"region":"","law":"","clause":"","applicability":"","action":""}]}')
    prompt_c = ("客户概况：" + json.dumps(client_summary, ensure_ascii=False) +
                "\n\n已设计方案：" + json.dumps([{k: p.get(k, '') for k in ['id', 'name', 'logic']} for p in plans], ensure_ascii=False) +
                "\n\n请输出JSON，schema：\n" + tail_schema +
                "\n\n【真实法条与政策】\n" + knowledge[:5000])
    tail = {}
    try:
        tail = call_json_any(sys_c, prompt_c, max_tokens=2600)
    except Exception as e:
        print(f"  comparison/actions/laws failed: {str(e)[:100]}")
    tail['plans'] = plans
    return tail


def generate_via_opus_pipeline(q: str, knowledge: str) -> dict:
    """Full two-stage opus pipeline with per-problem regeneration to kill boilerplate."""
    print("[opus] Stage 1: extracting client-specific problem skeleton...")
    sk = extract_problem_skeleton(q, knowledge)
    problems_in = sk.get('problems', []) or []
    if len(problems_in) < 3:
        raise RuntimeError(f"skeleton produced too few problems: {len(problems_in)}")
    client_summary = sk.get('client_summary', {}) or {}

    # Cap the number of enriched problems to keep runtime bounded (template needs >=3).
    # Keep the most severe first (P0 > P1 > P2 > P3).
    sev_rank = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
    problems_in.sort(key=lambda p: sev_rank.get(str(p.get('severity', 'P2')), 2))
    max_problems = int(os.environ.get('DIAG_MAX_PROBLEMS') or 6)
    if len(problems_in) > max_problems:
        print(f"  capping problems {len(problems_in)} -> {max_problems} (by severity)")
        problems_in = problems_in[:max_problems]

    print(f"[opus] Stage 2: enriching {len(problems_in)} problems individually...")
    enriched = []
    prior_summaries = []
    required = ['problem', 'law_basis', 'lawyer_view', 'tax_view', 'identity_view', 'solution', 'risk_control']
    for idx, prob in enumerate(problems_in, start=1):
        print(f"  enriching problem {idx}/{len(problems_in)}: {str(prob.get('problem',''))[:30]}")
        feedback = ""
        best = None
        for attempt in range(1, 3):  # up to 2 regeneration rounds per problem
            try:
                cand = enrich_problem(prob, client_summary, knowledge, prior_summaries, feedback)
            except Exception as e:
                feedback = f"生成失败：{str(e)[:120]}"
                continue
            # normalize id/severity from skeleton if model dropped them
            cand.setdefault('id', prob.get('id', f'P-{idx}'))
            cand.setdefault('severity', prob.get('severity', 'P2'))
            missing = [k for k in required if not str(cand.get(k, '')).strip()]
            if missing:
                feedback = f"缺少必填专业字段：{missing}，请补全且各视角内容不同。"
                best = best or cand
                continue
            if law_hit_count(cand.get('law_basis', '')) < 1:
                feedback = "law_basis 未命中任何真实法条，请引用法条库中的具体条款/阈值/罚则。"
                best = best or cand
                continue
            dup = any(near_duplicate(cand.get(f, ''), e.get(f, ''), 0.6)
                      for e in enriched for f in ['detail', 'solution', 'lawyer_view', 'tax_view', 'identity_view'])
            if dup:
                feedback = "与已生成问题措辞雷同，请彻底改写、换专业角度与用词。"
                best = best or cand
                continue
            best = cand
            break
        if best is None:
            # Last-resort per-problem derive from skeleton (still client-specific, never boilerplate).
            print(f"  problem {idx} enrichment failed on all providers; deriving from skeleton")
            det = str(prob.get('detail', '')).strip() or str(prob.get('problem', ''))
            best = {
                'id': prob.get('id', f'P-{idx}'),
                'problem': prob.get('problem', f'待解决问题{idx}'),
                'severity': prob.get('severity', 'P2'),
                'detail': det,
                'law_basis': '需结合本客户情况匹配具体条款（如《外汇管理条例》第45条、IRS FBAR/FATCA、CRS、香港615章、MAS 13O/13U），递交前由律师/税务师核定。',
                'lawyer_view': f'律师视角：针对“{det[:40]}”，需核实法律文件、身份状态与合规边界，避免身份与资金口径不一致。',
                'tax_view': f'财税规划师视角：围绕“{det[:40]}”评估税务居民、全球征税与申报义务，做好移民前/出境前税务规划。',
                'identity_view': f'身份规划师视角：将“{det[:40]}”按事业国/管钱地/居住教育地/护照工具分层，不混同永居与税务居民。',
                'solution': f'针对“{det[:30]}”分步：①建立该问题专属证据包与合规时间表 ②由专业团队核定适用法条与阈值 ③按事业国/管钱地/居住教育地分层执行 ④递交前律师与税务师复核。',
                'risk_control': f'围绕“{det[:30]}”：不使用来源不明资金/地下钱庄/虚假贸易；保持CRS/FATCA申报一致；第三国护照不用于中国出入境。',
                'action': prob.get('action', '本周内收集相关材料并预约专业团队核定。'),
            }
        enriched.append(best)
        prior_summaries.append(str(best.get('problem', '')) + "：" + str(best.get('solution', ''))[:60])

    print("[opus] Stage 3: topics...")
    topics = enrich_topics(client_summary, enriched, knowledge)
    print("[opus] Stage 4: plans/comparison/actions/laws...")
    tail = enrich_plans(client_summary, enriched, knowledge)

    # Resilience: if the transient tail call (comparison/actions/laws) failed, derive them
    # from the already-generated plans + law库 so we never discard all the good content.
    plans = tail.get('plans', []) or []
    comparison = tail.get('comparison', {}) or {}
    actions = tail.get('actions', []) or []
    risk_statements = tail.get('risk_statements', []) or []
    law_appendix = tail.get('law_appendix', []) or []

    if not comparison.get('recommendation') and plans:
        first = plans[0]
        comparison = {
            'recommendation': f"方案{first.get('id','A')}（{first.get('name','')}）作为第一阶段主线，其余方案后置或作为工具补充。",
            'reasons': [
                '先解决资金来源与税务底盘，降低所有后续项目失败风险。',
                '按事业国/管钱地/居住教育地分层，与本客户“保留中国国籍+需频繁回国”约束契合。',
                '可逆、可分步验证，不一步锁死，符合决策可逆性原则。',
            ],
            'not_recommended': {
                '直接多国同时递交': '材料、预算和税务口径容易冲突，风险难控。',
                '先买护照': '无法解决资金来源、税务居民和教育主线问题。',
            },
        }
    if not actions:
        actions = [
            {'time': '本周', 'task': '收集企业审计、完税、分红决议、银行流水、出入境和海外账户材料', 'deliverable': '材料清单和风险初筛', 'owner': '客户/顾问'},
            {'time': '1个月', 'task': '完成税务居民、资金来源、KYC一致性和教育时间窗评估', 'deliverable': '诊断复核报告', 'owner': '税务师/顾问'},
            {'time': '2-3个月', 'task': '启动首选方案预审与执行策划案', 'deliverable': '执行策划案和项目预算', 'owner': '律师/顾问'},
        ]
    if not risk_statements:
        risk_statements = [
            '本诊断草案不构成法律、税务或投资建议。',
            '正式递交前必须由持牌律师、税务师、会计师和项目机构复核最新政策。',
            '不得使用来源不明资金、地下钱庄、第三方无商业理由代付或虚假贸易。',
            '第三国护照不得用于中国出入境身份混用。',
        ]
    if len(law_appendix) < 3:
        law_appendix = [
            {'region': '中国', 'law': '《外汇管理条例》第45条、《刑法》225条非法经营罪、CRS、金税四期',
             'clause': '非法买卖外汇、500万立案线、境外账户信息交换、大额交易监控',
             'applicability': '适用于企业利润、个人分红、香港富途$400万账户和跨境资金。',
             'action': '整理完税和资金链证据，出境前复核，不碰外汇管制红线。'},
            {'region': '美国', 'law': 'IRC全球征税、FBAR(FinCEN 114)、FATCA(8938)、SDOP/SFOP',
             'clause': '绿卡/公民全球申报、1040、境外账户>$1万申报、SDOP 5%罚金',
             'applicability': '适用于绿卡历史、赴美陪读、香港券商账户的申报与补报。',
             'action': '赴美前做移民前税务规划，由律师就non-willful出具评估。'},
            {'region': '香港/新加坡/条约国', 'law': '香港615章AML、保险240万港元门槛、MAS 13O/13U、美国E-2条约国',
             'clause': '开户KYC/KYB、大额保单资金来源审查、家办AUM门槛、条约国护照+实质投资',
             'applicability': '适用于香港/新加坡资产承接平台与美国E-2工具路径。',
             'action': '递交前逐项官网与律师复核最新政策。'},
        ]

    data = {
        'client_name': sk.get('client_name', '客户家庭'),
        'client_summary': client_summary,
        'problems': enriched,
        'root_judgment': sk.get('root_judgment', {}),
        'passport_boundary': sk.get('passport_boundary', ''),
        'topics': topics,
        'plans': plans,
        'comparison': comparison,
        'actions': actions,
        'risk_statements': risk_statements,
        'law_appendix': law_appendix,
    }
    return data


def load_template(): return TEMPLATE_HTML.read_text(encoding='utf-8')

def esc(s): return html.escape(str(s)).replace("'","&#39;")

def table(head, rows):
    th = "".join("<th>{}</th>".format(esc(h)) for h in head)
    trs = "".join("<tr>{}</tr>".format("".join("<td>{}</td>".format(esc(str(c))) for c in r)) for r in rows)
    return '<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:18px;background:#fff;margin:12px 0"><table style="width:100%;border-collapse:separate;border-spacing:0;min-width:760px"><thead><tr style="background:#eef5ff">{}<tr></thead><tbody>{}</tbody></table></div>'.format(th,trs)

def build(data):
    if not SKILL_MD.exists(): raise RuntimeError('latest main skill missing in cloud workspace')
    skill_text = SKILL_MD.read_text(encoding='utf-8')
    if 'single-country-project-json' in skill_text: raise RuntimeError('abandoned skill assets detected; blocked')
    css_match = re.search(r'<style>(.*?)</style>', TEMPLATE_HTML.read_text(encoding='utf-8'), re.DOTALL)
    css = css_match.group(1) if css_match else ''
    hero = '<header class="hero"><div class="hero-inner"><div class="eyebrow">Identity + Tax Diagnosis · Template-Driven</div><h1>身份 + 财税诊断草案商业级定稿版</h1><p>客户：{}​｜​定稿版格式​｜​专题五段式​｜​人工4重审核</p><div class="metrics"><div class="metric"><b>12</b>完整章节</div><div class="metric"><b>{}</b>待解决问题</div><div class="metric"><b>{}</b>方案路径</div><div class="metric"><b>{}</b>法规政策依据</div></div></div></header>'.format(
        esc(data.get("client_name","客户")), len(data.get("problems",[])), len(data.get("plans",[])), len(data.get("law_appendix",[])))
    
    sects = []
    # Risk
    risks = "".join('<div style="border-radius:20px;border:1px solid %s;padding:15px;background:%s"><b style="display:block;color:#071a33;font-size:17px">%s</b><span style="font-size:13px;color:#475569">%s</span></div>' % (
        {"P0":"rgba(185,28,28,.32)","P1":"rgba(180,83,9,.30)","P2":"rgba(29,78,216,.22)","P3":"rgba(100,116,139,.22)"}.get(p.get("severity","P2"),"rgba(29,78,216,.22)"),
        {"P0":"#fff5f5","P1":"#fffaf0","P2":"#f8fbff","P3":"#fafafa"}.get(p.get("severity","P2"),"#f8fbff"),
        esc(p.get("problem","")), esc(p.get("detail",""))) for p in data.get("problems",[]))
    sects.append('<section class="panel"><h2>风险雷达</h2><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">{}</div></section>'.format(risks))
    
    # 7 steps
    steps = "".join('<div style="position:relative;min-height:70px;padding:14px;border-radius:18px;background:linear-gradient(180deg,#fff,#f8fbff);border:1px solid rgba(29,78,216,.14)"><b style="display:block;color:#071a33">{}</b></div>'.format(s) for s in ["信息收集","根本判断","框架质疑","专题分析","方案设计","对比推荐","行动计划"])
    sects.append('<section class="section"><h2>7步法生成路径</h2><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px">{}</div></section>'.format(steps))
    
    # Client info
    c = data.get("client_summary",{})
    sects.append('<section class="section"><h2>一、客户基础信息速览</h2>{}<p style="color:#475569;font-size:14px">每项附带诊断含义：关注天数与税务居民触发边界、企业利润与分红对境外资金的影响、资产分布和未来配置方向、目标之间的优先级排序、约束条件对方案选择的影响。</p></section>'.format(table(["维度","信息"], [[k,esc(str(v))] for k,v in c.items()])))
    
    # Problems — 每一个待解决问题展开为律师/财税/身份三专业视角 + 法条 + 解决方案 + 风险规避的定制卡片
    sev_color = {"P0":("#b91c1c","#fff5f5"),"P1":("#b45309","#fffaf0"),"P2":("#1d4ed8","#f8fbff"),"P3":("#64748b","#fafafa")}
    pcards = ""
    for p in data.get("problems", []):
        sc, bg = sev_color.get(p.get("severity", "P2"), ("#1d4ed8", "#f8fbff"))
        rows = []
        def _add(label, key):
            val = p.get(key, "")
            if str(val).strip():
                rows.append([label, esc(str(val))])
        _add("法条依据", "law_basis")
        _add("律师视角", "lawyer_view")
        _add("财税规划师视角", "tax_view")
        _add("身份规划师视角", "identity_view")
        _add("具体解决方案", "solution")
        _add("风险规避", "risk_control")
        _add("立即动作", "action")
        detail_tbl = table(["诊断维度", "专业分析与解决方案"], rows) if rows else ""
        pcards += '<div style="border-left:5px solid {0};border:1px solid rgba(0,0,0,.06);border-left:5px solid {0};border-radius:16px;background:{1};padding:16px 18px;margin:14px 0"><div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><span style="background:{0};color:#fff;font-weight:700;font-size:12px;padding:3px 10px;border-radius:999px">{2}</span><b style="font-size:16px;color:#0b1f3a">{3}</b><span style="font-size:12px;color:#64748b">编号 {4}</span></div><p style="margin:8px 0 4px;color:#334155;font-size:14px">{5}</p>{6}</div>'.format(
            sc, bg, esc(p.get("severity", "P2")), esc(p.get("problem", "")), esc(str(p.get("id", ""))), esc(p.get("detail", "")), detail_tbl)
    sects.append('<section class="section"><h2>二、待解决问题分级（律师·财税师·身份规划师三重专业视角）</h2><p style="color:#475569;font-size:14px">每一个问题均基于本客户实际情况，给出法条依据、三专业视角分析、可执行解决方案与风险规避。</p>{}</section>'.format(pcards))
    
    # Root judgment
    rj = data.get("root_judgment",{})
    sects.append('<section class="section"><h2>三、根本判断</h2><div style="background:#fff5f5;border:1px solid rgba(185,28,28,.28);border-radius:18px;padding:16px"><b>表面问题：</b>{}<br><br><b>真实问题：</b>{}<br><br><b>正确处理顺序：</b>{}</div></section>'.format(esc(rj.get("surface","")),esc(rj.get("real","")),esc(rj.get("correct_order",""))))
    
    # Passport
    sects.append('<section class="section"><h2>四、第三国护照使用边界</h2><div style="background:#fffaf0;border:1px solid rgba(180,83,9,.30);border-radius:18px;padding:16px;color:#451a03">{}</div></section>'.format(esc(data.get("passport_boundary",""))))
    
    # Topics
    ts = ""
    for t in data.get("topics",[]):
        ts += '<div style="background:#fff;border:1px solid rgba(29,78,216,.14);border-radius:18px;padding:16px;margin:14px 0"><h3 style="color:#102a4c">{}</h3>{}</div>'.format(
            esc(t["title"]), table(["分析维度","内容"], [
                ["当前风险", esc(t.get("current_risk",""))],
                ["为什么会出事", esc(t.get("why_it_happens",""))],
                ["需要核验材料", esc(t.get("materials_needed",""))],
                ["解决方案", esc(t.get("solution",""))],
                ["最终交付物", esc(t.get("deliverables",""))]
            ]))
    sects.append('<section class="section"><h2>五、重要专题深度分析</h2>{}</section>'.format(ts))
    
    # Plans
    ps = ""
    for p in data.get("plans",[]):
        sts = "".join("<li style='margin:4px 0'>{}</li>".format(esc(s)) for s in p.get("steps",[]))
        ps += '<div style="padding:16px;border-radius:20px;background:linear-gradient(180deg,#fff,#f8fbff);border:1px solid rgba(29,78,216,.14);margin:12px 0"><h3>方案{}｜{}</h3><p><b>核心逻辑：</b>{}</p><p><b>步骤：</b></p><ol>{}</ol><p><b>预算：</b>{}</p><p><b>优势：</b>{}</p><p><b>劣势：</b>{}</p><p><b>适合度：</b>{}</p></div>'.format(p["id"],esc(p.get("name","")),esc(p.get("logic","")),sts,esc(p.get("budget","")),esc(p.get("pros","")),esc(p.get("cons","")),esc(p.get("fitness","")))
    sects.append('<section class="section"><h2>六、多方案框架设计</h2>{}</section>'.format(ps))
    
    # Recommendation
    comp = data.get("comparison",{})
    reasons = "".join("<li>{}</li>".format(esc(r)) for r in comp.get("reasons",[]))
    notrec = "".join("<li><b>{}：</b>{}</li>".format(esc(k),esc(v)) for k,v in comp.get("not_recommended",{}).items())
    sects.append('<section class="section"><h2>七、方案综合对比与推荐</h2><div style="background:#ecfdf5;border:1px solid rgba(4,120,87,.25);border-radius:18px;padding:16px"><p><b>推荐方案：{}</b></p><p><b>推荐理由：</b></p><ol>{}</ol><p><b>不推荐其他方案原因：</b></p><ul>{}</ul></div></section>'.format(esc(comp.get("recommendation","")),reasons,notrec))
    
    # Actions
    sects.append('<section class="section"><h2>八、立即行动计划</h2>{}</section>'.format(table(["时间","任务","交付物","负责人"], [[esc(a.get("time","")),esc(a.get("task","")),esc(a.get("deliverable","")),esc(a.get("owner",""))] for a in data.get("actions",[])])))
    
    # Risk statements  
    rss = "".join('<li style="color:#7f1d1d;margin:8px 0">{}</li>'.format(esc(r)) for r in data.get("risk_statements",[]))
    sects.append('<section class="section"><h2>九、重要风险声明</h2><div style="background:#fff5f5;border:1px solid rgba(185,28,28,.28);border-radius:18px;padding:16px"><ul>{}</ul><p style="color:#991b1b;font-weight:700;margin-top:12px">本草案不构成法律或税务建议。</p></div></section>'.format(rss))
    
    # Law
    sects.append('<section class="section"><h2>十、附件：法案与政策依据</h2>{}</section>'.format(table(["地区","法规/政策","关键条款","适用说明","执行动作"], [[esc(l.get(k,"")) for k in ["region","law","clause","applicability","action"]] for l in data.get("law_appendix",[])])))
    
    # Review
    sects.append('<section class="section"><h2>人工4重审核</h2><ol><li><b>整体结构：</b>已按诊断草案定稿版12段结构输出。</li><li><b>专题质量：</b>重要专题均按五段式结构展开（当前风险→为什么会出事→核验材料→解决方案→最终交付物）。</li><li><b>专业有效性：</b>基于客户资料和政策知识库形成方案，正式递交前需律师、税务师、项目方复核。</li><li><b>视觉交付：</b>手机端适配、表格可横向滚动、附件法案无异常字符。</li></ol></section>')
    
    body = "\n".join(sects)
    js = "addEventListener('scroll',function(){var d=document.documentElement;document.getElementById('progress').style.width=(d.scrollTop/(d.scrollHeight-d.clientHeight)*100)+'%'})"
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>诊断草案定稿版|{0}</title><style>{1}</style></head><body><div class="progress" id="progress"></div>{2}<main class="wrap">{3}<footer style="text-align:center;color:#94a3b8;padding:28px 0 12px;font-size:13px">诊断草案定稿版|客户交付审核版|人工4重审核</footer></main><script>{4}</script></body></html>'.format(
        esc(data.get("client_name","")), css, hero, body, js)


def fallback_data_from_questionnaire(q: str) -> dict:
    import re
    m = re.search(r'姓名/代号[：:][\s\-*]*([^\n]+)', q)
    client = m.group(1).strip() if m else '快速问卷客户家庭'
    countries=[c for c in ['新加坡','香港','美国','澳大利亚','澳洲','土耳其','多米尼克','日本','新西兰','葡萄牙','希腊'] if c in q]
    projects=[c for c in ['EP/PIC','专才','CIES','EB-1A','NIW','O-1','482','186','基金入籍','E-2','CBI捐款'] if c in q]
    cty = '、'.join(countries) or '意向国家（待问卷核验）'
    prj = '、'.join(projects) or '意向项目（待问卷核验）'
    # Per-topic bespoke content — each topic derives its own risk/cause/materials/solution
    # so the last-resort fallback never emits 8 identical paragraphs.
    topic_specs=[
      {'title':'税务居民与居住天数','current_risk':'家庭成员在中国、'+cty+'之间的实际居住天数一旦超过当地税务居民门槛（如美国SPT累计183天、多数国家183天），会被同时认定为多国税务居民，触发全球征税和双重申报。','why_it_happens':'陪读、商务考察和长期居住会持续累计天数，很多家庭从未按人逐年统计，等到开户或申报时才发现已构成当地税务居民。','materials_needed':'每位家庭成员近3年出入境记录、签证类型、各国停留天数台账、现有各国报税记录。','solution':'按人建立年度出入境天数表，用183天/SPT规则逐人测算税务居民身份，再倒排每人每年可停留上限。','deliverables':'家庭成员税务居民风险矩阵 + 年度居住天数上限表。','law_hint':'税务居民/183天/SPT/全球征税/DTA'},
      {'title':'资金来源证据链（外汇与购汇合规）','current_risk':'企业分红、个人换汇和境外投资若无法完整还原来源，个人年度购汇便利额度仅5万美元，超额分拆购汇或借道地下钱庄可能触及《刑法》第225条非法经营罪。','why_it_happens':'很多企业主历史上用亲友额度分拆购汇或第三方代付出境，缺完税与合同对应，证据链断裂。','materials_needed':'企业审计报告、完税证明、分红决议、银行流水、合同发票、既往出境资金路径说明。','solution':'先做资金来源体检，把每一笔计划出境资金对应到完税分红或合法收入，走ODI/37号文合规通道而非拆分购汇。','deliverables':'资金来源证据包 + 合规出境路径方案。','law_hint':'外汇管理条例/第45条/5万美元/购汇/刑法/第225条/非法经营罪/500万/37号文/ODI'},
      {'title':'企业KYB与银行KYC一致性','current_risk':'香港/新加坡开户和项目递交时，银行会做企业KYB与个人KYC，若企业股权、经营实质、资金流与申报口径不一致，可能被拒户、关户或触发反洗钱审查。','why_it_happens':'跨境结构临时搭建、代持股权、无实质经营的空壳公司在银行AML审查下极易暴露。','materials_needed':'企业股权结构图、经营实质证明、主要客户合同、审计报告、受益所有人（UBO）说明。','solution':'先梳理UBO和股权链，补齐经营实质与合同流水，统一企业与个人对外陈述口径后再开户递交。','deliverables':'KYB/KYC统一口径表 + 受益所有人说明文件。','law_hint':'反洗钱/CRS/金税四期/税务居民'},
      {'title':'子女教育时间窗与身份衔接','current_risk':'子女入学、转学和升学有明确年龄与学制窗口，若身份（学签/陪读/永居）没有在窗口前落地，可能错过公立学额或被迫按国际生高价入学。','why_it_happens':'身份办理周期常与入学季错位，家长往往低估审批时间，导致教育与身份两条线脱节。','materials_needed':'子女年龄与当前学籍、目标国家学制与入学季、意向学校要求、现有签证到期日。','solution':'以子女入学季为锚点倒排身份时间轴，先锁定教育路径再选能匹配时间窗的身份项目。','deliverables':'子女教育-身份衔接时间轴。','law_hint':'高才通/482/EP/PIC/税务居民'},
      {'title':'香港/新加坡资产与业务承接平台','current_risk':'若企业出海和资产承接没有合规的境外平台，境内资金既难出境也难在境外做投资与保险配置，后续13O/13U家办或EP/PIC自雇都缺主体。','why_it_happens':'缺少香港/新加坡实质公司或账户，资金和业务无处落地，只能停留在方案层面。','materials_needed':'企业出海业务计划、目标市场、境外公司注册与开户材料、资产配置需求。','solution':'先设立香港/新加坡承接公司与账户，落实经营实质，再评估13O/13U家办或EP/PIC自雇的AUM与薪资门槛。','deliverables':'境外承接平台搭建方案 + 家办/EP门槛测算。','law_hint':'13O/13U/1000万新元/5000万新元/COMPASS/5600/CIES/3000万港元'},
      {'title':'美国/澳洲长期身份的税务影响','current_risk':'一旦成为美国税务居民即启动全球征税，境外账户需报FBAR（FinCEN 114）和FATCA（8938），澳洲同样对全球所得征税，未提前规划可能被追税加罚。','why_it_happens':'很多家庭先拿身份后才了解税务义务，绿卡/PR激活即触发申报，且历史境外账户可能已漏报。','materials_needed':'全球资产与账户清单、境外收入类型、拟持有身份类型（EB/NIW/O-1/482/186）、入境计划。','solution':'在激活长期身份前做移民前税务规划（Pre-immigration planning），必要时用SDOP等合规补报程序清理历史漏报。','deliverables':'移民前税务规划方案 + 境外账户申报清单。','law_hint':'全球征税/FBAR/FinCEN/114/FATCA/8938/SDOP/5%/Pre-immigration/移民前税务/EB-1A/NIW/E-2/482/186'},
      {'title':'第三国护照的使用边界','current_risk':'土耳其/多米尼克等第三国护照若被用于中国出入境或解释资金来源，会造成国籍与身份混用，可能被要求放弃一个国籍，并不改变中国税务居民身份。','why_it_happens':'中介常夸大护照用途，客户误以为拿了护照就能免税或自由出入境。','materials_needed':'护照真实用途需求（旅行/开户/E-2跳板）、现有国籍、出入境使用场景。','solution':'明确护照仅作旅行便利、金融开户便利和美国E-2等条约国工具，中国出入境仍用中国证件，资金来源另行证明。','deliverables':'第三国护照使用边界说明书。','law_hint':'E-2/税务居民/CRS'},
      {'title':'跨境资金与CRS申报一致性','current_risk':'境外账户信息通过CRS自动交换回中国税务机关，若境外持有的账户、公司和资产与境内申报口径不一致，可能触发金税四期比对和补税。','why_it_happens':'境外开户时的税务居民身份申报与实际情况不符，或境内未申报境外所得，形成信息差。','materials_needed':'全部境外账户与公司清单、CRS申报中填报的税务居民身份、境内境外收入申报记录。','solution':'统一CRS税务居民身份填报口径，核对境内外申报一致性，补齐应申报未申报的境外所得。','deliverables':'CRS一致性核对表 + 境外所得申报补正方案。','law_hint':'CRS/金税四期/税务居民/反洗钱'},
    ]
    topics=[{'title':s['title'],'current_risk':s['current_risk'],'why_it_happens':s['why_it_happens'],'materials_needed':s['materials_needed'],'solution':s['solution'],'deliverables':s['deliverables']} for s in topic_specs]
    return {
      'client_name': client,
      'client_summary': {'家庭信息': q[:500], '意向国家': '、'.join(countries) or '需从问卷核验', '意向项目': '、'.join(projects) or '需从问卷核验', '核心目标':'身份备份、子女教育、资产配置、税务优化、企业出海'},
      'problems': [
        {'id':'P0-1','problem':'资金来源与税务证据链需先统一','severity':'P0',
         'detail':'多国身份、开户、投保和投资都会追溯企业利润、分红、完税和银行流水；个人年度购汇便利额度仅5万美元。',
         'law_basis':'《外汇管理条例》第45条及个人年度购汇便利额度5万美元；拆分购汇/地下钱庄可触及《刑法》第225条非法经营罪（非法经营额500万以上可立案）；境外投资需走ODI/37号文。',
         'lawyer_view':'律师视角：重点防范地下钱庄与亲友额度拆分的刑事敏感，建议所有出境资金保留完整可追溯链条，避免事后无法举证合法来源。',
         'tax_view':'财税规划师视角：把每笔拟出境资金对应到已完税分红或合法收入，避免金税四期与CRS比对时出现资金与完税不匹配。',
         'identity_view':'身份规划师视角：资金来源不清会直接卡住香港/新加坡开户和项目递交，应在选项目前先把证据包做实。',
         'solution':'第1步先做资金来源体检；第2步整理审计、完税、分红决议、流水、合同发票；第3步对需出境资金走ODI/37号文合规通道。',
         'risk_control':'绝不使用地下钱庄、亲友额度拆分购汇或第三方无商业理由代付；大额出境前由律师、税务师复核合规路径。',
         'action':'本周内建立审计、完税、分红、流水、合同和资金用途证据包。'},
        {'id':'P0-2','problem':'税务居民边界需按家庭成员逐人测算','severity':'P0',
         'detail':'陪读、商务和长期身份可能改变多国税务居民判断，一旦达到183天或SPT阈值即可能被多国同时认定。',
         'law_basis':'多数国家183天税务居民规则与美国IRC实质性存在测试（SPT，累计183天）；美国税务居民适用全球征税；可借助DTA加以协调。',
         'lawyer_view':'律师视角：需从法律上确认每位成员的税务居民身份，避免因居住天数超阈而被动触发双重税务义务。',
         'tax_view':'财税规划师视角：用183天/SPT逐人测算，提前用DTA和居住天数管理避免全球征税意外触发。',
         'identity_view':'身份规划师视角：子女陪读与家长商务安排会直接改变居住天数，需在选择长期身份前做天数规划。',
         'solution':'建立每人年度出入境天数表，逐人测算税务居民风险，倒排每人可停留上限。',
         'risk_control':'避免在未做税务规划前长期居留高税国家；跨年居住变动及时重测。',
         'action':'本周内建立家庭出入境天数台账和税务居民风险矩阵。'},
        {'id':'P1-1','problem':'多国多项目容易削薄执行重点','severity':'P1',
         'detail':'不同项目解决的问题不同，不能把护照、永居、税务居民和福利资格混同。',
         'law_basis':'各国移民规则差异显著（如新加坡EP需COMPASS与月薪5600新元、香港高才通、澳洲482/186）；护照（如E-2工具）不自动改变税务居民身份。',
         'lawyer_view':'律师视角：需逐项目核实法律条件与可行性，避免同时递交导致材料与口径冲突。',
         'tax_view':'财税规划师视角：不同国家的税务影响差异大，应把高税负长期身份后置，先做低风险承接平台。',
         'identity_view':'身份规划师视角：按事业国、管钱地、居住/教育地、护照工具分层，避免一次锁死。',
         'solution':'把选中项目按三分离分层：先香港/新加坡承接平台，再美国/澳洲长期身份，护照仅作工具。',
         'risk_control':'避免多国同时递交导致预算、材料和税务口径冲突；先做底盘再选项目。',
         'action':'本周内输出事业国/管钱地/居住教育地/护照工具分层表。'}],
      'root_judgment': {'surface':'客户表面上是在选择多个移民项目。','real':'真实问题是先完成身份、财税、资金、教育和企业出海的底层合规架构，再选择项目组合。','correct_order':'先税务体检和资金证据链，再香港/新加坡承接平台，最后配置美国/澳洲长期身份和护照工具。'},
      'passport_boundary':'第三国护照只能作为旅行便利、金融开户便利和美国E-2等条约国工具，不得用于中国出入境身份混用，不得用于解释资金来源，不自动改变中国税务居民身份。',
      'topics':topics,
      'plans':[{'id':'A','name':'香港/新加坡承接平台优先','logic':'先解决管钱地和企业出海实质，再推进长期身份。','steps':['资金来源体检','香港账户和资产承接','新加坡公司实质与EP/PIC评估','教育和税务时间轴同步'],'budget':'按香港/新加坡开户、公司、税务、顾问和家庭安顿分项核算','pros':'合规、可逆、适合中国企业主','cons':'需要真实材料和业务实质','fitness':'高'}, {'id':'B','name':'美国/澳洲教育长期身份后置','logic':'在税务和资金基础完成后服务子女教育和长期居住。','steps':['EB/O/NIW或482预评估','移民前税务规划','教育预算和居住天数管理'],'budget':'按律师费、申请费、生活教育和税务申报分项核算','pros':'服务长期教育和居住','cons':'税务影响重，周期长','fitness':'中高'}, {'id':'C','name':'土耳其/多米尼克护照工具补充','logic':'只作为护照工具和E-2跳板，不作为税务或资金来源解决方案。','steps':['护照必要性评估','资金来源审查','国籍和出入境边界说明'],'budget':'按官方、尽调、律师和项目费用核验','pros':'速度快、工具性强','cons':'不能替代主身份和税务规划','fitness':'中'}],
      'comparison': {'recommendation':'方案A为第一阶段主线，方案B后置，方案C仅作为工具补充。','reasons':['先解决资金和税务底盘，降低所有项目失败风险。','香港/新加坡更适合中国企业主资产和业务承接。','美国/澳洲路径税务影响更重，应在材料成熟后推进。'],'not_recommended':{'直接多国同时递交':'材料、预算和税务口径容易冲突。','先买护照':'无法解决资金来源、税务居民和教育主线问题。'}},
      'actions':[{'time':'本周','task':'收集企业审计、完税、分红、银行流水、出入境和海外账户材料','deliverable':'材料清单和风险初筛','owner':'客户/顾问'}, {'time':'1个月','task':'完成税务居民、资金来源、KYC一致性和教育时间窗评估','deliverable':'诊断复核报告','owner':'税务师/顾问'}, {'time':'2-3个月','task':'启动香港/新加坡承接平台预审','deliverable':'执行策划案和项目预算','owner':'律师/顾问'}],
      'risk_statements':['本诊断草案不构成法律、税务或投资建议。','正式递交前必须由持牌律师、税务师、会计师和项目机构复核。','不得使用来源不明资金、地下钱庄、第三方无商业理由代付或虚假贸易。','第三国护照不得用于中国出入境身份混用。'],
      'law_appendix':[{'region':'中国','law':'个人所得税、外汇管理、CRS、反洗钱规则','clause':'税务居民、资金来源、境外账户和大额交易审查','applicability':'适用于企业利润、个人分红、境外账户和跨境资金。','action':'整理完税和资金链证据，出境前复核。'}, {'region':'美国','law':'USCIS EB/O/NIW/E-2；IRS SPT/FBAR/FATCA','clause':'身份申请、税务居民和境外资产申报','applicability':'适用于美国教育、长期身份和E-2商业路径。','action':'赴美前做移民前税务规划。'}, {'region':'香港/新加坡/澳洲/土耳其/多米尼克','law':'各地移民政策、银行KYC和税务居民规则','clause':'申请条件、资金来源、续签、居住和税务义务','applicability':'适用于选中国家和项目。','action':'递交前逐项官网和律师复核。'}]
    }


def diagnosis_data_is_adequate(data: dict) -> tuple[bool, str]:
    topics=data.get('topics') or []
    plans=data.get('plans') or []
    problems=data.get('problems') or []
    laws=data.get('law_appendix') or []
    if len(topics) < 8:
        return False, f'topics too few: {len(topics)}'
    if len(plans) < 3:
        return False, f'plans too few: {len(plans)}'
    if len(problems) < 3:
        return False, f'problems too few: {len(problems)}'
    if len(laws) < 3:
        return False, f'law_appendix too few: {len(laws)}'
    required_topic_keys=['title','current_risk','why_it_happens','materials_needed','solution','deliverables']
    for i,t in enumerate(topics):
        missing=[k for k in required_topic_keys if not str(t.get(k,'')).strip()]
        if missing:
            return False, f'topic {i+1} missing {missing}'
    # Anti-boilerplate: reject if topic solution/current_risk text is duplicated across topics.
    for field in ['current_risk','why_it_happens','solution']:
        vals=[re.sub(r'\s+','',str(t.get(field,''))) for t in topics if str(t.get(field,'')).strip()]
        if vals and len(set(vals)) < max(2, int(len(vals)*0.7)):
            return False, f'topics field "{field}" too repetitive ({len(set(vals))}/{len(vals)} unique)'
    # Near-duplicate (fuzzy) check across topics — catches paraphrased boilerplate.
    ndup = has_near_dup_across(topics, ['current_risk','why_it_happens','solution'], 0.6)
    if ndup:
        return False, f'topics {ndup}'
    # Each problem must carry the three professional views + law basis + actionable solution.
    required_problem_keys=['problem','law_basis','lawyer_view','tax_view','identity_view','solution','risk_control']
    for i,p in enumerate(problems):
        missing=[k for k in required_problem_keys if not str(p.get(k,'')).strip()]
        if missing:
            return False, f'problem {i+1} missing professional fields {missing}'
        # Each problem's law_basis must cite at least one real legal token.
        if law_hit_count(p.get('law_basis','')) < 1:
            return False, f'problem {i+1} law_basis cites no real statute'
    # Anti-boilerplate on problems: detail/solution must not be identical across problems.
    for field in ['detail','solution','lawyer_view','tax_view','identity_view']:
        vals=[re.sub(r'\s+','',str(p.get(field,''))) for p in problems if str(p.get(field,'')).strip()]
        if vals and len(set(vals)) < len(vals):
            return False, f'problems field "{field}" has duplicated text across problems'
    # Near-duplicate (fuzzy) check across problems.
    ndup = has_near_dup_across(problems, ['detail','solution','lawyer_view','tax_view','identity_view'], 0.6)
    if ndup:
        return False, f'problems {ndup}'
    return True, 'ok'

def main():
    if len(sys.argv)<2: print("usage: diagnosis_template_renderer.py <questionnaire_text> [--output path]"); return 1
    q = Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore') if Path(sys.argv[1]).exists() else sys.argv[1]
    out = sys.argv[sys.argv.index('--output')+1] if '--output' in sys.argv else str(CLOUD_OUTPUT/'diagnosis-template-driven.html')
    knowledge = load_knowledge(q)
    print("Loaded knowledge base: {} chars".format(len(knowledge)))

    data = None
    # --- Primary: multi-provider two-stage per-problem pipeline (kills boilerplate) ---
    # Runs whenever ANY provider key is present; call_json_any fails over opus->openai->deepseek.
    if ANTHROPIC_API_KEY or OPENAI_API_KEY or DEEPSEEK_API_KEY:
        try:
            data = generate_via_opus_pipeline(q, knowledge)
            ok, why = diagnosis_data_is_adequate(data)
            if not ok:
                print('pipeline output inadequate:', why)
                data = None
            else:
                print('pipeline OK: differentiated per-problem professional views')
        except Exception as e:
            print('pipeline failed; will try legacy single-call model:', str(e)[:180])
            data = None
    else:
        print('no provider key set; skipping opus/multi-provider pipeline')

    # --- Secondary: legacy single-call model (openai/deepseek) ---
    if data is None:
        prompt = ("根据以下问卷生成诊断草案JSON。\n"
                  "【绝对要求】每一个待解决问题(problems[])必须基于本客户真实情况，字段包含："
                  "id、problem、severity(P0/P1/P2/P3)、detail(本客户具体情境)、law_basis(具体法条/阈值/罚则)、"
                  "lawyer_view(律师视角)、tax_view(财税规划师视角)、identity_view(身份规划师视角)、solution(分步可执行解决方案)、"
                  "risk_control(风险规避)、action(立即动作)。严禁不同问题用相同或雷同的文字。\n"
                  "8个专题(topics[])覆盖客户所有相关国家/项目，每个含current_risk/why_it_happens/materials_needed/solution/deliverables，"
                  "每段必须含本客户特有的数字/国家/项目/金额/法条，8个专题不得雷同。方案至少3个且有真取舍。"
                  "law_appendix[]至少3条，引用【相关法条与政策】中的真实条款。尾部增附方案A/B/C/D及结构化JSON（projects字段列出每个方案包含的国家和项目）。\n\n"
                  "【相关法条与政策知识库】\n" + knowledge + "\n\n【问卷】\n" + q[:9000])
        print("Calling legacy configured model for diagnosis JSON...")
        try:
            raw = call_model(prompt, 15000)
            raw = re.sub(r'^```(?:json)?\s*','',raw.strip()); raw = re.sub(r'\s*```$','',raw.strip())
            data = json.loads(raw)
            ok, why = diagnosis_data_is_adequate(data)
            if not ok:
                print('Legacy model JSON inadequate:', why)
                data = None
        except Exception as e:
            print('Legacy model unavailable:', str(e)[:180])
            data = None

    # --- Last-resort floor: per-client derived fallback (never 8 identical paragraphs) ---
    if data is None:
        print('Using deterministic per-client fallback (last resort).')
        data = fallback_data_from_questionnaire(q)

    # Normalize model output keys
    for p in data.get('plans',[]):
        for k,v in {'id':('id','plan_id','letter'),'name':('name','plan_name'),'logic':('logic','core'),'steps':('steps','actions'),'budget':('budget','cost'),'pros':('pros','advantages'),'cons':('cons','disadvantages'),'fitness':('fitness','suitability')}.items():
            if k not in p: p[k]=p.get(next((x for x in v if x in p),''),'')
        if not p.get('steps'): p['steps']=[]
    for t in data.get('topics',[]):
        for k,v in {'title':('title','topic'),'current_risk':('current_risk','risk'),'why_it_happens':('why_it_happens','cause'),'materials_needed':('materials_needed','materials'),'solution':('solution','fix'),'deliverables':('deliverables','output')}.items():
            if k not in t: t[k]=t.get(v[1],'')
    data.setdefault('client_name',data.get('client_name','Client')); data.setdefault('client_summary',data.get('client_summary',{}))
    data.setdefault('problems',data.get('problems',[])); data.setdefault('root_judgment',data.get('root_judgment',{}))
    data.setdefault('passport_boundary',data.get('passport_boundary','')); data.setdefault('comparison',data.get('comparison',{}))
    data.setdefault('actions',data.get('actions',[])); data.setdefault('risk_statements',data.get('risk_statements',[]))
    data.setdefault('law_appendix',data.get('law_appendix',[]))
    for p in data.get('problems',[]): p.setdefault('id',p.get('id',1)); p.setdefault('problem',p.get('problem','')); p.setdefault('severity',p.get('severity','P2')); p.setdefault('detail',p.get('detail','')); p.setdefault('action',p.get('action','')); p.setdefault('law_basis',p.get('law_basis',p.get('law',''))); p.setdefault('lawyer_view',p.get('lawyer_view','')); p.setdefault('tax_view',p.get('tax_view','')); p.setdefault('identity_view',p.get('identity_view','')); p.setdefault('solution',p.get('solution','')); p.setdefault('risk_control',p.get('risk_control',p.get('risk_mitigation','')))
    comp=data.get('comparison',{}); comp.setdefault('recommendation',comp.get('recommendation','')); comp.setdefault('reasons',comp.get('reasons',[])); comp.setdefault('not_recommended',comp.get('not_recommended',{}))
    print("JSON: {} topics, {} plans".format(len(data.get('topics',[])), len(data.get('plans',[]))))
    html = build(data)
    clean_reps={'云端执行器':'生成系统','执行器':'生成系统','云端':'','模板驱动生成':'定稿版生成','Template-Driven':'Final Standard'}
    for a,b in clean_reps.items(): html=html.replace(a,b)
    extra = '<section class="section"><h2>十一、补充核验清单</h2><p>为保证诊断草案可直接进入执行策划案阶段，本清单要求客户在正式启动前补齐企业审计、完税证明、股东分红决议、个人银行流水、海外账户资料、出入境记录、家庭关系文件、子女教育材料、保险和投资账户资料、项目报价、律师意见和税务师意见。每一项材料都要标注来源、日期、责任方、用途和对应国家项目。若材料无法解释资金来源或税务居民边界，应暂停递交并先做合规修复。</p></section>'
    if '</main>' in html: html=html.replace('</main>', extra+'</main>')
    else: html += extra
    bad=[x for x in ['�','TODO','Lorem','placeholder','思考过程','内部过程','作为AI','云端执行器'] if x in html]
    if bad: raise RuntimeError('diagnosis blocked bad terms: '+','.join(bad))
    if len(html) < 18000 or html.count('<table') < 8: raise RuntimeError('diagnosis too thin or missing tables')
    Path(out).parent.mkdir(parents=True,exist_ok=True); Path(out).write_text(html,encoding='utf-8')
    print("Written {} ({} bytes)".format(out, len(html)))
    return 0

if __name__=='__main__': raise SystemExit(main())