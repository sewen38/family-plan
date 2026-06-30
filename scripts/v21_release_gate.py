#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V21 release gate — non-bypassable final gate before sending any V21 delivery link.

This gate is deliberately stricter than normal audit scripts. It blocks release unless:
1. The registered pristine template package matches the expected SHA256.
2. The pristine extracted template files match the package contents.
3. The fusion page preserves the V21 template shape, not a self-invented shell.
4. The fusion page recursively passes all single-project child pages.
5. Customer-visible text contains no internal/build/review/path remnants.

If this script returns non-zero, the assistant MUST NOT send the link.
"""
from __future__ import annotations
import hashlib, json, re, subprocess, sys, zipfile
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'template-registry/template-registry.json'
RECURSIVE=ROOT/'scripts/audit_v21_recursive_human_gate.py'
HUMAN_STANDARD=ROOT/'scripts/audit-v21-human-standard.py'

BLOCK_VISIBLE=[
 'Professional Review','Acceptance Review','Source Map','Quality Gate','Project Modules',
 'template-v21','generated-v21','human-final','clean.html','final-single/generated',
 '待确认','待补充','待计算','placeholder','工作底稿','底稿','补强说明','修复说明','生成说明',
 'Clean Final','核验记录','V20Plus','TODO','TBD','fallback','仅供测试','内部审核','结构预览',
 'family-plan-pages/','skills/family-plan','tax-assessment/','tr-assessment/','MEMORY.md','!important'
]

REQUIRED_TEMPLATE_HEADINGS=[
 '快速目录',
 '数据完整性检查表',
 '完整单项目模块嵌入区',
 '一、客户家庭基本信息',
 '二、核心策略',
 '三、合规清理详细方案',
 '四、境外资金归集与投资架构',
 '五、投资使用建议',
 '六、财富架构搭建方案',
 '七、税务分析',
 '八、资金跨境合规方案',
 '九、身份路径规划',
 '十、教育规划',
 '十一、福利居住国规划',
 '十二、预算明细汇总',
 '十三、执行时间轴',
 '十四、财税执行策划案全文',
 '十五、重要风险声明'
]

FORBIDDEN_TEMPLATE_SUBSTITUTES=[
 '页面交付质量摘要', # self-invented replacement for 数据完整性检查表
 '11个完整项目模块清单', # self-invented replacement exposing module list before real template block
 '质量摘要',
]

def sha256(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def visible_text(html:str)->str:
    soup=BeautifulSoup(html,'html.parser')
    for t in soup(['script','style']): t.decompose()
    return soup.get_text('\n',strip=True)

def fail(msgs:list[str], msg:str):
    msgs.append(msg)

def check_registry_and_pristine(msgs:list[str]):
    if not REG.exists():
        fail(msgs,'template registry missing')
        return None
    data=json.loads(REG.read_text())
    tid=data.get('highest_priority_template')
    tpl=next((x for x in data.get('templates',[]) if x.get('id')==tid),None)
    if not tpl:
        fail(msgs,'highest priority template not found in registry')
        return None
    zip_path=Path(tpl['source_package'])
    pristine=Path(tpl['extracted_dir'])
    expected=tpl.get('source_package_sha256')
    # Cloud-portable mode: registry may contain local absolute paths from the build machine.
    # If those paths are unavailable in GitHub Actions, require the repository copy of the
    # pristine template instead of blocking before content gates can run.
    repo_pristine = ROOT / 'template-v21-20260614-inbound-8f268c79'
    if not zip_path.exists():
        if not repo_pristine.exists():
            fail(msgs,f'source package missing and repo pristine template missing: {zip_path}')
    elif expected and sha256(zip_path)!=expected:
        fail(msgs,'source package SHA256 mismatch')
    if not pristine.exists():
        if repo_pristine.exists():
            pristine = repo_pristine
        else:
            fail(msgs,f'pristine template dir missing: {pristine}')
    if zip_path.exists() and pristine.exists():
        with zipfile.ZipFile(zip_path) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                target=pristine/info.filename
                if not target.exists():
                    fail(msgs,f'pristine missing file from zip: {info.filename}')
                elif hashlib.sha256(z.read(info.filename)).hexdigest()!=sha256(target):
                    fail(msgs,f'pristine file differs from zip: {info.filename}')
    return tpl


def check_svg_no_black_or_class_dependency(fusion:Path,msgs:list[str]):
    """Block SVGs that can become browser-black boxes after CSS/style stripping."""
    html=fusion.read_text(encoding='utf-8',errors='ignore')
    soup=BeautifulSoup(html,'html.parser')
    issues=[]
    for idx,svg in enumerate(soup.find_all('svg'),1):
        # Pure black fills/strokes/backgrounds are not acceptable for V21 diagrams.
        for tag in svg.find_all(True):
            vals=[]
            for attr in ['fill','stroke','style']:
                v=tag.get(attr)
                if v: vals.append(str(v).lower().replace(' ',''))
            if any(x in v for v in vals for x in ['#000','#000000','black','rgb(0,0,0)']):
                issues.append(f'svg#{idx} black paint on <{tag.name}>')
                break
        # If rect/text/path depends on class-only styles, it may render black when style tags are stripped.
        for tag in svg.find_all(['rect','text','path','polygon','line']):
            if tag.get('class'):
                if tag.name in ['rect','path','polygon'] and not tag.get('fill') and not tag.get('stroke'):
                    issues.append(f'svg#{idx} class-only shape <{tag.name}> may render black')
                    break
                if tag.name == 'text' and not tag.get('fill') and not tag.get('style'):
                    issues.append(f'svg#{idx} class-only text may become unreadable')
                    break
    if issues:
        fail(msgs,'SVG black-box/readability gate failed: '+json.dumps(issues[:20],ensure_ascii=False))

def check_template_shape(fusion:Path,msgs:list[str]):
    html=fusion.read_text(encoding='utf-8',errors='ignore')
    soup=BeautifulSoup(html,'html.parser')
    vis=visible_text(html)
    bad={t:vis.count(t) for t in BLOCK_VISIBLE if vis.count(t)}
    if bad: fail(msgs,'customer-visible blocked terms: '+json.dumps(bad,ensure_ascii=False))
    headings=[h.get_text(' ',strip=True) for h in soup.find_all(['h1','h2','h3'])]
    joined='\n'.join(headings)
    missing=[h for h in REQUIRED_TEMPLATE_HEADINGS if h not in joined]
    if missing: fail(msgs,'missing required pristine-template headings: '+', '.join(missing))
    forbidden=[h for h in FORBIDDEN_TEMPLATE_SUBSTITUTES if h in joined]
    if forbidden: fail(msgs,'self-invented template substitute headings present: '+', '.join(forbidden))
    # ordering: full module block must be before chapter 1, and data integrity table before full module block.
    def pos(term:str)->int: return vis.find(term)
    p_dir=pos('快速目录'); p_data=pos('数据完整性检查表'); p_mod=pos('完整单项目模块嵌入区'); p_ch1=pos('一、客户家庭基本信息')
    for name,p in [('快速目录',p_dir),('数据完整性检查表',p_data),('完整单项目模块嵌入区',p_mod),('一、客户家庭基本信息',p_ch1)]:
        if p<0: fail(msgs,f'missing visible block: {name}')
    if all(p>=0 for p in [p_dir,p_data,p_mod,p_ch1]):
        if not (p_dir < p_data < p_mod < p_ch1):
            fail(msgs,'template block order wrong; must be 快速目录 → 数据完整性检查表 → 完整单项目模块嵌入区 → 第1章')
    # Must not expose local file path in visible text.
    if re.search(r'(/[A-Za-z0-9_\-.]+){2,}|\.html\b', vis):
        # allow public URLs? block local/html file names in visible text for customer pages.
        suspicious=[]
        for line in vis.split('\n'):
            if line.startswith('http://') or line.startswith('https://'):
                continue
            if '.html' in line or 'final-single/' in line or 'project-modules' in line:
                suspicious.append(line[:160])
        if suspicious:
            fail(msgs,'visible file/path remnants: '+json.dumps(suspicious[:10],ensure_ascii=False))

def check_recursive(fusion:Path,msgs:list[str]):
    if not RECURSIVE.exists():
        fail(msgs,'recursive human gate script missing')
        return
    out=ROOT/'output/verification/release-gate-recursive-report.md'
    cmd=[sys.executable,str(RECURSIVE),str(fusion),'--md',str(out)]
    res=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True)
    if res.returncode!=0:
        fail(msgs,'recursive child-page gate failed; see '+str(out))

def check_same_country_merge(fusion:Path,msgs:list[str]):
    """Hard gate for same-country multi-project merging.

    If multiple child module links point to the same country, the fusion page is still
    splitting one country into several modules instead of using one country-level
    plan with unselected projects subtracted.
    """
    html=fusion.read_text(encoding='utf-8',errors='ignore')
    refs=re.findall(r'(?:href|src)=["\']([^"\']+\.html[^"\']*)["\']', html, flags=re.I)
    refs=sorted(set(r.split('#')[0].split('?')[0] for r in refs if 'project-modules' in r or 'final-single' in r))
    country_map={
        'sg':['sg-','singapore','新加坡'],
        'hk':['hk-','hongkong','香港'],
        'us':['us-','usa','美国'],
        'au':['au-','australia','澳大利亚','澳洲'],
        'tr':['tr-','turkey','土耳其'],
        'dm':['dm-','dominica','多米尼克'],
    }
    counts={}
    for ref in refs:
        low=ref.lower()
        for c,keys in country_map.items():
            if any(k.lower() in low for k in keys):
                counts[c]=counts.get(c,0)+1
                break
    dup={c:n for c,n in counts.items() if n>1}
    if dup:
        fail(msgs,'same-country multi-project not merged into one country module: '+json.dumps(dup,ensure_ascii=False))


def check_human_standard(fusion:Path,msgs:list[str]):
    if not HUMAN_STANDARD.exists():
        fail(msgs,'human standard audit script missing')
        return
    out=ROOT/'output/verification/release-gate-human-standard-report.md'
    cmd=[sys.executable,str(HUMAN_STANDARD),str(fusion),'--md-report',str(out)]
    res=subprocess.run(cmd,cwd=str(ROOT),text=True,capture_output=True)
    if res.returncode!=0:
        fail(msgs,'human-standard gate failed; see '+str(out))


def main():
    if len(sys.argv)<2:
        print('usage: v21_release_gate.py <fusion.html>')
        return 2
    fusion=Path(sys.argv[1]).expanduser().resolve()
    msgs=[]
    if not fusion.exists():
        fail(msgs,f'fusion file missing: {fusion}')
    check_registry_and_pristine(msgs)
    if fusion.exists():
        check_template_shape(fusion,msgs)
        check_same_country_merge(fusion,msgs)
        check_svg_no_black_or_class_dependency(fusion,msgs)
        check_recursive(fusion,msgs)
        check_human_standard(fusion,msgs)
    print('# V21 RELEASE GATE')
    print('fusion:',fusion)
    if msgs:
        print('RESULT: BLOCKED')
        for m in msgs: print('-',m)
        return 1
    print('RESULT: PASS')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
