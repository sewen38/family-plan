# Cloud Executor Sync

Status: synced and cloud-runner fixed.

- Skill: family-plan-v21-final
- Policy: current latest is no-JSON version; JSON方案已放弃
- Local skill path: `/Users/hongleizhu/.openclaw/workspace/skills/family-plan-v21-final`
- Cloud workspace path in repo: `skills/family-plan-v21-final`
- Cloud runner repo: `sewen38/family-plan`
- Cloud runner default model: `aitechflux/gpt-5.5`
- Cloud runner default base URL: `https://us.aitechflux.com/v1`
- Required GitHub secret: `OPENAI_API_KEY`
- Optional GitHub secrets: `OPENAI_BASE_URL`, `OPENAI_MODEL`

## 2026-06-17 修复确认

已修复云端执行器“文件同步了但执行逻辑未接入 skill”的问题：

1. `diagnosis_template_renderer.py` 改为读取本 skill 内诊断草案定稿模板：
   - `skills/family-plan-v21-final/assets/diagnosis-final-template-v2-deep/index.html`
2. `v21_fusion_renderer.py` 改为严格从完整 V21 单项目 HTML 内容源回源融合；不再靠 JSON 方案生成正文。
3. 新增 `scripts/cloud-runner/validate_cloud_sync.py`，GitHub Actions 运行前强制 preflight：
   - 主 skill 存在
   - 诊断模板存在
   - 无 JSON 方案残留
   - GPT-5.5/base URL 默认值正确
   - 执行 renderer 使用完整单项目 HTML 内容源
4. 执行策划案本地跑通测试：
   - 快速版问卷样本
   - 6个单项目模块：新加坡 EP/PIC、香港 ASMTP、美国 EB-1A、澳洲 482、土耳其基金、多米尼克 CBI
   - `scripts/v21_release_gate.py cloud-output/execution-plan-issue-991.html` → `RESULT: PASS`
   - 诊断草案、执行策划案、6个单项目页可见文本/图文 gate → `END_TO_END_VISIBLE_GATE=PASS`
5. 已推送 GitHub main：
   - cloud runner 修复 commit: `7075831`
   - 根路径测试页发布 commit: `548c9a4`

## 测试审核链接

GitHub raw 已确认可访问；GitHub Pages 可能有短暂刷新延迟。

- 诊断草案测试页：`https://sewen38.github.io/family-plan/diagnosis-v21-cloud-fix-test-20260617.html`
- 执行策划案测试页：`https://sewen38.github.io/family-plan/execution-v21-cloud-fix-test-20260617.html`
- 单项目模块示例：`https://sewen38.github.io/family-plan/project-modules-991/au-482.html`

If repository secrets override defaults, ensure:

```text
OPENAI_BASE_URL=https://us.aitechflux.com/v1
OPENAI_MODEL=aitechflux/gpt-5.5
```

## 2026-06-17 13:47 方案二：备用模型链

已在云端诊断 renderer 中加入备用模型链：

- Primary: `aitechflux/gpt-5.5`
- Fallback default: `deepseek/deepseek-v4-flash`
- 可用环境变量覆盖：`OPENAI_FALLBACK_MODELS=model1,model2`
- 对 `429/502/503/504` 会先重试，再切换备用模型。
- 若所有模型失败，才进入确定性定稿模板兜底，避免半成品输出。

## 2026-06-17 14:00 DeepSeek独立备用通道

已新增 DeepSeek 独立备用通道：

- Primary: `aitechflux/gpt-5.5` via `OPENAI_API_KEY` / `https://us.aitechflux.com/v1`
- Fallback: `deepseek-chat` via `DEEPSEEK_API_KEY` / `https://api.deepseek.com/v1`
- GitHub Actions 需要新增 repository secret: `DEEPSEEK_API_KEY`
- 可选覆盖：`OPENAI_FALLBACK_MODELS`、`DEEPSEEK_BASE_URL`

注意：不要把 DeepSeek key 写入仓库文件；必须通过 GitHub Actions secret 注入。
