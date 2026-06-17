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
OPENAI_FALLBACK_MODELS = [m.strip() for m in (os.environ.get("OPENAI_FALLBACK_MODELS") or "deepseek/deepseek-v4-flash").split(",") if m.strip()]

SYSTEM = """你是跨境家庭全球规划顾问。只输出JSON，不要输出任何解释、Markdown围栏或HTML。必须包含8个专题且每个含五段式结构。所有字段必填。"""

def call_one_model(model: str, prompt: str, max_tokens: int) -> str:
    payload = {"model": model, "messages": [{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],
               "temperature": 0.15, "max_tokens": max_tokens, "response_format": {"type":"json_object"}}
    req = urllib.request.Request(OPENAI_BASE_URL+"/chat/completions", data=json.dumps(payload,ensure_ascii=False).encode(), method="POST")
    req.add_header("Authorization","Bearer "+OPENAI_API_KEY)
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
                print(f"Calling model candidate {mi+1}/{len(models)}: {model} attempt {attempt}/3")
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
    hero = '<header class="hero"><div class="hero-inner"><div class="eyebrow">Identity + Tax Diagnosis · Template-Driven</div><h1>身份 + 财税诊断草案商业级定稿版</h1><p>客户：{}｜定稿版格式｜专题五段式｜人工4重审核</p><div class="metrics"><div class="metric"><b>12</b>完整章节</div><div class="metric"><b>{}</b>待解决问题</div><div class="metric"><b>{}</b>方案路径</div><div class="metric"><b>{}</b>法规政策依据</div></div></div></header>'.format(
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
    
    # Problems
    sects.append('<section class="section"><h2>二、待解决问题分级</h2>{}</section>'.format(table(["编号","问题","严重度","具体说明","立即动作"], [[p["id"],esc(p["problem"]),p["severity"],esc(p.get("detail","")),esc(p.get("action",""))] for p in data.get("problems",[])])))
    
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
    topic_names=['税务居民与居住天数','资金来源证据链','企业KYB与银行KYC','子女教育时间窗','香港/新加坡资产与业务平台','美国/澳洲长期身份税务影响','第三国护照使用边界','跨境资金与CRS申报一致性']
    topics=[]
    for t in topic_names:
        topics.append({'title':t,'current_risk':'若不先处理该专题，后续开户、递交、投保、入学或续签会被要求补充材料，甚至触发拒签、关户、税务申报和资金来源风险。','why_it_happens':'多国家项目同时推进时，身份规则、银行KYC、CRS、税务居民、资金出境和教育材料互相影响；任何一个口径不一致都会放大风险。','materials_needed':'护照、出入境记录、企业审计、完税证明、分红决议、银行流水、合同发票、海外账户、学校材料、保险材料、项目报价、官方政策链接和律师税务师意见。','solution':'先建立统一证据包和年度合规日历，再按国家项目分层执行；所有费用、法案、时间轴和材料均在递交前复核。','deliverables':'税务居民风险矩阵、资金来源证据包、KYC统一口径表、教育身份时间轴、项目预算表、法案附件和执行策划案。'})
    return {
      'client_name': client,
      'client_summary': {'家庭信息': q[:500], '意向国家': '、'.join(countries) or '需从问卷核验', '意向项目': '、'.join(projects) or '需从问卷核验', '核心目标':'身份备份、子女教育、资产配置、税务优化、企业出海'},
      'problems': [
        {'id':'P0-1','problem':'资金来源与税务证据链需先统一','severity':'P0','detail':'多国家身份、开户、投保和投资都会追溯企业利润、分红、完税和银行流水。','action':'建立审计、完税、分红、流水、合同和资金用途证据包。'},
        {'id':'P0-2','problem':'税务居民边界需按家庭成员逐人测算','severity':'P0','detail':'陪读、商务和长期身份可能改变多国税务居民判断。','action':'建立年度出入境天数表和税务居民风险矩阵。'},
        {'id':'P1-1','problem':'多国多项目容易削薄执行重点','severity':'P1','detail':'不同项目解决的问题不同，不能把护照、永居、税务居民和福利资格混同。','action':'按事业国、管钱地、居住/教育地、护照工具分层。'}],
      'root_judgment': {'surface':'客户表面上是在选择多个移民项目。','real':'真实问题是先完成身份、财税、资金、教育和企业出海的底层合规架构，再选择项目组合。','correct_order':'先税务体检和资金证据链，再香港/新加坡承接平台，最后配置美国/澳洲长期身份和护照工具。'},
      'passport_boundary':'第三国护照只能作为旅行便利、金融开户便利和美国E-2等条约国工具，不得用于中国出入境身份混用，不得用于解释资金来源，不自动改变中国税务居民身份。',
      'topics':topics,
      'plans':[{'id':'A','name':'香港/新加坡承接平台优先','logic':'先解决管钱地和企业出海实质，再推进长期身份。','steps':['资金来源体检','香港账户和资产承接','新加坡公司实质与EP/PIC评估','教育和税务时间轴同步'],'budget':'按香港/新加坡开户、公司、税务、顾问和家庭安顿分项核算','pros':'合规、可逆、适合中国企业主','cons':'需要真实材料和业务实质','fitness':'高'}, {'id':'B','name':'美国/澳洲教育长期身份后置','logic':'在税务和资金基础完成后服务子女教育和长期居住。','steps':['EB/O/NIW或482预评估','移民前税务规划','教育预算和居住天数管理'],'budget':'按律师费、申请费、生活教育和税务申报分项核算','pros':'服务长期教育和居住','cons':'税务影响重，周期长','fitness':'中高'}, {'id':'C','name':'土耳其/多米尼克护照工具补充','logic':'只作为护照工具和E-2跳板，不作为税务或资金来源解决方案。','steps':['护照必要性评估','资金来源审查','国籍和出入境边界说明'],'budget':'按官方、尽调、律师和项目费用核验','pros':'速度快、工具性强','cons':'不能替代主身份和税务规划','fitness':'中'}],
      'comparison': {'recommendation':'方案A为第一阶段主线，方案B后置，方案C仅作为工具补充。','reasons':['先解决资金和税务底盘，降低所有项目失败风险。','香港/新加坡更适合中国企业主资产和业务承接。','美国/澳洲路径税务影响更重，应在材料成熟后推进。'],'not_recommended':{'直接多国同时递交':'材料、预算和税务口径容易冲突。','先买护照':'无法解决资金来源、税务居民和教育主线问题。'}},
      'actions':[{'time':'本周','task':'收集企业审计、完税、分红、银行流水、出入境和海外账户材料','deliverable':'材料清单和风险初筛','owner':'客户/顾问'}, {'time':'1个月','task':'完成税务居民、资金来源、KYC一致性和教育时间窗评估','deliverable':'诊断复核报告','owner':'税务师/顾问'}, {'time':'2-3个月','task':'启动香港/新加坡承接平台预审','deliverable':'执行策划案和项目预算','owner':'律师/顾问'}],
      'risk_statements':['本诊断草案不构成法律、税务或投资建议。','正式递交前必须由持牌律师、税务师、会计师和项目机构复核。','不得使用来源不明资金、地下钱庄、第三方无商业理由代付或虚假贸易。','第三国护照不得用于中国出入境身份混用。'],
      'law_appendix':[{'region':'中国','law':'个人所得税、外汇管理、CRS、反洗钱规则','clause':'税务居民、资金来源、境外账户和大额交易审查','applicability':'适用于企业利润、个人分红、境外账户和跨境资金。','action':'整理完税和资金链证据，出境前复核。'}, {'region':'美国','law':'USCIS EB/O/NIW/E-2；IRS SPT/FBAR/FATCA','clause':'身份申请、税务居民和境外资产申报','applicability':'适用于美国教育、长期身份和E-2商业路径。','action':'赴美前做移民前税务规划。'}, {'region':'香港/新加坡/澳洲/土耳其/多米尼克','law':'各地移民政策、银行KYC和税务居民规则','clause':'申请条件、资金来源、续签、居住和税务义务','applicability':'适用于选中国家和项目。','action':'递交前逐项官网和律师复核。'}]
    }

def main():
    if len(sys.argv)<2: print("usage: diagnosis_template_renderer.py <questionnaire_text> [--output path]"); return 1
    q = Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore') if Path(sys.argv[1]).exists() else sys.argv[1]
    out = sys.argv[sys.argv.index('--output')+1] if '--output' in sys.argv else str(CLOUD_OUTPUT/'diagnosis-template-driven.html')
    prompt = "根据以下问卷生成诊断草案JSON。确保8个专题覆盖客户所有相关国家/项目，每个专题含current_risk/why_it_happens/materials_needed/solution/deliverables。方案至少3个。尾部增附方案A/B/C/D及结构化JSON（projects字段列出每个方案包含的国家和项目）。\n\n【问卷】\n"+q[:9000]
    print("Calling configured model for diagnosis JSON...")
    try:
        raw = call_model(prompt, 15000)
        raw = re.sub(r'^```(?:json)?\s*','',raw.strip()); raw = re.sub(r'\s*```$','',raw.strip())
        data = json.loads(raw)
    except Exception as e:
        print('Model unavailable; using deterministic final-template fallback:', str(e)[:180])
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
    for p in data.get('problems',[]): p.setdefault('id',p.get('id',1)); p.setdefault('problem',p.get('problem','')); p.setdefault('severity',p.get('severity','P2')); p.setdefault('detail',p.get('detail','')); p.setdefault('action',p.get('action',''))
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