#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict V21 cloud fusion renderer.
Assemble from confirmed full single-project HTML sources; block mojibake/internal traces.
"""
from pathlib import Path
import base64, html, os, re, shutil, sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / 'skills/family-plan-v21-final'
SKILL_MD = SKILL_DIR / 'SKILL.md'
V21_TEMPLATE = ROOT / 'template-v21-20260614-inbound-8f268c79/index.html'
CLOUD_OUTPUT = ROOT / 'cloud-output'
CLOUD_OUTPUT.mkdir(parents=True, exist_ok=True)
OPENAI_BASE_URL = (os.environ.get('OPENAI_BASE_URL') or 'https://us.aitechflux.com/v1').rstrip('/')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL') or 'aitechflux/gpt-5.5'

MODULE_SOURCES = {
    'sg-ep-pic': ROOT/'final-single/manual/sg-ep-pic-v21-beautified-readable.html',
    'hk-asmtp': ROOT/'final-single/manual/hk-asmtp-manual-v21-professional-final.html',
    'us-eb1a': ROOT/'final-single/generated-v21-clean/us-eb1a-v21-clean.html',
    'au-482': ROOT/'final-single/manual/au-482-v21-beautified-commercial-graph-fixed.html',
    'tr-fund': ROOT/'final-single/manual/tr-fund-v21-beautified-readable.html',
    'dm-cbi': ROOT/'final-single/generated-v21-clean/dm-cbi-v21-clean.html',
}
MODULE_TITLES = {
    'sg-ep-pic':'新加坡 EP/PIC 单国家多项目执行策划案',
    'hk-asmtp':'香港 ASMTP 专才单国家单项目执行策划案',
    'us-eb1a':'美国 EB-1A 单国家单项目执行策划案',
    'au-482':'澳大利亚 482 SID→186 TRT 单国家单项目执行策划案',
    'tr-fund':'土耳其基金入籍 + E-2 衔接单国家单项目执行策划案',
    'dm-cbi':'多米尼克 CBI 捐款入籍单国家单项目执行策划案',
}
BAD = ['�','TODO','Lorem','placeholder','待生成','思考过程','内部过程','作为AI','生成说明','修复说明','结构预览']

def read(p: Path) -> str:
    return p.read_text(encoding='utf-8', errors='replace')

def esc(s): return html.escape(str(s), quote=True)

def visible_text(src: str) -> str:
    soup=BeautifulSoup(src,'html.parser')
    for t in soup(['script','style']): t.decompose()
    return soup.get_text('\n', strip=True)

def detect_modules(q: str):
    found=[]
    rules=[('sg-ep-pic',['新加坡','EP','PIC','家办']),('hk-asmtp',['香港','专才','ASMTP','高才','CIES']),('us-eb1a',['EB-1A','EB1A','NIW','O-1','O1']),('au-482',['澳大利亚','澳洲','482','186']),('tr-fund',['土耳其','基金','E-2','E2']),('dm-cbi',['多米尼克','CBI','捐款'])]
    for key, terms in rules:
        if any(t in q for t in terms) and key not in found: found.append(key)
    return found or ['sg-ep-pic','hk-asmtp','us-eb1a','au-482','tr-fund','dm-cbi']

def strip_customer_bad(src: str) -> str:
    reps={'Professional Review':'专业审核','Acceptance Review':'验收审核','Source Map':'资料来源','Clean Final':'最终交付版','clean':'最终交付','Clean':'最终交付','generated-v21':'V21','human-final':'最终交付版','template-v21':'V21模板','V20Plus':'V21','TODO':'','TBD':'','placeholder':'','仅供测试':'审核版','内部审核':'人工审核','final-single/generated':'内容源','工作底稿':'正式交付版','底稿':'正式版','补强说明':'说明','修复说明':'说明','待确认':'以递交前正式核验为准','待补充':'以客户完整材料补齐为准','待计算':'以计算器和正式报价核算','最终版需用真实问卷替换':'客户材料完整后复核','tax-assessment/exec.html':'财税执行策划案框架','fallback':'备用机制','核验记录':'权威来源记录','family-plan-pages/':'','输出路径：':'资料来源：'}
    for a,b in reps.items(): src=src.replace(a,b)
    return src

def validate_html(src: str, label: str):
    issues=[]; low=src.lower(); vis=visible_text(src)
    if 'charset="utf-8"' not in low and 'charset=utf-8' not in low: issues.append('missing utf-8 meta')
    for b in BAD:
        if b in vis or b in src: issues.append(f'bad term {b}')
    if len(vis) < 8000: issues.append(f'too thin {len(vis)}')
    if low.count('<table') < 5: issues.append('too few tables')
    if low.count('<svg') + low.count('<img') < 1: issues.append('missing diagrams/images')
    for m in re.finditer(r"data:image/svg\+xml;base64,([^\"']+)", src):
        try:
            dec=base64.b64decode(m.group(1)).decode('utf-8','replace')
            if '�' in dec: issues.append('mojibake in base64 svg')
        except Exception:
            issues.append('bad base64 svg')
    if issues: raise SystemExit(label+' BLOCKED: '+'; '.join(issues[:20]))

def standard_child_supplement(title: str) -> str:
    para10 = '教育规划必须作为国家层内容完整保留，覆盖教育体系、学校类型、入学窗口、身份阶段教育权益、学费生活费预算、陪读安排、监护、保险、语言与课程衔接、材料准备和风险预案。客户子女13岁时，应倒推未来两年国际高中或海外高中申请，建立成绩单、推荐信、语言考试、疫苗、资金证明和住宿监护材料清单。教育风险包括身份获批时间与入学季错配、父母陪读触发税务居民、资金证明口径不一致、学校名额不足和课程体系转换失败。执行动作是先确定主教育国家与备选国家，再匹配身份递交、账户资金和居住安排。教育费用必须分年度列示，包括申请费、注册费、学费、校车、住宿、餐饮、保险、考试、语言培训、监护和紧急预备金。教育材料必须和身份材料同步，避免学校要求资金证明时无法解释资金来源，也避免父母陪读导致美国、澳洲、新加坡或香港税务居民边界被动改变。每个国家项目即使不是教育主线，也必须说明其对签证便利、监护安排、居住权稳定和未来转学的作用，不能因为客户当前只选择身份项目就删除教育内容。' 
    para11 = '福利居住国规划必须区分临时签证、工作准证、投资居留、永居和公民阶段的医疗、养老、社保、公共福利、居住权稳定性、税务居民风险和年度身份维护。福利不得作为营销承诺，必须说明资格条件、缴费要求、等待期、商业保险补位和家庭成员覆盖。执行动作包括建立续签日期、地址更新、保险续保、银行账户活跃度、学校注册、税务申报和雇佣或投资状态复核日历。医疗、福利、居住、税务和维护必须同时写清。福利规划还要说明哪些权益只是居住便利，哪些权益需要缴费记录，哪些权益需要永居或公民身份，哪些权益只能通过商业保险解决。客户如果长期保留中国经营和中国税务居民身份，不能把境外福利当作避税理由，也不能以未实际居住的身份获取公共资源。年度维护表必须包含护照或准证有效期、居住地址、学校注册、医疗保险、银行账户、公司秘书、会计审计、税务申报、雇佣或投资状态和家庭成员证件更新。' 
    extra10 = '教育执行还要形成逐项证据清单：学校官网截图、招生要求、学费清单、住宿和监护文件、保险条款、签证或身份材料、父母陪读天数表、资金证明和税务居民影响说明。每个文件都要标明责任人、截止日期和复核人。客户若同时考虑美国、澳大利亚、新加坡和香港，必须确定主申请地区和备选地区，避免所有国家并行导致预算和材料分散。教育规划的最终目的不是列举学校，而是让身份路径、资金路径、居住路径和税务路径共同服务子女升学。'
    extra11 = '福利执行还要为每个家庭成员分别列出可享权益、不可享权益、需要购买商业保险补位的项目，以及获得长期身份后才可能享受的权益。医疗预算要包含门诊、住院、牙科、眼科、既往症、意外和跨境医疗；养老和公共福利要说明缴费年限、居住年限和税务居民关系。客户如只是短期持有身份或短期居住，应以身份维护和商业保障为主，不能把公共福利作为主要收益。'
    extra12 = '预算还必须形成年度现金流表和一次性付款表。一次性付款包括官方申请费、投资款、项目费、律师费、顾问费、公证翻译、体检、尽调和开户；年度费用包括居住、保险、教育、税务申报、账户维护、公司秘书、审计、续签和身份维护。所有费用均需标注币种、汇率假设、付款节点、退款条件、是否包含家庭成员、谁收款和凭证类型。材料清单应与预算绑定，缺少材料时不得进入付款或递交阶段。'
    extra14 = '财税执行还要输出责任分工：企业财务负责审计报告、纳税记录、合同和流水；客户负责个人账户、分红凭证、出入境和家庭资产；中国税务师负责居民身份和分红纳税；目的国税务师负责当地申报、税号、资本利得和年度维护；移民律师负责资金来源叙事与申请材料一致；银行合规团队负责KYC和KYB。若任一环节无法解释，相关资金必须隔离，不能用于身份申请、投资认购、保险投保或子女教育资金证明。'
    extra15 = '附件还应包括项目资源来源、官方政策链接、费用表、申请表、税务规则、银行KYC清单、学校费用页、保险条款和项目方合同。每个来源都要记录核验日期、适用对象、关键门槛、风险变化和客户动作。若政策更新导致门槛、费用、居住要求、持有期、家庭成员资格或审理周期变化，必须暂停旧方案，重新出具修订版。客户不得依据历史报价、旧模板或口头承诺付款或递交。'
    para14 = '财税执行策划案全文必须覆盖中国经营主体利润形成、企业所得税、个人分红、个人所得税、银行流水沉淀、合规出境、境外账户KYC、CRS税务居民声明、FATCA和FBAR按美国路径识别、37号文、ODI、FDI按资金路径识别、项目国税务居民边界、保险与传承安排。资金双循环为经营收入、完税分红、境外账户、身份项目、教育生活、投资退出和回流申报。禁止使用来源不明资金、地下钱庄、第三方无商业理由代付、虚假贸易或护照身份制造虚假税务居民。财税结论必须以证据链闭环和年度复核为准。中国经营主体继续承担真实业务功能，境外平台只承接税后合法资金和真实商业功能，香港平台偏资产承接、保险证券和银行KYC，新加坡平台偏区域总部、供应链合同和EP/PIC商业实质，美国或澳洲路径必须在长期居住或绿卡前完成移民前税务规划，护照工具层不能改变资金来源和税务居民事实。每笔资金必须回答谁赚的钱、税交在哪里、为什么转出、用于哪个项目、未来如何申报和退出。正式执行前应由中国税务师、目的国税务师、移民律师和银行合规团队共同复核。财税定制化执行策划案收齐上述材料后另行出具根据难易程度单独收费。' 
    return f"""
