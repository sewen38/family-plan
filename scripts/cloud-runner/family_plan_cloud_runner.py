#!/usr/bin/env python3
"""Family Plan Cloud Runner (GitHub Actions).

Token-optimized cloud runner:
- diagnosis: pending questionnaire issue -> final-standard mobile Markdown diagnosis
- execution: execution-request issue -> V21-style mobile HTML execution plan -> commit to GitHub Pages path -> comment link

Required repository secrets:
- OPENAI_API_KEY
Optional:
- OPENAI_BASE_URL (default https://api.openai.com/v1)
- OPENAI_MODEL (default deepseek/deepseek-v4-flash)
"""
from __future__ import annotations
import base64, html, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from typing import Any, List, Optional

REPO = os.environ.get("REPO", "sewen38/family-plan")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or "deepseek/deepseek-v4-flash"
MODE = (os.environ.get("INPUT_MODE") or "diagnosis").lower()
INPUT_ISSUE = os.environ.get("INPUT_ISSUE_NUMBER") or os.environ.get("EVENT_ISSUE_NUMBER") or ""

SYSTEM_BASE = """你是跨境家庭全球规划顾问。只用最终定稿版标准，禁用旧9节/旧8段/docx默认/摘要型输出。客户视角，手机端可读，无内部痕迹、TODO、乱码。输出前自检人工4重审核：整体结构、专题/模块质量、专业有效性、视觉交付。"""
DIAGNOSIS_STD = """诊断草案12段：1封面摘要+风险雷达 2七步法 3客户信息速览含诊断含义 4待解决问题P0-P3+立即动作 5根本判断 6第三国护照边界 7重要专题深度分析 8多方案 9对比推荐 10财税解决方案 11行动计划+风险声明 12法案依据。重要专题必须五段式：当前风险→为什么会出事→需要核验材料→解决方案→最终交付物。末尾给A/B/C/D方案和结构化JSON。"""
EXEC_STD = """执行策划案按V21最终定稿：手机端HTML、完整单项目模块区、15章拆章重组、单国家单项目质量永远第一、图片/架构图必须按客户情况解决问题。必须含：客户信息、根本判断、项目矩阵、合规、资金、身份、教育、福利、预算材料、时间轴、财税全文、法案附件、人工4重审核。"""

COUNTRY_FILES = {
    "美国|加拿大|EB-5|EB1|EB-1|NIW|O-1|E-2": ["references/美加移民政策对比研究-2026.md"],
    "新加坡|日本|泰国|马来西亚|GIP|EP|家办": ["references/immigration-policies-2025-2026.md"],
    "英国|澳大利亚|澳洲|新西兰|482|186|SMC": ["references/immigration-research-uk-au-nz-2025.md"],
    "葡萄牙|西班牙|希腊|马耳他|爱尔兰|欧洲": ["references/europe-immigration-policies-2026.md"],
    "土耳其|瓦努阿图|多米尼克|格鲁吉亚": ["references/immigration-research-tr-vu-dm-ge-2026.md"],
    "迪拜|阿联酋|中国|香港|CIES|高才|专才": ["references/immigration-research-uae-china-2025.md"],
}
COMMON_FILES = ["references/final-output-standards/v21-final-exec-standard.md"]


def gh(method: str, path: str, data: Optional[dict] = None) -> Any:
    if not GH_TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN")
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{path}", data=body, method=method)
    req.add_header("Authorization", f"Bearer {GH_TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub API {method} {path} failed: {e.code} {detail[:1000]}")


def labels(issue: dict) -> List[str]:
    return [x.get("name", "") for x in issue.get("labels", [])]


def list_targets() -> List[dict]:
    if INPUT_ISSUE:
        return [gh("GET", f"/issues/{INPUT_ISSUE}")]
    label = "execution-request" if MODE == "execution" else "pending"
    issues = gh("GET", f"/issues?state=open&labels={label}&per_page=10")
    return [i for i in issues if "pull_request" not in i]


def add_labels(num: int, names: List[str]) -> None:
    gh("POST", f"/issues/{num}/labels", {"labels": names})


