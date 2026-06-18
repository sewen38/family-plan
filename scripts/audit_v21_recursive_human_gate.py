#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V21 recursive human gate.

This is a stricter parent-level gate for V21 delivery:
- Audit the fusion page itself.
- Extract all single-project module links from the fusion page.
- Audit every linked single-project page.
- Check chapter 10/11/12/14/15 and commission page in each single-project page.
- Fail the whole deliverable if any child page fails.

It intentionally catches problems that count-only scripts miss: thin education/welfare,
missing commission fields, customer-visible internal words, and non-standard page shape.
"""
from __future__ import annotations
import re, sys, json
from pathlib import Path
from html import unescape
from bs4 import BeautifulSoup

ROOT = Path('/Users/hongleizhu/.openclaw/workspace/family-plan-pages')

BAD_VISIBLE_TERMS = [
    '待确认','待补充','待计算','placeholder','工作底稿','底稿','补强','附录页','附录说明','过程稿','过程页','结构预览',
    'Clean','clean','generated','manual','Professional Review','Acceptance Review','Source Map','template-v21','final-single/generated',
    'human-final','最终版需用真实问卷替换','TODO','TBD','V20Plus','内部审核','仅供测试','fallback'
]
INTERNAL_PATH_TERMS = ['family-plan-pages/','skills/family-plan','tax-assessment/','tr-assessment/','MEMORY.md']

CHAPTER_LABELS = {
    10:['十、教育规划','第10章','教育规划'],
    11:['十一、福利居住国规划','第11章','福利居住国规划','福利与医疗'],
    12:['十二、预算明细汇总','第12章','预算明细','费用明细'],
    13:['十三、执行时间轴','第13章','执行时间轴','时间轴'],
    14:['十四、财税执行策划案全文','第14章','财税执行策划案全文'],
    15:['十五、重要风险声明','第15章','条款级法案附件','重要风险声明']
}
MIN_LEN = {10:900, 11:900, 12:900, 14:1200, 15:1000}
REQUIRED_WORDS = {
    10:['教育','学校','入学','预算','风险'],
    11:['医疗','福利','居住','税务','维护'],
    12:['费用','三方','材料','生活','预算'],
    14:['财税','税务居民','CRS','资金','申报'],
    15:['风险','条款','法规','客户动作','适用']
}
COMMISSION_WORDS = ['佣金','服务费','底价','结佣周期','结佣批次','对接人','状态']


def strip_tags(html:str)->str:
    html=re.sub(r'<script\b[^>]*>.*?</script>',' ',html,flags=re.I|re.S)
    html=re.sub(r'<style\b[^>]*>.*?</style>',' ',html,flags=re.I|re.S)
    html=re.sub(r'<[^>]+>',' ',html)
    return re.sub(r'\s+',' ',unescape(html)).strip()


def read(path:Path)->str:
    return path.read_text(encoding='utf-8',errors='ignore')


def visible_text(soup:BeautifulSoup)->str:
    for t in soup(['script','style']): t.decompose()
    return soup.get_text('\n',strip=True)


def extract_by_heading(html:str, n:int)->str:
    labels=CHAPTER_LABELS[n]
    starts=[]
    # Prefer explicit chapter anchors before headings. For headings, prefer the full
    # canonical chapter title (first label) and only then fallback to generic labels.
    m=re.search(rf'id\s*=\s*(["\']?)(?:ch|s){n}\b\1',html,flags=re.I)
    if m: starts.append(m.start())
    if not starts and labels:
        m=re.search(re.escape(labels[0]),html,flags=re.I)
        if m: starts.append(m.start())
    if not starts:
        for lab in labels[1:]:
            m=re.search(re.escape(lab),html,flags=re.I)
            if m: starts.append(m.start())
    if not starts: return ''
    start=min(starts)
    nexts=[]
    for k in range(n+1,16):
        m=re.search(rf'id\s*=\s*(["\']?)(?:ch|s){k}\b\1',html[start+1:],flags=re.I)
        if m:
            nexts.append(start+1+m.start())
            continue
        labs=CHAPTER_LABELS.get(k,[])
        # Boundary must be a canonical full chapter title, not generic words like “时间轴”.
        if labs:
            m=re.search(re.escape(labs[0]),html[start+1:],flags=re.I)
            if m: nexts.append(start+1+m.start())
    end=min(nexts) if nexts else len(html)
    return html[start:end]


def project_links(fusion_path:Path, html:str)->list[Path]:
    soup=BeautifulSoup(html,'html.parser')
    links=[]
    for tag in soup.find_all(['a','iframe']):
        href=tag.get('href') or tag.get('src') or ''
        if '.html' in href and ('project-modules' in href or 'final-single' in href):
            href=href.split('#')[0].split('?')[0]
            p=(fusion_path.parent / href).resolve()
            if p not in links: links.append(p)
    # also onclick togglePlan(...html)
    for m in re.finditer(r"(['\"])([^'\"]*\.html[^'\"]*)\1", html):
        href=m.group(2).split('#')[0].split('?')[0]
        if 'project-modules' in href or 'final-single' in href:
            p=(fusion_path.parent / href).resolve()
            if p not in links: links.append(p)
    return links


def audit_project(path:Path)->dict:
    html=read(path)
    soup=BeautifulSoup(html,'html.parser')
    vis=visible_text(BeautifulSoup(html,'html.parser'))
    issues=[]
    bad={t:vis.count(t) for t in BAD_VISIBLE_TERMS+INTERNAL_PATH_TERMS if vis.count(t)}
    if bad: issues.append('客户可见内部/未完成词: '+json.dumps(bad,ensure_ascii=False))
    chapter_info={}
    for n in [10,11,12,14,15]:
        sec=extract_by_heading(html,n)
        txt=strip_tags(sec)
        words=REQUIRED_WORDS[n]
        missing_words=[w for w in words if w not in txt]
        chapter_info[n]={'chars':len(txt),'tables':sec.lower().count('<table'),'svg':sec.lower().count('<svg'),'missing_words':missing_words[:5]}
        if not sec:
            issues.append(f'第{n}章缺失或无法按标准识别')
        elif len(txt)<MIN_LEN[n]:
            issues.append(f'第{n}章过薄: {len(txt)} < {MIN_LEN[n]}')
        elif len(missing_words)>2:
            issues.append(f'第{n}章关键词不足: 缺 {missing_words}')
        if n==12 and sec.lower().count('<table')<3:
            issues.append('第12章预算表格不足（少于3张）')
    comm_text='\n'.join([x.get_text(' ',strip=True) for x in soup.find_all(['section','div','table']) if '佣金' in x.get_text(' ',strip=True) or '结佣' in x.get_text(' ',strip=True)])
    missing_comm=[w for w in COMMISSION_WORDS if w not in comm_text]
    if missing_comm:
        issues.append('佣金页字段缺失: '+','.join(missing_comm))
    if '密码' not in comm_text and '888888' not in comm_text:
        issues.append('佣金页缺密码/隔离提示')
    return {'path':str(path),'exists':path.exists(),'bytes':path.stat().st_size if path.exists() else 0,'issues':issues,'chapters':chapter_info,'commission_chars':len(comm_text)}


def main():
    if len(sys.argv)<2:
        print('usage: audit_v21_recursive_human_gate.py <fusion.html> [--md report.md]')
        return 2
    fusion=Path(sys.argv[1]).expanduser().resolve()
    html=read(fusion)
    soup=BeautifulSoup(html,'html.parser')
    vis=visible_text(BeautifulSoup(html,'html.parser'))
    report=[]
    overall=[]
    bad={t:vis.count(t) for t in BAD_VISIBLE_TERMS+INTERNAL_PATH_TERMS if vis.count(t)}
    if bad: overall.append('融合页客户可见内部/未完成词: '+json.dumps(bad,ensure_ascii=False))
    links=project_links(fusion,html)
    if len(links)<1: overall.append('未识别到任何单项目链接')
    results=[]
    for p in links:
        if not p.exists():
            results.append({'path':str(p),'exists':False,'issues':['单项目文件不存在']})
        else:
            results.append(audit_project(p))
    blocked=bool(overall or any(r.get('issues') for r in results))
    md=[]
    md.append('# V21 递归人工审核报告')
    md.append('')
    md.append(f'- 融合页: `{fusion}`')
    md.append(f'- 单项目链接数: {len(links)}')
    md.append(f'- 总结论: **{"BLOCKED" if blocked else "PASS"}**')
    md.append('')
    if overall:
        md.append('## 融合页问题')
        for x in overall: md.append(f'- {x}')
        md.append('')
    md.append('## 单项目逐页审核')
    for r in results:
        md.append(f"### {Path(r['path']).name}")
        md.append(f"- 文件: `{r['path']}`")
        md.append(f"- 结论: **{'BLOCKED' if r.get('issues') else 'PASS'}**")
        if r.get('issues'):
            for x in r['issues']: md.append(f'  - {x}')
        if r.get('chapters'):
            md.append('')
            md.append('| 章节 | 字数 | 表格 | SVG | 缺关键词 |')
            md.append('|---|---:|---:|---:|---|')
            for n,info in r['chapters'].items():
                md.append(f"| 第{n}章 | {info['chars']} | {info['tables']} | {info['svg']} | {', '.join(info['missing_words']) or '-'} |")
        md.append('')
    out='\n'.join(md)
    if '--md' in sys.argv:
        idx=sys.argv.index('--md')
        Path(sys.argv[idx+1]).write_text(out,encoding='utf-8')
    print(out)
    return 1 if blocked else 0

if __name__=='__main__':
    raise SystemExit(main())
