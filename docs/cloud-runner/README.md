# Family Plan Cloud Runner（GitHub Actions 云端执行器）

## 目标

让问卷提交后，即使总统电脑关机，也能由 GitHub Actions 云端扫描 GitHub Issues，生成诊断草案并回写 Issue。

## 已实现

- `.github/workflows/family-plan-cloud-runner.yml`
- `scripts/cloud-runner/family_plan_cloud_runner.py`
- 支持：
  - `issues` opened/labeled/edited 触发
  - 每 10 分钟定时扫描 pending issue
  - 手动 workflow_dispatch 指定 issue
  - in-progress 并发锁
  - 云端模型 API 调用
  - 定稿版诊断草案结构
  - 重要专题五段式
  - 人工4重审核前置检查
  - 回写评论、打 diagnosed 标签、关闭 issue

## 必需 Secrets

在 GitHub 仓库 `sewen38/family-plan` 配置：

- `OPENAI_API_KEY`：必需，OpenAI 兼容 API Key
- `OPENAI_BASE_URL`：可选，默认 `https://api.openai.com/v1`
- `OPENAI_MODEL`：可选，默认 `gpt-4o-mini`

没有 `OPENAI_API_KEY` 时，workflow 会启动但不会生成内容，会在 Issue 评论中写明阻塞原因。

## 当前边界

- 诊断草案云端化：已具备代码与 workflow，配置 Secret 后可运行。
- 执行策划案全自动云端生成：需要继续补充 V21 HTML 构建器、release gate 云端脚本、GitHub Pages 发布动作；本版本先完成诊断草案云端执行器。

## 验收命令

```bash
python scripts/cloud-runner/family_plan_cloud_runner.py
```

本地运行也需要环境变量：`GITHUB_TOKEN`、`OPENAI_API_KEY`、`REPO`。
