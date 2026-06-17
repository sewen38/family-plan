# Cloud Executor Sync

Status: synced to GitHub Actions cloud-runner workspace.

- Skill: family-plan-v21-final
- Policy: current latest is no-JSON version; JSON方案已放弃
- Cloud workspace path in repo: `skills/family-plan-v21-final`
- Cloud runner default model: `aitechflux/gpt-5.5`
- Cloud runner default base URL: `https://us.aitechflux.com/v1`
- Required GitHub secret: `OPENAI_API_KEY`
- Optional GitHub secrets: `OPENAI_BASE_URL`, `OPENAI_MODEL`

If repository secrets override defaults, ensure:

```text
OPENAI_BASE_URL=https://us.aitechflux.com/v1
OPENAI_MODEL=aitechflux/gpt-5.5
```
