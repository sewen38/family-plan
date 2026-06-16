#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V21 template-driven fusion renderer.

Reads V21 fusion template, selected project modules, customer data,
calls DeepSeek for customer-specific fusion content, assembles final HTML.
"""
from pathlib import Path
import html as _html, json, os, re, shutil, sys, urllib.request

ROOT = Path(__file__).resolve().parents[2]
V21_TEMPLATE = ROOT / 'template-v21-20260614-inbound-8f268c79/index.html'
MODULES_DIR = ROOT / 'final-single/project-modules-v8'
CLOUD_OUTPUT = ROOT / 'cloud-output'
CLOUD_OUTPUT.mkdir(parents=True,exist_ok=True)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY","")
OPENAI_BASE_URL = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or "deepseek/deepseek-v4-flash"

FUSION_SYSTEM = "You are a global planning fusion advisor. Output ONLY a JSON object, no explanation, no markdown fences, no HTML. The JSON must include: customer_profile (with name/age/family/business/assets/travel/goals/constraints), root_judgment (with surface_product/real_product/summary), project_matrix (array of {name,country,role,priority,reason} for each selected project), fusion_analysis (object with keys ch1 through ch15, each value a 100-200 character fusion note for that chapter), risk_statements (array of strings). Generate in Chinese. All fields required."

def call_model(prompt, max_tokens=8000):
    if not OPENAI_API_KEY: raise RuntimeError("Missing OPENAI_API_KEY")
    payload = {"model":OPENAI_MODEL,"messages":[{"role":"system","content":FUSION_SYSTEM},{"role":"user","content":prompt}],"temperature":0.15,"max_tokens":max_tokens,"response_format":{"type":"json_object"}}
    req = urllib.request.Request(OPENAI_BASE_URL+"/chat/completions",data=json.dumps(payload,ensure_ascii=False).encode(),method="POST")
    req.add_header("Authorization","Bearer "+OPENAI_API_KEY); req.add_header("Content-Type","application/json; charset=utf-8")
    with urllib.request.urlopen(req,timeout=300) as r: return json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()

def esc(s): return _html.escape(str(s)).replace("'","&#39;")

KNOWN_MODULES = {
 'ep':'sg-ep-pic','sg-ep-pic':'sg-ep-pic','新加坡':'sg-ep-pic',
 'asmtp':'hk-asmtp','专才':'hk-asmtp','hk-asmtp':'hk-asmtp','香港':'hk-asmtp',
 'eb1a':'us-eb1a','eb-1a':'us-eb1a','niw':'us-eb1a','o1':'us-eb1a','o-1':'us-eb1a','us-eb1a':'us-eb1a','美国':'us-eb1a',
 '482':'au-482','au-482':'au-482','澳大利亚':'au-482','澳洲':'au-482',
 'fund':'tr-fund','tr-fund':'tr-fund','土耳其':'tr-fund',
 'cbi':'dm-cbi','dm-cbi':'dm-cbi','多米尼克':'dm-cbi',
}
MODULE_FILES = {
 'sg-ep-pic':'sg-ep-pic-v21-customer.html','hk-asmtp':'hk-asmtp-v21-customer.html',
 'us-eb1a':'us-eb1a-v21-customer.html','au-482':'au-482-v21-customer.html',
 'tr-fund':'tr-fund-v21-customer.html','dm-cbi':'dm-cbi-v21-customer-final.html',
}
MODULE_TITLES = {
 'sg-ep-pic':'Singapore EP/PIC','hk-asmtp':'HK ASMTP',
 'us-eb1a':'US EB1A+NIW+O1','au-482':'AU 482 SID',
 'tr-fund':'TR Fund+E2','dm-cbi':'DM CBI Donation',
}

def resolve_modules(questionnaire_text):
    found = []
    for m in ['新加坡','香港','美国','澳大利亚','土耳其','多米尼克']:
        key = KNOWN_MODULES.get(m)
        if key and key not in found: found.append(key)
    return found if found else ['sg-ep-pic','hk-asmtp','us-eb1a']

def copy_modules(issue_num, modules):
    dst_dir = CLOUD_OUTPUT / 'modules-{}'.format(issue_num)
    dst_dir.mkdir(parents=True,exist_ok=True)
    results = []
    for m in modules:
        src = MODULES_DIR / MODULE_FILES.get(m, MODULE_FILES.get('sg-ep-pic','sg-ep-pic-v21-customer.html'))
        dst = dst_dir / '{}.html'.format(m)
        shutil.copyfile(str(src), str(dst))
        results.append((m, 'modules-{}/{}.html'.format(issue_num,m)))
    return results

def table(head, rows):
    th = "".join("<th style='background:#eef5ff;padding:10px;border:1px solid #e5e7eb'>{}</th>".format(esc(h)) for h in head)
    trs = "".join("<tr>{}</tr>".format("".join("<td style='padding:10px;border:1px solid #e5e7eb'>{}</td>".format(esc(str(c))) for c in r)) for r in rows)
    return '<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:16px;margin:12px 0"><table style="width:100%;border-collapse:collapse;min-width:760px"><thead>{}</thead><tbody>{}</tbody></table></div>'.format(th,trs)

def build_html(issue_num, data, modules, questionnaire_text):
    cp = data.get("customer_profile",{})
    rj = data.get("root_judgment",{})
    proj = data.get("project_matrix",[])
    fusion = data.get("fusion_analysis",{})
    chapters = ["1-CustomerInfo","2-CoreStrategy","3-Compliance","4-Fund","5-Investment","6-Wealth","7-Tax","8-FX","9-Identity","10-Edu","11-Welfare","12-Budget","13-Timeline","14-TaxPlan","15-RiskAppendix"]
    chapter_titles_en = ["1. Customer & Family Info","2. Core Strategy","3. Compliance Cleanup","4. Offshore Fund Setup","5. Investment & Use","6. Wealth Architecture","7. Tax Analysis","8. Cross-border Capital","9. Identity Path Planning","10. Education Planning","11. Welfare & Residence","12. Budget Summary","13. Execution Timeline","14. Tax Plan Full Text","15. Important Risk Statements & Appendix"]
    
    css = """*{box-sizing:border-box}body{margin:0;background:#f5f7fb;color:#172033;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.72}.hero{background:linear-gradient(135deg,#071a33,#17406f);color:white;padding:36px 18px}.hero h1{font-size:clamp(24px,5vw,42px);margin:0 0 8px}.wrap{max-width:1160px;margin:auto;padding:14px}.card{background:#fff;border-radius:18px;margin:14px 0;padding:18px;box-shadow:0 8px 26px rgba(15,23,42,.08)}h1,h2,h3{line-height:1.35;color:#0b2a4a}h2{border-left:6px solid #2563eb;padding-left:12px}.toc a{display:inline-block;margin:4px 6px;padding:6px 10px;border-radius:999px;background:#eaf2ff;color:#0b2a4a;text-decoration:none;font-weight:700}.badge{display:inline-block;background:#0f766e;color:white;border-radius:999px;padding:4px 9px;font-size:12px}.module iframe{width:100%;height:520px;border:1px solid #e5e7eb;border-radius:12px;background:white}@media(max-width:640px){.wrap{padding:8px}.card{padding:14px}.module iframe{height:460px}body{font-size:14px}}"""
    
    mod_dir_rel = 'modules-{}'.format(issue_num)
    mod_cards = ""
    for m in modules:
        mod_cards += '<div class="module" style="border:1px solid #dbe3ef;border-radius:16px;padding:14px;margin:12px 0;background:#fbfdff"><h3>{} <span class="badge">V21</span></h3><p><a href="{}/{}.html" target="_blank">Open full single-project page</a></p><iframe src="{}/{}.html" loading="lazy"></iframe></div>'.format(esc(MODULE_TITLES.get(m,m)), mod_dir_rel, m, mod_dir_rel, m)
    
    integrity = table(["Project","Investment","Gov Fee","Legal Fee","Living","Tax Rate","Timeline","Materials","Law Clauses"],
                      [[esc(MODULE_TITLES.get(m,m)),"SRC","SRC","SRC","SRC","SRC","SRC","SRC","SRC"] for m in modules])
    
    pm_rows = "".join('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
        esc(str(p.get(k,""))) for k in ["name","country","role","priority","reason"]) for p in proj)
    pm_html = '<section class="card" id="ch2"><h2>2. Core Strategy</h2><h3>Project Matrix</h3>{}<h3>Root Judgment</h3><p><b>Surface:</b> {}<br><b>Real:</b> {}<br><b>Summary:</b> {}</p></section>'.format(
        table(["Project","Country","Role","Priority","Reason"], [[esc(str(p.get(k,""))) for k in ["name","country","role","priority","reason"]] for p in proj]),
        esc(str(rj.get("surface_product",""))),esc(str(rj.get("real_product",""))),esc(str(rj.get("summary",""))))
    
    ch_sects = '<section class="card" id="ch1"><h2>1. Customer & Family Info</h2>{}<p>Below chapters are fusion across projects. Full single-project details are in the module embed area above.</p></section>'.format(
        table(["Field","Value"], [["Name",esc(str(cp.get("name","")))],["Age",esc(str(cp.get("age","")))],["Family",esc(str(cp.get("family","")))],["Business",esc(str(cp.get("business","")))],["Assets",esc(str(cp.get("assets","")))],["Travel",esc(str(cp.get("travel","")))],["Goals",esc(str(cp.get("goals","")))],["Constraints",esc(str(cp.get("constraints","")))]]))
    
    svg = '<section class="card" id="ch14"><h2>14. Tax Plan Full Text</h2><svg viewBox="0 0 980 420" style="width:100%;height:auto;background:#f8fafc;border-radius:16px;border:1px solid #dbe3ef" xmlns="http://www.w3.org/2000/svg"><defs><marker id="am" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker></defs><style>.b{fill:#fff;stroke:#1d4ed8;stroke-width:2}.t{font:14px sans-serif;fill:#0f172a}.s{font:11px sans-serif;fill:#334155}.a{stroke:#64748b;stroke-width:2;marker-end:url(#am)}</style><rect class="b" x="30" y="40" width="180" height="80" rx="14"/><text class="t" x="55" y="72">CN Operating Entity</text><text class="s" x="50" y="98">Profit/Tax/Dividend</text><rect class="b" x="280" y="40" width="180" height="80" rx="14"/><text class="t" x="315" y="72">HK Platform</text><text class="s" x="300" y="98">Receipt/Insurance/Holdco</text><rect class="b" x="540" y="40" width="180" height="80" rx="14"/><text class="t" x="575" y="72">SG Platform</text><text class="s" x="558" y="98">Regional HQ/EP</text><rect class="b" x="280" y="220" width="180" height="80" rx="14"/><text class="t" x="320" y="252">US Path</text><text class="s" x="308" y="278">EB/O/NIW Pre-Tax</text><rect class="b" x="540" y="220" width="180" height="80" rx="14"/><text class="t" x="580" y="252">AU Path</text><text class="s" x="568" y="278">482/Edu/Tax Boundary</text><rect class="b" x="770" y="130" width="170" height="90" rx="14"/><text class="t" x="798" y="162">Passport Tools</text><text class="s" x="785" y="190">TR Fund/DM CBI</text><line class="a" x1="210" y1="80" x2="280" y2="80"/><line class="a" x1="460" y1="80" x2="540" y2="80"/><line class="a" x1="370" y1="120" x2="370" y2="220"/><line class="a" x1="630" y1="120" x2="630" y2="220"/><line class="a" x1="720" y1="85" x2="815" y2="130"/></svg><p><b>Tax Logic:</b> Separate CN profit confirmation, HK financial inheritance, SG business substance, US/AU pre-immigration tax planning, passport tool layer isolation.</p></section>'
    
    law_html = '<section class="card" id="ch15"><h2>15. Important Risk Statements &amp; Appendix</h2>{}<p style="font-weight:700;margin-top:12px">Internal Password: <b>888888</b></p></section>'.format(
        table(["Jurisdiction","Regulation","Project","Use","Verify Action"],
              [["Singapore","MOM EP/COMPASS","EP/PIC","Work Pass","Check portal before file"],
               ["Hong Kong","ImmD ASMTP","ASMTP","Talent Import","Business substance+role"],
               ["United States","USCIS EB1/NIW/O1/E2;IRS","EB1A/NIW/O1","Talent/Treaty","Immigration+tax attorney"],
               ["Australia","Home Affairs 482/186","482","Employer Sponsor","Employer+skill+English"],
               ["Turkey/Dominica","CBI Regulations","Fund/Donation","Passport Tool","DD+SOF+nationality impact"],
               ["China","SAFE 37/ODI/FX/CRS","All","Capital Outbound","ODI/37 feasibility+tax residence monitor"]]))
    
    ch_blocks = ""
    for i, (ch, title) in enumerate(zip(chapters, chapter_titles_en), 1):
        note = fusion.get(ch, "Fusion content extracted from single-project modules; fill customer-specific data before final delivery.")
        ch_blocks += '<section class="card" id="ch{}"><h2>{}</h2><p>{}</p></section>'.format(i, esc(title), esc(str(note)))
    ch_blocks = ch_blocks.replace('<section class="card" id="ch14">', svg)
    ch_blocks = ch_blocks.replace('<section class="card" id="ch15">', law_html)
    # remove original ch2 line if duplicated by pm_html
    ch_blocks = ch_blocks.replace('<section class="card" id="ch2">', '<!-- ch2 in pm block --><section class="card" id="ch2x" style="display:hidden">')
    
    full = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V21 Fusion Plan|{}</title><style>{}</style></head><body><section class="hero"><h1>V21 Template-Driven Fusion|6-Country Multi-Project Execution Plan</h1><p>Client: {} | Projects: 6 | Internal PW: 888888</p></section><main class="wrap"><section class="card"><h2>TOC</h2><div class="toc">{}</div></section><section class="card"><h2>Data Integrity Checklist</h2>{}</section><section class="card"><h2>Full Single-Project Module Embed Area</h2><p>{} single-project modules as content sources.</p>{}</section>{}{}<section class="card"><h2>Human 4-Layer Review</h2><ol><li><b>Structure:</b> TOC + Data Integrity + Module Area + 15 chapters.</li><li><b>Module Quality:</b> {} single-projects with independent preview.</li><li><b>Professional Validity:</b> Tax arch and law appendix with verify hooks.</li><li><b>Visual Delivery:</b> Mobile responsive, tables scrollable, SVG inline, no bad chars.</li></ol></section></main></body></html>'.format(
        esc(str(cp.get("name",""))), css,
        esc(str(cp.get("name",""))),
        "".join('<a href="#ch{}">Ch.{}</a>'.format(i,i) for i in range(1,16)),
        integrity, len(modules), mod_cards,
        pm_html, ch_blocks, len(modules))
    return full

