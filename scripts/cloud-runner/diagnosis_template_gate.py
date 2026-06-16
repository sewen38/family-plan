#!/usr/bin/env python3
from pathlib import Path
from html.parser import HTMLParser
import json, sys, re
ROOT=Path(__file__).resolve().parents[2]
REG=ROOT/'template-registry/diagnosis-template-registry.json'
class H(HTMLParser):
    def __init__(self): super().__init__(); self.headings=[]; self.in_h=False; self.buf=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('h1','h2','h3'): self.in_h=True; self.buf=[]
    def handle_data(self,data):
        if self.in_h: self.buf.append(data)
    def handle_endtag(self,tag):
        if tag in ('h1','h2','h3') and self.in_h:
            t=' '.join(''.join(self.buf).split())
            if t: self.headings.append(t)
            self.in_h=False

def headings(s):
    h=H(); h.feed(s); return h.headings

def main():
    if len(sys.argv)<2:
        print('usage: diagnosis_template_gate.py <html>'); return 2
    p=Path(sys.argv[1]); s=p.read_text(encoding='utf-8',errors='ignore')
    reg=json.loads(REG.read_text(encoding='utf-8'))
    tpl=reg['templates'][0]
    hs='\n'.join(headings(s))
    errors=[]
    for h in tpl['mandatory_headings']:
        if h not in hs:
            errors.append('missing heading: '+h)
    for term in ['当前风险','为什么会出事','需要核验材料','解决方案','最终交付物']:
        if s.count(term)<5:
            errors.append(f'topic term too few: {term}={s.count(term)}')
    for bad in ['TODO','prompt','作为AI','好的，','遵照','�','锟']:
        if bad in s: errors.append('bad visible term: '+bad)
    
    tpl_html=Path(tpl['template_html']).read_text(encoding='utf-8',errors='ignore')
    min_len=int(len(tpl_html)*0.85)
    if len(s)<min_len: errors.append(f'too short: {len(s)} < {min_len} (85% template)')
    print('# DIAGNOSIS TEMPLATE GATE')
    print('file:',p)
    if errors:
        print('RESULT: BLOCKED')
        for e in errors: print('-',e)
        return 1
    print('RESULT: PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
