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
add('提交后进入诊断草案页', "document.getElementById('f').onsubmit" in index and "renderDiagnosis('⏳ 已提交" in index)
add('网络失败也进入诊断页兜底', '当前网络无法自动提交，请复制问卷给智能体生成诊断草案' in index)
add('跨设备协议文本存在', '【财税方案快速问卷提交】' in index and 'buildProtocolText' in index and '复制问卷给智能体' in index)
add('诊断未生成不能进下一阶段', '诊断草案尚未生成，不能进入下一阶段' in index)
add('新批量清空旧评估数据', 'bd[String(issue)]={}' in index)
add('汇总只读取projects数组', 'selectedProject' not in summary and 'solutions' not in summary and 'Array.isArray(info.projects)' in summary)
add('汇总全空仍可下一阶段', '当前所选国家均暂无符合项目' in summary and "document.getElementById('actions').style.display = 'flex'" in summary)
add('汇总跳正式exec', "var target = 'exec.html?issue='" in summary and 'exec-v12.html' not in summary)
add('执行案14章框架', all(x in exec_html for x in ['01','02','03','04','05','06','07','08','09','10','11','12','13','14']))
add('执行案国家内减法多国加法', '国家内减法 + 多国家加法' in exec_html and '未勾选项目不进入任何章节' in exec_html)
add('执行案顶部计算器专区', all(x in exec_html for x in ['顶部计算器专区','新加坡 COMPASS','日本高才 HSP','新西兰 SMC','澳大利亚 EOI']))

pages = ['jp-assessment.html','vu-assessment.html','ge-assessment.html']
for page in pages:
    s = (ROOT / page).read_text(encoding='utf-8')
    add(f'{page}只保存勾选项目', 'input[name="selProject"]:checked' in s and 'seenProjects' in s)
    add(f'{page}空结果有下一阶段', '下一阶段（跳过该国）' in s)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(('✅' if ok else '❌'), name)
if failed:
    raise SystemExit('FAILED: ' + '; '.join(failed))
print('FLOW VERIFICATION PASS')
