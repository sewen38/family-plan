# family-plan-issue-proxy

Server-side GitHub Issue creator for the quick questionnaire. Keeps GitHub token out of browser HTML.

## Deploy

```bash
cd workers/issue-proxy
npx wrangler secret put GITHUB_TOKEN
npx wrangler deploy
```

Use a fine-grained GitHub token scoped only to repo `sewen38/family-plan` with Issues read/write. Rotate/revoke any token previously embedded in HTML.

After deploy, set `ISSUE_PROXY_URL` in `start.html`/`index.html` to the deployed Worker URL.
