#!/usr/bin/env python3
from pathlib import Path
import re, json, sys
from html.parser import HTMLParser

ROOT=Path('/Users/hongleizhu/.openclaw/workspace/family-plan-pages')
FILES={
 'diagnosis_template': ROOT/'diagnosis-random-identity-tax-commercial-review-v2-deep.html',
 'diagnosis_output': ROOT/'cloud-output/diagnosis-draft-issue-58.html',
 'exec_template': ROOT/'template-v21-20260614/index.html',
 'exec_output_remote_placeholder': ROOT/'cloud-output/execution-plan-issue-59.html',
}

class H(HTMLParser):
    def __init__(self): super().__init__(); self.headings=[]; self.in_h=None; self.buf=[]
    def handle_starttag(self, tag, attrs):
        if tag in ('h1','h2','h3'): self.in_h=tag; self.buf=[]
    def handle_data(self, data):
        if self.in_h: self.buf.append(data)
    def handle_endtag(self, tag):
        if self.in_h==tag:
            txt=' '.join(''.join(self.buf).split())
            if txt: self.headings.append(txt)
            self.in_h=None

def read(p):
    if not p.exists(): return ''
    return p.read_text(encoding='utf-8', errors='ignore')

def headings(html):
    h=H(); h.feed(html); return h.headings

def audit(name, template_html, output_html, required_terms):
    th=headings(template_html); oh=headings(output_html)
    out={}
    out['template_size']=len(template_html); out['output_size']=len(output_html)
    out['size_ratio']=round(len(output_html)/max(1,len(template_html)),3)
    out['required_terms_missing']=[t for t in required_terms if t not in output_html]
    out['template_headings_missing']=[h for h in th[:80] if h and h not in oh]
    out['bad_terms']={t:output_html.count(t) for t in ['好的','遵照','作为AI','prompt','TODO','云端执行器','代码围栏','仅供测试','placeholder','fallback'] if output_html.count(t)}
    out['heading_count_template']=len(th); out['heading_count_output']=len(oh)
    return out

report={}
report['diagnosis']=audit('diagnosis', read(FILES['diagnosis_template']), read(FILES['diagnosis_output']), ['风险雷达','当前风险','为什么会出事','需要核验材料','解决方案','最终交付物','人工4重审核'])
# execution output may not exist locally unless pulled; compare if exists
report['execution']=audit('execution', read(FILES['exec_template']), read(FILES['exec_output_remote_placeholder']), ['快速目录','数据完整性检查表','完整单项目模块嵌入区','一、客户家庭基本信息','十四、财税执行策划案全文','十五、重要风险声明','888888'])
print(json.dumps(report,ensure_ascii=False,indent=2))
