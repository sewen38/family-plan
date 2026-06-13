#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = []

def add(name, ok):
    checks.append((name, bool(ok)))

index = (ROOT / 'index.html').read_text(encoding='utf-8')
summary = (ROOT / 'batch-summary.html').read_text(encoding='utf-8')
exec_html = (ROOT / 'exec.html').read_text(encoding='utf-8')

add('快速问卷为最终V3版本', '快速版问卷 <span style="font-size:12px;color:#888">V3</span>' in index)
add('资产结构房产联动存在', "toggleAsset(this,'house')" in index and 'asset_house' in index and '房产数量' in index and "genValuation('house','房产','套','万元')" in index)
add('提交后进入V20诊断草案复制流程', "document.getElementById('f').onsubmit" in index and "renderDiagnosis('✅ 已提交。请复制问卷文本发给智能体" in index)
add('网络失败也进入诊断页兜底', '当前网络无法自动提交，请复制问卷给智能体生成诊断草案' in index)
add('跨设备协议文本存在', '【财税方案快速问卷提交】' in index and 'buildProtocolText' in index and '复制问卷给智能体' in index)
add('诊断未生成不能进下一阶段', '诊断草案尚未生成，不能进入下一阶段' in index)
add('新批量清空旧评估数据', 'bd[String(issue)]={}' in index)
add('汇总只读取projects数组', 'selectedProject' not in summary and 'solutions' not in summary and 'Array.isArray(info.projects)' in summary)
add('汇总全空仍可下一阶段', '当前所选国家均暂无符合项目' in summary and "document.getElementById('actions').style.display = 'flex'" in summary)
add('汇总跳正式融合执行策划案', ("var target = 'fusion.html?issue='" in summary or "var target = 'exec.html?issue='" in summary) and 'exec-v12.html' not in summary)
fusion_html = (ROOT / 'fusion.html').read_text(encoding='utf-8')
document_html = (ROOT / 'document.html').read_text(encoding='utf-8')

add('诊断草案底部法案条款表', all(x in document_html for x in ['附录：本诊断草案涉及的相关法案条款','法案名称','第几条第几款','《中华人民共和国国籍法》','第3条','第9条']))
add('诊断草案乱码清理', 'cleanText' in document_html and "replace(/[\\uFFFD]+/g,'')" in document_html and '�' not in document_html)
add('执行案V20说明', 'V20 · 15章融合执行策划案' in exec_html and '14章客户交付版' not in exec_html)
add('执行案国家内减法多国加法', '国家内减法 + 多国家加法' in exec_html and '未勾选项目不进入任何章节' in exec_html)
add('执行案顶部计算器专区', all(x in exec_html for x in ['顶部计算器专区','新加坡 COMPASS','日本高才 HSP','新西兰 SMC','澳大利亚 EOI']))
add('融合页V20引擎', 'V20 引擎' in fusion_html and 'V19 引擎' not in fusion_html)
add('融合页先完整单项目模块再归并', fusion_html.find('完整单项目模块嵌入区（用于厚度校验）') >= 0 and fusion_html.find('完整单项目模块嵌入区（用于厚度校验）') < fusion_html.find('融合归并总览'))
add('融合页按单项目V20Plus叠加', all(x in fusion_html for x in ['V20Plus 单项目厚度验收清单','relatedSubpaths','国家 × 项目','费用明细','三方费用明细','费用汇总','材料清单','三方材料清单']))
add('融合页法案条款附件表', all(x in fusion_html for x in ['lawTableFromSections','法律法规与项目资源来源汇总','法案名称','第几条第几款','《中华人民共和国国籍法》','汇发〔2014〕37号']))
add('融合页多项目不覆盖', 'projects[c]=(projects[c]||[]).concat(vals)' in fusion_html)
add('融合页香港专才专项规则', all(x in fusion_html for x in ['isHkAsmtp','hkAsmtpSec','hkAsmtpRiskLaw','ASMTP雇主担保专才 + 自有公司/自雇专才']))
add('融合页美国EB1A定稿标准专项规则', all(x in fusion_html for x in ['isUsEb1a','usEb1aSec','usEb1aRiskLaw','EB-1A Extraordinary Ability + O-1A桥接','未选EB-5投资款不得进入本案预算','INA) | §203(b)(1)(A)']))
add('融合页15章与财税全文', all(x in fusion_html for x in ['单国家单项目 V20Plus 模块','十四、财税执行策划案全文','十五、重要风险声明与附件']))

pages = ['jp-assessment.html','vu-assessment.html','ge-assessment.html']
for page in pages:
    s = (ROOT / page).read_text(encoding='utf-8')
    add(f'{page}只保存勾选项目', 'input[name="selProject"]:checked' in s and 'seenProjects' in s)
    add(f'{page}空结果有下一阶段', '下一阶段（跳过该国）' in s)


# JavaScript syntax smoke test for main pages. Prevents broken inline strings from disabling submit.
import re
import subprocess
for html_file in ['index.html', 'start.html']:
    html = (ROOT / html_file).read_text(encoding='utf-8')
    scripts = '\n'.join(re.findall(r'<script>(.*?)</script>', html, flags=re.S))
    tmp = Path('/tmp/family-plan-' + html_file + '.js')
    tmp.write_text(scripts, encoding='utf-8')
    result = subprocess.run(['node', '--check', str(tmp)], capture_output=True, text=True)
    add(html_file + ' JS语法有效', result.returncode == 0)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(('✅' if ok else '❌'), name)
if failed:
    raise SystemExit('FAILED: ' + '; '.join(failed))
print('FLOW VERIFICATION PASS')