def set_labels(num: int, names: List[str]) -> None:
    gh("PATCH", f"/issues/{num}", {"labels": sorted(set(names))})


def comment(num: int, body: str) -> None:
    gh("POST", f"/issues/{num}/comments", {"body": body[:65000]})


def close_issue(num: int) -> None:
    gh("PATCH", f"/issues/{num}", {"state": "closed"})


def extract_body(body: str) -> str:
    blocks = re.findall(r"```(?:json|text|markdown|md)?\s*([\s\S]*?)```", body or "")
    return (max(blocks, key=len) if blocks else (body or "")).strip()


def compact_text(s: str, max_chars: int) -> str:
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s[:max_chars]


def relevant_files(q: str, execution: bool = False) -> List[str]:
    files: List[str] = []
    for pat, fps in COUNTRY_FILES.items():
        if re.search(pat, q, re.I):
            files.extend(fps)
    if not files:
        files = ["references/美加移民政策对比研究-2026.md", "references/immigration-policies-2025-2026.md"]
    if execution:
        files.extend(COMMON_FILES)
    return list(dict.fromkeys(files))[:4]


def extract_relevant_snippets(text: str, q: str, max_chars: int = 9000) -> str:
    keywords = [k for k in re.split(r"[^\w\u4e00-\u9fff+-]+", q) if len(k) >= 2]
    priority = ["投资", "永居", "入籍", "税务", "资金", "教育", "福利", "CIES", "GIP", "EB-5", "EP", "482", "186", "37号文", "CRS", "FATCA"]
    keys = list(dict.fromkeys(priority + keywords[:30]))
    paras = re.split(r"\n(?=#|##|###|\|)|\n\n+", text)
    picked = []
    for para in paras:
        if any(k and k in para for k in keys):
            picked.append(para.strip())
        if sum(len(x) for x in picked) > max_chars:
            break
    if not picked:
        picked = paras[:8]
    return compact_text("\n\n".join(picked), max_chars)


def load_knowledge(q: str, execution: bool = False) -> str:
    chunks = []
    for fp in relevant_files(q, execution):
        if os.path.exists(fp):
            data = open(fp, encoding="utf-8", errors="ignore").read()
            chunks.append(f"## {fp}\n" + extract_relevant_snippets(data, q, 4500 if execution else 3500))
    return compact_text("\n\n".join(chunks), 14000 if execution else 9000)


def call_model(system: str, prompt: str, max_tokens: int) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY repository secret.")
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(f"{OPENAI_BASE_URL}/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Model API failed: {e.code} {detail[:1200]}")


def validate_diagnosis(text: str) -> List[str]:
    req = ["风险雷达", "根本判断", "第三国护照", "重要专题", "当前风险", "为什么会出事", "需要核验材料", "解决方案", "最终交付物", "方案", "行动计划", "风险声明", "法案", "人工4重审核"]
    return validate_common(text, req, 5500)


def validate_execution_html(text: str) -> List[str]:
    req = ["<!doctype html", "viewport", "完整单项目模块", "财税", "法案", "人工4重审核", "风险声明"]
    errors = validate_common(text.lower() if "<!doctype html" in text.lower() else text, req, 9000)
    if not any(x in text for x in ["十五", "第15章", "15章", "第十五章"]):
        errors.append("missing: 十五/第15章")
    return errors


def validate_common(text: str, required: List[str], min_len: int) -> List[str]:
    errors = []
    check_text = text if any(ord(c) > 127 for c in "".join(required)) else text.lower()
    for r in required:
        if r not in text and r.lower() not in text.lower():
            errors.append(f"missing: {r}")
    for f in ["TODO", "待生成", "Lorem", "�", "作为AI", "prompt"]:
        if f in text:
            errors.append(f"forbidden: {f}")
    if len(text) < min_len:
        errors.append(f"too short: {len(text)} < {min_len}")
    return errors


