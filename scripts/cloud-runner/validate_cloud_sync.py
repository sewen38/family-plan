#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
issues=[]
def check(cond,msg):
    if not cond: issues.append(msg)
skill=ROOT/'skills/family-plan-v21-final/SKILL.md'
diag_tpl=ROOT/'skills/family-plan-v21-final/assets/diagnosis-final-template-v2-deep/index.html'
diag=ROOT/'scripts/cloud-runner/diagnosis_template_renderer.py'
execp=ROOT/'scripts/cloud-runner/v21_fusion_renderer.py'
check(skill.exists(),'missing main skill')
check(diag_tpl.exists(),'missing diagnosis final template in skill')
s=skill.read_text(encoding='utf-8') if skill.exists() else ''
check('single-country-project-json' not in s,'old abandoned skill assets still present')
ds=diag.read_text(encoding='utf-8') if diag.exists() else ''
es=execp.read_text(encoding='utf-8') if execp.exists() else ''
check('skills/family-plan-v21-final/assets/diagnosis-final-template-v2-deep/index.html' in ds,'diagnosis renderer not using skill template')
check('aitechflux/gpt-5.5' in ds and 'https://us.aitechflux.com/v1' in ds,'diagnosis renderer model/base not GPT5.5 defaults')
check('final-single/manual' in es and 'MODULE_SOURCES' in es,'execution renderer not using final single HTML sources')
check('aitechflux/gpt-5.5' in es and 'https://us.aitechflux.com/v1' in es,'execution renderer model/base not GPT5.5 defaults')
if issues:
    print('CLOUD_SYNC: BLOCKED')
    for i in issues: print('-',i)
    sys.exit(1)
print('CLOUD_SYNC: PASS')