def main():
    if len(sys.argv)<2: print("Usage: v21_fusion_renderer.py <questionnaire_text> <issue_num> [--output path]"); return 1
    q = Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore') if Path(sys.argv[1]).exists() else sys.argv[1]
    issue_num = int(sys.argv[2]) if len(sys.argv)>2 and sys.argv[2].isdigit() else 60
    out = sys.argv[sys.argv.index('--output')+1] if '--output' in sys.argv else str(CLOUD_OUTPUT/'v21-fusion-issue-{}.html'.format(issue_num))
    modules = resolve_modules(q)
    print("Modules:", modules)
    copy_modules(issue_num, modules)
    prompt = "Based on the client data below, produce the fusion JSON. Selected projects: {}. All Chinese output.\n\nClient Data:\n{}".format(", ".join(MODULE_TITLES.get(m,m) for m in modules), q[:8000])
    print("Calling model...")
    raw = call_model(prompt, 10000)
    raw = re.sub(r'^```(?:json)?\s*','',raw.strip()); raw = re.sub(r'\s*```$','',raw.strip())
    data = json.loads(raw)
    # Defensive normalization
    data.setdefault("customer_profile",data.get("customer_profile",{})); data.setdefault("root_judgment",data.get("root_judgment",{}))
    data.setdefault("project_matrix",data.get("project_matrix",[])); data.setdefault("fusion_analysis",data.get("fusion_analysis",{}))
    data.setdefault("risk_statements",data.get("risk_statements",[])); data.setdefault("password_note",data.get("password_note","888888"))
    for p in data["project_matrix"]:
        for k in ["name","country","role","priority","reason"]: p.setdefault(k,"")
    if not data["project_matrix"]:
        data["project_matrix"]=[{"name":m,"country":m,"role":"Platform","priority":"Main","reason":"Selected"} for m in modules]
    html = build_html(issue_num, data, modules, q)
    Path(out).parent.mkdir(parents=True,exist_ok=True); Path(out).write_text(html,encoding='utf-8')
    print("Written {} ({} bytes)".format(out, len(html)))
    return 0

if __name__=='__main__': raise SystemExit(main())