def html_wrap_if_needed(content: str, title: str) -> str:
    if "<html" in content.lower() and "<!doctype" in content.lower():
        return content
    escaped = html.escape(content).replace("\n", "<br>\n")
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#f5f7fb;color:#172033;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.72}}.hero{{background:linear-gradient(135deg,#071a33,#17406f);color:#fff;padding:28px 16px}}.wrap{{max-width:980px;margin:auto;padding:14px}}.card{{background:#fff;border-radius:16px;padding:16px;margin:12px 0;box-shadow:0 8px 24px rgba(15,23,42,.08)}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #e5e7eb;padding:8px;vertical-align:top}}.table-wrap{{overflow-x:auto}}@media(max-width:640px){{body{{font-size:14px}}.wrap{{padding:8px}}.card{{padding:13px}}table{{min-width:760px}}}}</style></head><body><section class="hero"><h1>{html.escape(title)}</h1><p>V21 云端执行策划案 · 手机端审核版</p></section><main class="wrap"><section class="card">{escaped}</section></main></body></html>'''


def markdown_to_mobile_html(md: str, title: str) -> str:
    safe = html.escape(md)
    body = safe
    body = re.sub(r"^### (.+)$", r"<h3>\1</h3>", body, flags=re.M)
    body = re.sub(r"^## (.+)$", r"<h2>\1</h2>", body, flags=re.M)
    body = re.sub(r"^# (.+)$", r"<h1>\1</h1>", body, flags=re.M)
    body = body.replace("\n", "<br>\n")
    body = re.sub(r"&lt;strong&gt;|&lt;/strong&gt;", "", body)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#f5f7fb;color:#172033;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.72}}.hero{{background:linear-gradient(135deg,#071a33,#17406f);color:#fff;padding:30px 16px}}.hero h1{{font-size:24px;margin:0 0 8px}}.wrap{{max-width:980px;margin:auto;padding:14px}}.card{{background:#fff;border-radius:16px;padding:16px;margin:12px 0;box-shadow:0 8px 24px rgba(15,23,42,.08);overflow-wrap:anywhere}}h1,h2,h3{{color:#0b2a4a;line-height:1.35}}h2{{border-left:5px solid #2563eb;padding-left:10px;margin-top:26px}}p,li{{font-size:15px}}@media(max-width:640px){{.wrap{{padding:8px}}.card{{padding:13px}}p,li{{font-size:14px}}.hero h1{{font-size:21px}}}}</style></head><body><section class="hero"><h1>{html.escape(title)}</h1><p>云端诊断草案 · 手机端审核版</p></section><main class="wrap"><article class="card">{body}</article></main></body></html>'''


def put_file(path: str, content: str, message: str) -> str:
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    data = {"message": message, "content": encoded, "branch": "main"}
    try:
        old = gh("GET", f"/contents/{path}")
        if old and old.get("sha"):
            data["sha"] = old["sha"]
    except Exception:
        pass
    gh("PUT", f"/contents/{path}", data)
    return f"https://sewen38.github.io/family-plan/{path}"


def make_diagnosis(issue: dict, q: str, knowledge: str) -> str:
    prompt = f"""按最终标准生成《跨境家庭全球规划诊断草案》。手机端Markdown。末尾必须有方案A/B/C/D和JSON。

【问卷】\n{compact_text(q, 7000)}

【相关知识】\n{knowledge}"""
    return call_model(SYSTEM_BASE + "\n" + DIAGNOSIS_STD, prompt, 9000)


def repair_output(kind: str, draft: str, errors: List[str], q: str, knowledge: str) -> str:
    standard = DIAGNOSIS_STD if kind == "diagnosis" else EXEC_STD
    extra = "" if kind == "diagnosis" else "执行策划案HTML必须显式出现章节标题：第1章至第15章，最后一章标题必须含‘第15章’或‘十五、重要风险声明与附件’。"
    prompt = f"""以下草稿未通过云端人工4重审核前置 gate。请直接输出修复后的完整最终稿，不要解释。

【错误项】
{chr(10).join('- '+e for e in errors)}

【必须遵守】
{standard}
{extra}

【客户资料】
{compact_text(q, 6000)}

【相关知识】
{compact_text(knowledge, 6000)}

【待修复草稿】
{compact_text(draft, 12000)}
"""
    return call_model(SYSTEM_BASE + "\n" + standard, prompt, 9000 if kind == "diagnosis" else 12000)


