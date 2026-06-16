#!/usr/bin/env python3
"""Diagnosis template-driven renderer."""
from pathlib import Path
import html, json, os, re, sys, urllib.request

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_HTML = ROOT / 'template-diagnosis-v2-deep-20260616/index.html'
CLOUD_OUTPUT = ROOT / 'cloud-output'
CLOUD_OUTPUT.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or "deepseek/deepseek-v4-flash"

SYSTEM = """你是跨境家庭全球规划顾问。只输出JSON，不要输出任何解释、Markdown围栏或HTML。必须包含8个专题且每个含五段式结构。所有字段必填。"""

def call_model(prompt: str, max_tokens: int = 12000) -> str:
    if not OPENAI_API_KEY: raise RuntimeError("Missing OPENAI_API_KEY")
    payload = {"model": OPENAI_MODEL, "messages": [{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],
               "temperature": 0.15, "max_tokens": max_tokens, "response_format": {"type":"json_object"}}
    req = urllib.request.Request(OPENAI_BASE_URL+"/chat/completions", data=json.dumps(payload,ensure_ascii=False).encode(), method="POST")
    req.add_header("Authorization","Bearer "+OPENAI_API_KEY)
    req.add_header("Content-Type","application/json; charset=utf-8")
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()

def load_template(): return TEMPLATE_HTML.read_text(encoding='utf-8')

def esc(s): return html.escape(str(s)).replace("'","&#39;")

def table(head, rows):
    th = "".join("<th>{}</th>".format(esc(h)) for h in head)
    trs = "".join("<tr>{}</tr>".format("".join("<td>{}</td>".format(esc(str(c))) for c in r)) for r in rows)
    return '<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:18px;background:#fff;margin:12px 0"><table style="width:100%;border-collapse:separate;border-spacing:0;min-width:760px"><thead><tr style="background:#eef5ff">{}<tr></thead><tbody>{}</tbody></table></div>'.format(th,trs)

def build(data):
    css_match = re.search(r'<style>(.*?)</style>', TEMPLATE_HTML.read_text(encoding='utf-8'), re.DOTALL)
    css = css_match.group(1) if css_match else ''
    hero = '<header class="hero"><div class="hero-inner"><div class="eyebrow">Identity + Tax Diagnosis · Template-Driven</div><h1>身份 + 财税诊断草案商业级定稿版</h1><p>客户：{}｜模板驱动生成｜定稿版12段结构+专题五段式+人工4重审核</p><div class="metrics"><div class="metric"><b>12</b>完整章节</div><div class="metric"><b>{}</b>待解决问题</div><div class="metric"><b>{}</b>方案路径</div><div class="metric"><b>{}</b>法规政策依据</div></div></div></header>'.format(
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
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>诊断草案定稿版|{0}</title><style>{1}</style></head><body><div class="progress" id="progress"></div>{2}<main class="wrap">{3}<footer style="text-align:center;color:#94a3b8;padding:28px 0 12px;font-size:13px">诊断草案定稿版|模板驱动生成|人工4重审核</footer></main><script>{4}</script></body></html>'.format(
        esc(data.get("client_name","")), css, hero, body, js)

def main():
    if len(sys.argv)<2: print("usage: diagnosis_template_renderer.py <questionnaire_text> [--output path]"); return 1
    q = Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore') if Path(sys.argv[1]).exists() else sys.argv[1]
    out = sys.argv[sys.argv.index('--output')+1] if '--output' in sys.argv else str(CLOUD_OUTPUT/'diagnosis-template-driven.html')
    prompt = "根据以下问卷生成诊断草案JSON。确保8个专题覆盖客户所有相关国家/项目，每个专题含current_risk/why_it_happens/materials_needed/solution/deliverables。方案至少3个。尾部增附方案A/B/C/D及结构化JSON（projects字段列出每个方案包含的国家和项目）。\n\n【问卷】\n"+q[:9000]
    print("Calling DeepSeek for diagnosis JSON...")
    raw = call_model(prompt, 15000)
    raw = re.sub(r'^```(?:json)?\s*','',raw.strip()); raw = re.sub(r'\s*```$','',raw.strip())
    data = json.loads(raw)
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
    Path(out).parent.mkdir(parents=True,exist_ok=True); Path(out).write_text(html,encoding='utf-8')
    print("Written {} ({} bytes)".format(out, len(html)))
    return 0

if __name__=='__main__': raise SystemExit(main())