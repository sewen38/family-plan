# 本地执行策划案对标定稿模板差距分析（已执行修复版）

## 对标模板
- https://sewen38.github.io/family-plan/fusion-v21-fidelity-beautified-commercial-au-graph-fixed.html?v=20260614-fixed

## 指标对比
| 指标 | 定稿模板 | 当前本地保真版 | 结论 |
|---|---:|---:|---|
| HTML字节 | 221284 | 297222 | 当前更厚 |
| 正文字数 | 78338 | 81088 | 当前更厚 |
| 表格 | 178 | 203 | 当前更多 |
| SVG | 15 | 15 | 持平 |
| project-block | 50 | 50 | 持平 |

## 原 #70 未达标原因
1. 父级融合页使用摘要式生成逻辑，只有9张表、3个SVG，没有按项目逐章回源重组。
2. 定稿模板要求“完整单项目模块 + 15章逐项目拆章重组”，原 #70 主要依赖 iframe/链接，父级正文厚度不足。
3. 数据完整性检查表形态不足，未覆盖投资门槛、官方费、律师顾问费、生活费、税率、周期、材料清单、法案条款。
4. 香港/土耳其源页第14章标题结构不规范，保真抽章器无法识别财税全文，导致父级第14章过薄。
5. 旧缓存过多，容易误测历史 issue/project-modules。

## 已执行修复
1. 旧缓存已归档到 `_local-audit/old-cache-archive-20260618-1128/`；当前 `cloud-output` 只保留 #69/#70 和 project-modules-70。
2. 使用定稿模板同源的 `scripts/build-v21-template-fusion.py` 生成本地保真拆章重组版。
3. 增强香港/土耳其源模块第6/9/13/14章图形、表格、财税说明和执行表。
4. 修复香港/土耳其源模块第14章标题结构，使“十四、财税执行策划案全文”能被保真拆章器正确识别。
5. 清理客户可见内部词/路径：template-v21、generated-v21、final-single、工作底稿、V20Plus、skills路径、tr-assessment路径、待确认等。
6. 本地 `v21_release_gate.py`：PASS。
7. recursive child-page gate：PASS。
8. human-standard gate：PASS。
9. 章节顺序/顶部错位检查：PASS。
10. 重复堆砌检查：PASS。

## 当前本地文件
- 本地保真执行策划案：`_local-audit/current/execution-plan-issue-70-fidelity-local.html`
- 当前单项目模块：`_local-audit/current/cloud-output/project-modules-70/`

## 备注
本轮按用户要求“先不管云端，优先确保本地达标”，因此尚未把云端 runner 切换到保真重组生成模式。下一步如继续执行，应把 cloud runner 的执行策划案生成器从简化 `v21_fusion_renderer.py` 切到保真重组逻辑，并同步线上链接。