def make_execution(issue: dict, q: str, knowledge: str) -> str:
    prompt = f"""生成手机端可打开的V21执行策划案HTML。必须输出完整HTML源码，不要Markdown围栏。
若客户选择多国多项目，先放“完整单项目模块嵌入区”，每个单项目必须有独立质量摘要和章节入口；再做15章拆章重组。
必须包含根据客户情况绘制的SVG架构图（内嵌SVG，不用外链图片），并解释如何解决税务/资金/身份问题。

【客户/诊断/方案选择资料】\n{compact_text(q, 10000)}

【相关知识】\n{knowledge}"""
    raw = call_model(SYSTEM_BASE + "\n" + EXEC_STD, prompt, 12000)
    return html_wrap_if_needed(raw, f"执行策划案云端审核版 Issue {issue['number']}")


def process(issue: dict) -> None:
    num = issue["number"]
    labs = labels(issue)
    effective_mode = "execution" if (MODE == "execution" or "execution-request" in labs) else "diagnosis"
    if "in-progress" in labs:
        print(f"Issue #{num} already in-progress, skip")
        return
    terminal = "executed" if effective_mode == "execution" else "diagnosed"
    if terminal in labs:
        print(f"Issue #{num} already {terminal}, skip")
        return
    add_labels(num, ["in-progress"])
    original_labs = [x for x in labs if x != "in-progress"]
    q = extract_body(issue.get("body", ""))
    try:
        if effective_mode == "execution":
            knowledge = load_knowledge(q, execution=True)
            result = make_execution(issue, q, knowledge)
            errors = validate_execution_html(result)
            if errors:
                result = repair_output("execution", result, errors, q, knowledge)
                result = html_wrap_if_needed(result, f"执行策划案云端审核版 Issue {num}")
                errors = validate_execution_html(result)
            if errors:
                comment(num, "## 云端执行策划案已阻塞：未通过V21人工4重审核前置检查\n\n" + "\n".join(f"- {e}" for e in errors))
                set_labels(num, original_labs + ["execution-request", "cloud-blocked"])
                return
            path = f"cloud-output/execution-plan-issue-{num}.html"
            url = put_file(path, result, f"Add cloud execution plan for issue {num}")
            comment(num, f"## 云端执行策划案已生成\n\n审核链接：\n{url}\n\n人工4重审核：已通过基础云端 gate（结构、模块质量、专业有效性、手机端交付）。\n\n云端执行器：GitHub Actions family-plan-cloud-runner")
            set_labels(num, original_labs + ["executed"])
            close_issue(num)
        else:
            knowledge = load_knowledge(q, execution=False)
            result = make_diagnosis(issue, q, knowledge)
            errors = validate_diagnosis(result)
            if errors:
                result = repair_output("diagnosis", result, errors, q, knowledge)
                errors = validate_diagnosis(result)
            if errors:
                comment(num, "## 云端诊断已阻塞：未通过人工4重审核前置检查\n\n" + "\n".join(f"- {e}" for e in errors))
                set_labels(num, original_labs + ["pending", "cloud-blocked"])
                return
            diag_html = markdown_to_mobile_html(result, f"诊断草案云端审核版 Issue {num}")
            diag_path = f"cloud-output/diagnosis-draft-issue-{num}.html"
            diag_url = put_file(diag_path, diag_html, f"Add cloud diagnosis draft for issue {num}")
            comment(num, result + f"\n\n---\n云端诊断草案HTML审核链接：\n{diag_url}\n\n云端执行器：GitHub Actions family-plan-cloud-runner")
            set_labels(num, original_labs + ["questionnaire", "diagnosed"])
            close_issue(num)
    except Exception as e:
        comment(num, f"## 云端执行器未完成\n\n原因：`{str(e)}`")
        set_labels(num, original_labs + (["execution-request"] if effective_mode == "execution" else ["pending"]) + ["cloud-blocked"])
        raise


def main() -> int:
    targets = list_targets()
    if not targets:
        print(f"No targets for mode={MODE}")
        return 0
    for issue in targets:
        process(issue)
        time.sleep(1)
    return 0

if __name__ == "__main__":
    sys.exit(main())