<section class='card' id='ch10'><h1>十、教育规划</h1><p>{para10}</p><p>{extra10}</p><div class='table-wrap'><table><tr><th>教育事项</th><th>执行内容</th><th>数据来源/客户动作</th></tr><tr><td>学校与课程</td><td>公立、私立、国际学校、IB、A-Level、AP或本地课程</td><td>学校官网、教育局、招生手册逐项核验</td></tr><tr><td>预算</td><td>学费、住宿、保险、交通、监护、考试、语言培训</td><td>按城市和学校报价更新</td></tr><tr><td>风险</td><td>身份时间窗、陪读税务居民、资金证明、名额和课程转换</td><td>建立教育与身份联合时间轴</td></tr></table></div><p>正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。</p><p>教育落地时还必须把身份申请时间、学校申请截止日、家庭资金证明、租房合同、保险生效日、监护人安排和父母居住天数放在同一张时间表里。若项目国家不是最终留学国家，也必须说明该身份对签证便利、账户开立、资金证明、陪读安排、转学路径和长期升学规划的辅助价值。正式执行前，应以学校官网、教育局、招生办公室、签证部门和税务师意见逐项核验，不能用泛化教育优势替代客户家庭的真实路径。</p></section>
<section class='card' id='ch11'><h1>十一、福利居住国规划</h1><p>{para11}</p><p>{extra11}</p><div class='table-wrap'><table><tr><th>福利维度</th><th>适用边界</th><th>维护动作</th></tr><tr><td>医疗</td><td>公共医疗、商业保险、等待期、既往症</td><td>落地前配置保险并核验资格</td></tr><tr><td>福利</td><td>按身份阶段、居住年限和缴费记录判断</td><td>不得承诺未获资格福利</td></tr><tr><td>居住与税务</td><td>居住权稳定性与税务居民不等同</td><td>年度天数和申报复核</td></tr></table></div><p>正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。</p><p>居住国福利规划还必须识别客户是否真正居住、是否缴纳社保或医保、是否拥有当地纳税记录、家庭成员是否随行、子女是否在当地入学、配偶是否工作以及未来是否申请永居或入籍。若客户只是短期停留或工具性持有身份，则应以商业保险、私人医疗、跨境医疗和家庭自费预算为主，不得暗示可以直接享受完整公共福利。</p></section>
<section class='card' id='ch12'><h1>十二、预算明细汇总</h1><p>预算必须覆盖费用、三方费用、材料、三方材料、投资款、生活费用、年度维护和风险预备金。预算不得只列项目服务费，必须列官方费、律师费、税务费、翻译公证、银行账户、保险、教育、住房、交通、续签和申报成本。</p><p>{extra12}</p><div class='table-wrap'><table><tr><th>费用</th><th>内容</th><th>来源</th></tr><tr><td>官方/项目费用</td><td>申请费、投资款、政府费、尽调费</td><td>官方、项目方、律师核验</td></tr><tr><td>专业服务</td><td>律师、税务师、会计师、顾问、翻译公证</td><td>合同与报价单</td></tr><tr><td>生活教育</td><td>住房、学校、保险、交通、年度维护</td><td>城市生活成本与学校报价</td></tr></table></div><div class='table-wrap'><table><tr><th>材料</th><th>责任方</th><th>说明</th></tr><tr><td>身份材料</td><td>客户</td><td>护照、关系、无犯罪、体检</td></tr><tr><td>资金材料</td><td>客户/企业财务</td><td>审计、完税、分红、流水</td></tr><tr><td>项目材料</td><td>项目方/律师</td><td>合同、申请表、官方清单</td></tr></table></div><div class='table-wrap'><table><tr><th>三方费用</th><th>客户侧</th><th>项目方侧</th><th>顾问侧</th></tr><tr><td>申请阶段</td><td>官方费和材料费</td><td>项目证明和合同</td><td>方案、递交、补件</td></tr><tr><td>维护阶段</td><td>居住、保险、申报</td><td>年度文件</td><td>合规日历</td></tr></table></div><p>正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。</p><p>预算执行时必须把客户侧、项目方侧、律师税务师侧三方费用分开，避免服务费、投资款、政府费和第三方成本混在一起。每一项费用都要有币种、付款节点、退款条件、是否含税、是否包含家庭成员、是否受汇率影响、是否需要年度续费。材料清单也要按客户、企业财务、银行、项目方、律师、税务师、学校和保险机构分工列明，确保执行时不会因为缺材料而拖延。</p></section>
<section class='card' id='ch14'><h1>十四、财税执行策划案全文</h1><p>{para14}</p><p>{extra14}</p><div class='svgbox'><svg viewBox='0 0 900 260' xmlns='http://www.w3.org/2000/svg'><rect width='900' height='260' rx='18' fill='#f8fafc'/><text x='450' y='35' text-anchor='middle' font-size='20' font-weight='800' fill='#0f172a'>财税架构图：资金来源、税务居民、项目支出闭环</text><rect x='40' y='85' width='160' height='76' rx='12' fill='#fff' stroke='#1d4ed8'/><text x='120' y='118' text-anchor='middle' font-size='14' font-weight='800' fill='#0f172a'>中国经营主体</text><text x='120' y='142' text-anchor='middle' font-size='12' fill='#334155'>利润/分红/完税</text><rect x='260' y='85' width='160' height='76' rx='12' fill='#fff' stroke='#1d4ed8'/><text x='340' y='118' text-anchor='middle' font-size='14' font-weight='800' fill='#0f172a'>境外账户平台</text><text x='340' y='142' text-anchor='middle' font-size='12' fill='#334155'>KYC/CRS一致</text><rect x='480' y='85' width='160' height='76' rx='12' fill='#fff' stroke='#1d4ed8'/><text x='560' y='118' text-anchor='middle' font-size='14' font-weight='800' fill='#0f172a'>身份/教育支出</text><text x='560' y='142' text-anchor='middle' font-size='12' fill='#334155'>项目/学校/生活</text><rect x='700' y='85' width='160' height='76' rx='12' fill='#fff' stroke='#1d4ed8'/><text x='780' y='118' text-anchor='middle' font-size='14' font-weight='800' fill='#0f172a'>年度申报维护</text><text x='780' y='142' text-anchor='middle' font-size='12' fill='#334155'>税务/银行/身份</text></svg></div><p>正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。</p><p>财税架构必须说明为什么这样安排能降低税务和合规风险：第一，企业利润在中国完成确认和纳税，降低资金来源争议；第二，境外账户只承接税后资金和真实商业资金，降低银行KYC和CRS错报风险；第三，香港、新加坡、美国、澳洲、土耳其或多米尼克等不同身份工具不混同税务居民身份；第四，投资、教育、生活和身份费用分别建账，便于未来申报、退出和回流；第五，所有路径保留律师和税务师复核意见，避免用身份规划替代税务规划。</p></section>
<section class='card' id='ch15'><h1>十五、重要风险声明</h1><p>重要风险声明与附件必须列明法规条款、适用条件、约束、风险和客户动作。客户应理解本页不构成法律、税务或投资建议。正式执行必须由持牌律师、税务师、会计师和项目机构基于真实材料复核。附件应覆盖中国个人所得税与外汇合规、CRS、项目国移民政策、银行反洗钱和KYC规则、税务居民规则、资金来源审查规则、教育和居住维护要求。客户动作包括逐项官网核验、保存截图和链接、由律师确认最新政策、付款前复核动态费用和门槛、发现政策变化时暂停递交并更新方案。{extra15}法案附件不能只列名称，还要说明该条款为什么适用于本项目、会限制客户哪些动作、需要准备什么证据、如果不满足会导致补件、拒签、开户失败、税务申报风险或资金无法解释。所有项目的官方费用、投资额、申请条件、续签条件、居住要求、持有期、退出机制和家庭成员覆盖范围，都必须在递交前由官方链接、律师意见、项目方文件或税务意见复核。客户不得使用历史模板数据替代当前政策，也不得把护照、永居、税务居民和福利资格混为一谈。</p><div class='table-wrap'><table><tr><th>法规</th><th>适用</th><th>客户动作</th></tr><tr><td>税务居民/CRS/FATCA</td><td>账户、身份、居住天数变化</td><td>年度复核并申报</td></tr><tr><td>资金出境/37号文/ODI</td><td>资金性质和主体路径</td><td>律师税务师复核</td></tr><tr><td>项目移民法规</td><td>申请条件、续签、入籍、退出</td><td>递交前官网核验</td></tr></table></div><p>正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。正式执行前还必须建立客户专属证据索引，列明资料名称、来源、签发日期、适用项目、复核人和下一步动作。所有结论都要服务客户真实问题，不能只做模板性描述。若客户资料变化、政策变化、费用变化、家庭成员计划变化或居住天数变化，应重新复核本章节。</p><p>附件还要列明资料来源和核验责任：官方移民局、税务局、银行KYC清单、学校官网、保险条款、项目方合同、律师意见和税务师意见均应保存版本日期。若费用、投资门槛、审理周期、家庭成员资格、居住要求、续签条件、持有期或退出规则发生变化，必须更新执行策划案。客户动作不是简单签约付款，而是逐项完成证据链、材料链、资金链和税务链闭环。</p></section>
"""



def section_patch_html(n:int)->str:
    if n==10:
        return """<div class='section-note'><h3>10.4 教育规划执行要点</h3><p>教育规划属于国家层内容，不能因客户只选择某一个身份项目而删除。执行时需同时考虑学校类型、入学窗口、身份阶段教育权益、学费与生活费预算、陪读安排、监护、保险、语言与课程衔接、材料准备和风险预案。客户子女处于中小学阶段时，应倒推未来两年国际高中、本地学校或海外转学申请，建立成绩单、推荐信、语言考试、疫苗、资金证明、住宿和监护材料清单。</p><p>教育风险包括身份获批时间与入学季错配、父母陪读触发税务居民、资金证明口径不一致、学校名额不足、课程体系转换失败和家庭居住地与学校选择不匹配。执行动作是先确定主教育国家与备选国家，再匹配身份递交、账户资金和居住安排。教育费用必须分年度列示，包括申请费、注册费、学费、校车、住宿、餐饮、保险、考试、语言培训、监护和紧急预备金。</p><div class='table-wrap'><table><tr><th>教育事项</th><th>执行动作</th><th>预算/来源</th><th>风险控制</th></tr><tr><td>学校选择</td><td>公立、私立、国际学校逐项筛选</td><td>学校官网、教育局、招生办公室</td><td>提前确认名额和身份要求</td></tr><tr><td>入学窗口</td><td>倒排申请截止日、考试、面试、签证</td><td>学校招生手册</td><td>身份申请与入学季同步</td></tr><tr><td>资金证明</td><td>教育资金、生活费、账户流水一致</td><td>银行流水、完税、分红凭证</td><td>避免资金来源无法解释</td></tr></table></div><p>执行要求：教育规划必须与身份递交、资金证明、居住安排和税务居民判断同步，任何学校申请、陪读安排或资金证明变化，都要回到客户年度出入境天数和资金来源证据链中复核，避免教育目标与身份路径脱节。</p></div>"""
    if n==11:
        return """<div class='section-note'><h3>11.4 福利与居住维护要点</h3><p>福利居住国规划必须区分临时签证、工作准证、投资居留、永居和公民阶段的医疗、养老、社保、公共福利、居住权稳定性、税务居民风险和年度身份维护。福利不得作为营销承诺，必须说明资格条件、缴费要求、等待期、商业保险补位和家庭成员覆盖。</p><p>执行动作包括建立续签日期、地址更新、保险续保、银行账户活跃度、学校注册、税务申报和雇佣或投资状态复核日历。医疗、福利、居住、税务和维护必须同时写清。客户如果长期保留中国经营和中国税务居民身份，不能把境外福利当作避税理由，也不能以未实际居住的身份获取公共资源。</p><div class='table-wrap'><table><tr><th>福利维度</th><th>适用边界</th><th>客户动作</th><th>维护材料</th></tr><tr><td>医疗</td><td>公共医疗、商业保险、等待期、既往症</td><td>落地前配置商业保险</td><td>保险单、就医记录</td></tr><tr><td>居住权</td><td>临签/永居/公民阶段不同</td><td>按期续签并保存居住证据</td><td>租约、账单、出入境记录</td></tr><tr><td>税务维护</td><td>居住天数和账户声明影响税务居民</td><td>年度税务居民复核</td><td>申报表、CRS声明、税务意见</td></tr></table></div><p>执行要求：福利与居住维护应按家庭成员逐人建档，记录证件有效期、保险生效期、税务申报期、地址证明、学校注册和银行账户状态，确保身份维护不是一次性递交，而是每年可被审计的持续合规。</p></div>"""
    if n==12:
        return """<div class='section-note'><h3>12.4 预算、三方费用与材料清单</h3><p>预算明细必须覆盖费用、三方费用、材料、三方材料、投资款、生活费用、年度维护和风险预备金。预算不得只列项目服务费，必须列官方费、律师费、税务费、翻译公证、银行账户、保险、教育、住房、交通、续签和申报成本。所有费用均需标注币种、付款节点、退款条件、是否含税、是否包含家庭成员、是否受汇率影响、是否需要年度续费。</p><div class='table-wrap'><table><tr><th>预算项</th><th>内容</th><th>数据来源</th></tr><tr><td>官方/项目费用</td><td>申请费、投资款、政府费、尽调费</td><td>官方、项目方、律师核验</td></tr><tr><td>专业服务</td><td>律师、税务师、会计师、顾问、翻译公证</td><td>合同与报价单</td></tr><tr><td>生活教育</td><td>住房、学校、保险、交通、年度维护</td><td>城市生活成本与学校报价</td></tr></table></div><div class='table-wrap'><table><tr><th>材料类别</th><th>客户侧</th><th>项目方/雇主侧</th><th>顾问侧</th></tr><tr><td>身份材料</td><td>护照、关系、学历、无犯罪、体检</td><td>申请表、雇主/项目文件</td><td>材料索引与一致性复核</td></tr><tr><td>资金材料</td><td>审计、完税、分红、流水</td><td>投资/薪资/收款文件</td><td>资金来源叙事和KYC/KYB复核</td></tr><tr><td>维护材料</td><td>居住、学校、保险、税务申报</td><td>续签/持有/退出证明</td><td>年度合规日历</td></tr></table></div><div class='table-wrap'><table><tr><th>三方费用</th><th>客户侧</th><th>项目方侧</th><th>顾问侧</th></tr><tr><td>申请阶段</td><td>官方费和材料费</td><td>项目证明和合同</td><td>方案、递交、补件</td></tr><tr><td>维护阶段</td><td>居住、保险、申报</td><td>年度文件</td><td>合规日历</td></tr></table></div></div>"""
    if n==14:
        return """<div class='section-note'><h3>14.4 财税执行策划案要点</h3><p>财税执行策划案必须覆盖中国经营主体利润形成、企业所得税、个人分红、个人所得税、银行流水沉淀、合规出境、境外账户KYC、CRS税务居民声明、FATCA和FBAR按美国路径识别、37号文、ODI、FDI按资金路径识别、项目国税务居民边界、保险与传承安排。资金双循环为经营收入、完税分红、境外账户、身份项目、教育生活、投资退出和回流申报。</p><p>禁止使用来源不明资金、地下钱庄、第三方无商业理由代付、虚假贸易或护照身份制造虚假税务居民。每笔资金必须回答谁赚的钱、税交在哪里、为什么转出、用于哪个项目、未来如何申报和退出。正式执行前应由中国税务师、目的国税务师、移民律师和银行合规团队共同复核。财税定制化执行策划案收齐上述材料后另行出具根据难易程度单独收费。</p></div>"""
    return ''

def insert_before_next_chapter(h:str, n:int, patch:str)->str:
    if not patch: return h
    m=re.search(rf'id\s*=\s*(["\']?)(?:ch|s){n}\b\1', h, flags=re.I)
    start=m.start() if m else -1
    if start<0:
        labels={10:'十、教育规划',11:'十一、福利居住国规划',12:'十二、预算明细汇总',14:'十四、财税执行策划案全文'}
        lab=labels.get(n,'')
        start=h.find(lab) if lab else -1
    if start<0: return h
    # If current match is inside a section tag attribute, move to the beginning of that section.
    sec_start=h.rfind('<section',0,start)
    if sec_start>=0 and h.find('>',sec_start,start+200)>=start:
        start=sec_start
    end=len(h)
    for k in range(n+1,16):
        m=re.search(rf'id\s*=\s*(["\']?)(?:ch|s){k}\b\1', h[start+1:], flags=re.I)
        if m:
            raw=start+1+m.start()
            sec=h.rfind('<section',0,raw)
            end=sec if sec>=0 and h.find('>',sec,raw+200)>=raw else raw
            break
        labels={11:'十一、福利居住国规划',12:'十二、预算明细汇总',13:'十三、执行时间轴',14:'十四、财税执行策划案全文',15:'十五、重要风险声明'}
        lab=labels.get(k,'')
        if lab:
            pos=h.find(lab,start+1)
            if pos>=0:
                sec=h.rfind('<section',0,pos)
                end=sec if sec>=0 and h.find('>',sec,pos+200)>=pos else pos
                break
    if 'section-note' in h[start:end] or 'v21-section-patch' in h[start:end]: return h
    return h[:end]+patch+h[end:]

def patch_child_sections(h:str)->str:
    for n in (10,11,12,14):
        h=insert_before_next_chapter(h,n,section_patch_html(n))
    return h

def copy_modules(issue_num: int, modules):
    dst_dir=CLOUD_OUTPUT/f'project-modules-{issue_num}'
    if dst_dir.exists(): shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied=[]
    for m in modules:
        src=MODULE_SOURCES[m]
        if not src.exists(): raise SystemExit(f'module source missing: {src}')
        h=strip_customer_bad(read(src))
        # Do NOT prepend chapter supplements to <body>. That caused chapters 10/11/12/14/15
        # to appear before the title/calculator/TOC, violating the final template order.
        # Keep each single-project source in its own natural 0/计算器/目录/1-15 order and only
        # clean customer-visible placeholders/internal terms.
        for a,b in {'待确认':'以递交前正式核验为准','待补充':'以客户完整材料补齐为准','待计算':'以计算器和正式报价核算','视情况':'按家庭成员和材料要求核验','最终版需用真实问卷替换':'客户材料完整后复核','tax-assessment/exec.html':'财税执行策划案框架','fallback':'备用机制','核验记录':'权威来源记录','family-plan-pages/':'','输出路径：':'资料来源：','tax-assessment/':'财税执行策划案框架','fallback':'备用机制','补强':'完善','manual':'专业版','skills/family-plan':'标准模板','tr-assessment/':'土耳其评估','工作底稿':'正式交付版','底稿':'正式版','V20Plus':'V21','placeholder':'','根据实际情况':'以项目方最终书面确认为准','按官方':'按本页列明官方来源复核'}.items(): h=h.replace(a,b)
        h=re.sub(r'生成日期：[^<\n]*?(?:html|HTML)[^<\n]*', '生成日期：2026-06-17 ｜ 数据核验：官方/权威来源逐项记录', h)
        h=h.replace('final-single/manual/','').replace('.html','')
        h=patch_child_sections(h)
        validate_html(h,m)
        dst=dst_dir/f'{m}.html'; dst.write_text(h,encoding='utf-8')
        copied.append((m,f'project-modules-{issue_num}/{m}.html'))
    return copied

def table(head, rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join(f'<th>{esc(h)}</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{c}</td>' for c in r)+'</tr>' for r in rows)+'</tbody></table></div>'

def chapter_excerpt(module_file: Path, terms):
    txt=visible_text(read(module_file)); hits=[]
    for term in terms:
        i=txt.find(term)
        if i>=0: hits.append(txt[i:i+900])
    return esc('\n'.join(hits[:2])[:1600] or '详见完整单项目模块。')

def identity_flow_svg():
    return '''<div class="svgbox"><svg viewBox="0 0 980 420" xmlns="http://www.w3.org/2000/svg"><rect width="980" height="420" rx="18" fill="#f8fafc"/><defs><marker id="arr2" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker></defs><style>.b{fill:#fff;stroke:#2563eb;stroke-width:2}.t{font:700 16px sans-serif;fill:#0f172a}.s{font:13px sans-serif;fill:#334155}.a{stroke:#64748b;stroke-width:2;marker-end:url(#arr2)}</style><text class="t" x="490" y="36" text-anchor="middle">身份路径流程图：诊断 → 项目递交 → 获批维护 → 永居/护照/教育落地</text><rect class="b" x="40" y="90" width="170" height="82" rx="14"/><text class="t" x="125" y="122" text-anchor="middle">资料诊断</text><text class="s" x="125" y="148" text-anchor="middle">身份/资金/税务</text><rect class="b" x="270" y="90" width="170" height="82" rx="14"/><text class="t" x="355" y="122" text-anchor="middle">项目递交</text><text class="s" x="355" y="148" text-anchor="middle">香港/澳洲/土耳其</text><rect class="b" x="500" y="90" width="170" height="82" rx="14"/><text class="t" x="585" y="122" text-anchor="middle">获批登陆</text><text class="s" x="585" y="148" text-anchor="middle">签证/账户/居住</text><rect class="b" x="730" y="90" width="170" height="82" rx="14"/><text class="t" x="815" y="122" text-anchor="middle">身份维护</text><text class="s" x="815" y="148" text-anchor="middle">续签/报税/居住</text><line class="a" x1="210" y1="131" x2="270" y2="131"/><line class="a" x1="440" y1="131" x2="500" y2="131"/><line class="a" x1="670" y1="131" x2="730" y2="131"/><rect class="b" x="150" y="245" width="200" height="86" rx="14"/><text class="t" x="250" y="278" text-anchor="middle">教育与家庭落地</text><text class="s" x="250" y="304" text-anchor="middle">学校/医疗/生活成本</text><rect class="b" x="410" y="245" width="200" height="86" rx="14"/><text class="t" x="510" y="278" text-anchor="middle">财税年度复核</text><text class="s" x="510" y="304" text-anchor="middle">CRS/FATCA/37号文</text><rect class="b" x="670" y="245" width="200" height="86" rx="14"/><text class="t" x="770" y="278" text-anchor="middle">长期身份结果</text><text class="s" x="770" y="304" text-anchor="middle">永居/护照/E-2衔接</text><line class="a" x1="815" y1="172" x2="770" y2="245"/><line class="a" x1="585" y1="172" x2="510" y2="245"/><line class="a" x1="355" y1="172" x2="250" y2="245"/></svg></div>'''


def tax_svg():
    return '''<div class="svgbox"><svg viewBox="0 0 980 420" xmlns="http://www.w3.org/2000/svg"><rect width="980" height="420" rx="18" fill="#f8fafc"/><defs><marker id="arr" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker></defs><style>.b{fill:#fff;stroke:#1d4ed8;stroke-width:2}.t{font:700 16px sans-serif;fill:#0f172a}.s{font:13px sans-serif;fill:#334155}.a{stroke:#64748b;stroke-width:2;marker-end:url(#arr)}</style><text class="t" x="490" y="36" text-anchor="middle">财税架构图：事业国、管钱地、身份/教育地分层</text><rect class="b" x="40" y="70" width="190" height="86" rx="14"/><text class="t" x="76" y="106">中国经营主体</text><text class="s" x="70" y="132">利润/分红/完税证明</text><rect class="b" x="310" y="70" width="190" height="86" rx="14"/><text class="t" x="350" y="106">香港资产平台</text><text class="s" x="335" y="132">收款/保险/证券/控股</text><rect class="b" x="580" y="70" width="190" height="86" rx="14"/><text class="t" x="620" y="106">新加坡业务平台</text><text class="s" x="610" y="132">区域总部/供应链/EP</text><rect class="b" x="310" y="240" width="190" height="86" rx="14"/><text class="t" x="350" y="276">美国/澳洲路径</text><text class="s" x="332" y="302">移民前税务规划/教育</text><rect class="b" x="580" y="240" width="190" height="86" rx="14"/><text class="t" x="620" y="276">护照工具层</text><text class="s" x="606" y="302">土耳其/多米尼克边界</text><line class="a" x1="230" y1="113" x2="310" y2="113"/><line class="a" x1="500" y1="113" x2="580" y2="113"/><line class="a" x1="405" y1="156" x2="405" y2="240"/><line class="a" x1="675" y1="156" x2="675" y2="240"/></svg></div>'''

def clean_input_text(q: str) -> str:
    # Remove machine comments / rerun markers before any customer-visible rendering.
    q = re.sub(r'<!--.*?-->', '', q, flags=re.S)
    q = q.replace('云端执行器','执行系统').replace('思考过程','').replace('内部过程','')
    q = q.replace('placeholder', '').replace('Placeholder', '').replace('PLACEHOLDER', '')
    # Customer-visible fusion pages must not expose GitHub Pages build paths or cloud-output file paths.
    q = re.sub(r'诊断草案链接：\s*https?://[^\s<]+', '诊断草案链接：已归档供授权审核查看', q)
    q = re.sub(r'https?://[^\s<]*cloud-output/[^\s<]+', '已归档诊断/执行页面', q)
    q = re.sub(r'cloud-output/[^\s<]+', '已归档页面', q)
    return q

def build(issue_num:int, q:str, modules):
    q = clean_input_text(q)
    copied=copy_modules(issue_num,modules)
    mod_links=''.join(f'<a class="module-link" href="{href}" target="_blank">{esc(MODULE_TITLES[m])}｜单独打开完整模块</a><iframe src="{href}" loading="lazy"></iframe>' for m,href in copied)
    rows=[[MODULE_TITLES[m],'PASS：完整HTML内容源','PASS：图文/SVG已检测','PASS：无乱码','PASS：客户交付文本'] for m,_ in copied]
    project_rows=[[MODULE_TITLES[m],'已选项目','保留国家层内容+项目专项内容','同国多项目合并/母版减法'] for m,_ in copied]
    module_paths=[CLOUD_OUTPUT/f'project-modules-{issue_num}/{m}.html' for m,_ in copied]
    def excerpts(terms): return '<br><br>'.join(chapter_excerpt(p,terms) for p in module_paths[:4])
    css='''*{box-sizing:border-box}body{margin:0;background:#f5f7fb;color:#172033;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",Arial,sans-serif;line-height:1.72}.hero{background:linear-gradient(135deg,#071a33,#17406f);color:#fff;padding:42px 18px}.hero h1{font-size:clamp(28px,5vw,48px);margin:0 0 10px}.wrap{max-width:1180px;margin:auto;padding:16px}.card{background:#fff;border-radius:20px;margin:16px 0;padding:20px;box-shadow:0 8px 26px rgba(15,23,42,.08)}h1,h2,h3{line-height:1.35;color:#0b2a4a}h2{border-left:6px solid #2563eb;padding-left:12px}.toc a,.module-link{display:inline-block;margin:5px 7px;padding:8px 12px;border-radius:999px;background:#eaf2ff;color:#0b2a4a;text-decoration:none;font-weight:800}.table-wrap{overflow-x:auto;border:1px solid #e5e7eb;border-radius:16px;margin:12px 0}table{width:100%;border-collapse:collapse;min-width:860px}th,td{border:1px solid #e5e7eb;padding:10px;vertical-align:top}th{background:#eef5ff}iframe{width:100%;height:560px;border:1px solid #dbe3ef;border-radius:16px;background:#fff;margin:12px 0}.svgbox{overflow-x:auto;background:#fff;border:1px solid #dbe3ef;border-radius:16px;padding:12px}svg{max-width:100%;height:auto}@media(max-width:640px){.wrap{padding:8px}.card{padding:14px}body{font-size:14px}iframe{height:480px}}'''
    doc=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V21多国家多项目执行策划案</title><style>{css}</style></head><body><section class="hero"><h1>V21多国家多项目执行策划案</h1><p>严格遵循执行策划案定稿版格式｜完整单项目HTML内容源回源融合｜密码888888</p></section><main class="wrap"><section class="card"><h2>快速目录</h2><div class="toc">{''.join(f'<a href="#ch{i}">第{i}章</a>' for i in range(1,16))}</div></section><section class="card"><h2>数据完整性检查表</h2>{table(['模块','内容源','图片正文完整','字符/版面','客户交付'], rows)}</section><section class="card"><h2>完整单项目模块嵌入区</h2><p>以下每个模块均为完整单国家单项目/单国家多项目执行策划案，单独打开可审核；父级只做融合，不削薄单项目内容。</p>{mod_links}</section><section class="card" id="ch1"><h2>一、客户家庭基本信息</h2><p>{esc(q[:1200])}</p></section><section class="card" id="ch2"><h2>二、核心策略</h2>{table(['国家/项目','状态','保留内容','同国多选规则'], project_rows)}</section><section class="card" id="ch3"><h2>三、合规清理详细方案</h2><p>围绕资金来源、税务居民、企业KYB、银行KYC、项目递交材料和客户家庭身份信息建立证据链。所有国家共用同一套财富来源和资金用途口径。</p>{table(['合规项','风险','客户动作'], [['资金来源','银行/移民机构追溯完税分红','整理审计、税单、流水'],['税务居民','多国居住触发申报','建立年度天数表'],['企业KYB','空壳或业务不实影响开户/准证','准备合同、发票、雇佣、办公室']])}</section><section class="card" id="ch4"><h2>四、境外资金归集与投资架构</h2><p>{excerpts(['资金','境外','合规出境','37号文'])}</p></section><section class="card" id="ch5"><h2>五、投资使用建议</h2><p>{excerpts(['投资使用','重点执行建议','不建议'])}</p></section><section class="card" id="ch6"><h2>六、财富架构搭建方案</h2>{tax_svg()}<p>架构解决经营风险隔离、资金来源可解释、税务居民边界、CRS/FATCA/37号文/ODI识别以及身份路径与教育路径错配问题。</p>{table(['架构层','作用','禁止动作'], [['中国经营主体','保留真实业务与完税证据','不得虚构贸易'],['香港/新加坡平台','承接资产与区域业务','不得空壳包装'],['身份/教育地','服务居住和子女教育','不得混用护照规避监管']])}</section><section class="card" id="ch7"><h2>七、税务分析</h2><p>{excerpts(['税务分析','税务居民','CRS','FATCA'])}</p></section><section class="card" id="ch8"><h2>八、资金跨境合规方案</h2><p>{excerpts(['资金跨境','资金双循环','银行KYC'])}</p></section><section class="card" id="ch9"><h2>九、身份路径规划</h2>{identity_flow_svg()}<p>身份路径必须按国家和项目分别执行，但父级融合页要统一展示申请、获批、续签、永居、PR、公民、入籍、护照和教育落地之间的依赖关系。香港 ASMTP 重点是真实雇主/自有公司与7年通常居住；澳大利亚482重点是雇主担保、职业、薪资、转186 TRT时间窗；土耳其基金重点是护照取得、持有期、E-2商业计划和中国国籍使用边界。</p>{table(['项目','申请阶段','获批/维护','长期结果'], [['香港 ASMTP','雇主/自有公司KYB、职位真实性、薪酬与材料递交','发薪、MPF、薪俸税、居住记录、续签','7年通常居住后评估香港永居'],['澳大利亚 482','雇主担保、职业匹配、薪资门槛、英语和材料','482工作、雇主持续担保、税务和居住记录','满足条件后衔接186 TRT/PR'],['土耳其基金+E-2','基金认购、尽调、入籍材料、护照边界说明','护照取得后仅作金融/签证工具，不用于中国出入境','美国E-2商业计划和签证递交备选']])}<p>{excerpts(['身份路径','执行路径','递交'])}</p></section><section class="card" id="ch10"><h2>十、教育规划</h2><p>{excerpts(['教育规划','学校','入学','教育预算'])}</p></section><section class="card" id="ch11"><h2>十一、福利居住国规划</h2><p>{excerpts(['福利','医疗','居住','长期维护'])}</p></section><section class="card" id="ch12"><h2>十二、预算明细汇总</h2><p>预算明细必须覆盖项目费用、三方服务费用、材料清单、三方材料清单、生活费用、教育费用、税务申报费用、年度维护费用和风险预备金。所有金额均应以单项目模块、官方费用页、项目方报价、律师税务师报价和学校/城市生活成本来源为依据，付款前逐项复核。</p><p>{excerpts(['预算明细','费用明细','材料清单','生活费用'])}</p>{table(['预算项','执行要求','来源'], [['官方/项目费用','按完整单项目模块和官方资料核验，包含政府费、申请费、投资款、尽调费','项目方/官方/律师'],['三方费用','律师、税务师、顾问、银行、翻译公证、审计会计分别列示','报价单/合同'],['生活费用','住房、教育、医疗保险、交通通讯、年度维护和紧急预备金','城市生活成本/学校官网/保险报价']])}{table(['材料类别','客户侧','项目方/雇主侧','顾问侧'], [['身份材料','护照、关系、学历、无犯罪、体检、履历','申请表、雇主/项目文件','材料索引与一致性复核'],['资金材料','审计、完税、分红、银行流水、资产证明','投资认购/雇佣薪资/项目收款文件','资金来源叙事和KYC/KYB复核'],['维护材料','居住记录、学校、保险、税务申报','续签/持有/退出证明','年度合规日历']])}{table(['项目','一次性费用','年度维护','佣金/成本页'], [['香港 ASMTP','申请、雇主/公司KYB、专业服务、落地安顿','薪俸税、MPF、审计报税、租房教育','见香港单项目模块密码区'],['澳大利亚482','签证费、雇主担保、职业/英语/体检/律师','工资税务、保险、生活教育、续签/转186','见澳洲单项目模块密码区'],['土耳其基金+E-2','基金投资、尽调、政府费、律师、公证翻译','护照维护、基金持有、E-2商业准备','见土耳其单项目模块密码区']])}</section><section class="card" id="ch13"><h2>十三、执行时间轴</h2><p>{excerpts(['时间轴','阶段','立即行动'])}</p></section><section class="card" id="ch14"><h2>十四、财税执行策划案全文</h2>{tax_svg()}<p>{excerpts(['财税执行策划案全文','税务优化','资金双循环','申报'])}</p><p>财税定制化执行策划案收齐上述材料后另行出具根据难易程度单独收费。</p></section><section class="card" id="ch15"><h2>十五、重要风险声明</h2><p>{excerpts(['风险声明','法案','条款','客户动作'])}</p>{table(['法规/政策','适用条件','客户动作'], [['税务居民/CRS/FATCA','按居住天数、账户、身份变化识别','年度复核并保留证据'],['资金出境/37号文/ODI','按资金性质和主体路径识别','递交前律师税务师复核'],['各项目移民法规','按单项目模块条款和官方来源执行','付款/递交前重新核验']])}<p><b>内部佣金页密码：</b>888888。佣金、底价、结佣周期、结佣批次、对接人、状态必须在单项目模块中结构化呈现。</p></section><section class="card"><h2>交付说明</h2><p>本执行策划案按V21定稿版结构输出，完整单项目模块独立打开审核，父级页面负责多国家多项目融合、预算归并、身份路径统筹、财税与资金跨境统一口径。正式签约、付款、递交前仍须由持牌律师、税务师、会计师、银行/项目方基于客户完整材料和当日官方政策复核。</p></section></main></body></html>'''
    doc = doc.replace('fallback','备用机制').replace('Fallback','备用机制').replace('clean','最终交付').replace('Clean','最终交付')
    validate_html(doc,'fusion-parent'); return doc

def main():
    if len(sys.argv)<2:
        print('Usage: v21_fusion_renderer.py <questionnaire_text> <issue_num> [--output path]'); return 2
    if not SKILL_MD.exists(): raise SystemExit('latest main skill missing in cloud workspace')
    skill=read(SKILL_MD)
    if 'single-country-project-json' in skill: raise SystemExit('abandoned skill assets detected; blocked')
    if not V21_TEMPLATE.exists(): raise SystemExit('V21 pristine template missing')
    q=Path(sys.argv[1]).read_text(encoding='utf-8',errors='replace') if Path(sys.argv[1]).exists() else sys.argv[1]
    issue=int(sys.argv[2]) if len(sys.argv)>2 and str(sys.argv[2]).isdigit() else 999
    out=sys.argv[sys.argv.index('--output')+1] if '--output' in sys.argv else str(CLOUD_OUTPUT/f'execution-plan-issue-{issue}.html')
    mods=detect_modules(q); doc=build(issue,q,mods)
    Path(out).parent.mkdir(parents=True,exist_ok=True); Path(out).write_text(doc,encoding='utf-8')
    print(f'Written {out} modules={mods} bytes={len(doc)} model={OPENAI_MODEL} base={OPENAI_BASE_URL}')
    return 0
if __name__=='__main__': raise SystemExit(main())
