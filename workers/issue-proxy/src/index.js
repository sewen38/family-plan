const json = (data, status = 200, headers = {}) => new Response(JSON.stringify(data), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', ...headers },
});

function corsHeaders(request) {
  const origin = request.headers.get('origin') || '';
  const allowed = 'https://sewen38.github.io';
  const ok = origin === allowed || origin.startsWith('https://sewen38.github.io');
  return {
    'access-control-allow-origin': ok ? origin : allowed,
    'access-control-allow-methods': 'GET, POST, OPTIONS',
    'access-control-allow-headers': 'content-type, accept',
    'access-control-max-age': '86400',
  };
}

function cleanText(value, max = 20000) {
  return String(value || '').replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').slice(0, max);
}


async function serveQuestionnaire(request) {
  const upstream = 'https://raw.githubusercontent.com/sewen38/family-plan/main/start.html';
  const res = await fetch(upstream, { headers: { 'accept': 'text/html' } });
  let html = await res.text();
  const origin = new URL(request.url).origin;
  // Same-origin mode: avoid Feishu/in-app browser cross-origin restrictions.
  html = html.replace(/var ISSUE_PROXY_URL='[^']*';/, `var ISSUE_PROXY_URL='${origin}';`);
  html = html.replace(/document\.html\?issue=/g, 'https://sewen38.github.io/family-plan/document.html?issue=');
  html = html.replace('最新版 20260629 Worker-Fixed', '最新版 20260629 Same-Origin Worker');
  return new Response(html, {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'no-store, max-age=0',
      'x-family-plan-entry': 'worker-same-origin',
    },
  });
}

// GitHub API helper (uses stored token)
async function gh(method, path, env, body = null) {
  const headers = {
    'authorization': `Bearer ${env.GITHUB_TOKEN}`,
    'accept': 'application/vnd.github+json',
    'user-agent': 'family-plan-issue-proxy',
    'x-github-api-version': '2022-11-28',
  };
  if (body) {
    headers['content-type'] = 'application/json; charset=utf-8';
  }
  const repo = env.GITHUB_REPO || 'sewen38/family-plan';
  const res = await fetch(`https://api.github.com/repos/${repo}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

// Extract diagnosis text from comments
function extractDiagnosisFromComments(comments) {
  if (!Array.isArray(comments)) return null;
  // Look for cloud runner's diagnosis comment format
  for (let i = comments.length - 1; i >= 0; i--) {
    const body = comments[i].body || '';
    // Cloud runner format: "## Diagnosis draft generated\n\nReview: https://..."
    if (body.includes('Diagnosis draft') || body.includes('诊断草案')) {
      // Extract the URL from the comment
      const urlMatch = body.match(/Review:\s*(https?:\/\/[^\s]+)/);
      if (urlMatch) return { url: urlMatch[1], stage: 'diagnosis_done' };
      return { url: null, stage: 'diagnosis_generating' };
    }
  }
  return null;
}

// Extract execution plan URL from comments
function extractExecutionFromComments(comments) {
  if (!Array.isArray(comments)) return null;
  for (let i = comments.length - 1; i >= 0; i--) {
    const body = comments[i].body || '';
    if (body.includes('Execution plan') || body.includes('执行策划案')) {
      const urlMatch = body.match(/Review:\s*(https?:\/\/[^\s]+)/);
      if (urlMatch) return { url: urlMatch[1], stage: 'execution_done' };
      return { url: null, stage: 'execution_generating' };
    }
  }
  return null;
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    if (!env.GITHUB_TOKEN) return json({ ok: false, error: 'missing_server_token' }, 500, cors);

    const url = new URL(request.url);
    const path = url.pathname;
    const repo = env.GITHUB_REPO || 'sewen38/family-plan';

    // ── GET /start.html or /start: serve same-origin questionnaire page ──
    if (request.method === 'GET' && (path === '/start.html' || path === '/start' || path === '/questionnaire')) {
      return serveQuestionnaire(request);
    }

    // ── POST / (default): create issue from questionnaire ──
    if (request.method === 'POST' && (path === '/' || path === '' || path === '/api/create-issue')) {
      let input;
      try { input = await request.json(); } catch (_) { return json({ ok: false, error: 'invalid_json' }, 400, cors); }

      const summary = cleanText(input.summary, 18000);
      const name = cleanText(input.name, 80) || '未知';
      if (!summary || summary.length < 20) return json({ ok: false, error: 'empty_summary' }, 400, cors);

      const title = `📋 ${name} · ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`;
      const body = `## 原始问卷数据\n\n\`\`\`\n${summary}\n\`\`\`\n\n---\n📅 ${new Date().toISOString()}\n来源：family-plan-issue-proxy`;

      const { ok, status, data } = await gh('POST', '/issues', env, {
        title, body, labels: ['questionnaire', 'pending'],
      });

      if (!ok || !data.number) return json({ ok: false, error: 'github_failed', status, detail: data }, 502, cors);

      // Also try to notify the agent via webhook if configured
      if (env.AGENT_WEBHOOK_URL) {
        try {
          await fetch(env.AGENT_WEBHOOK_URL, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({
              event: 'questionnaire_submitted',
              issue: data.number,
              name,
              summary_prefix: summary.slice(0, 500),
              url: data.html_url,
              ts: Date.now(),
            }),
          }).catch(() => {});
        } catch (_) {}
      }

      return json({ ok: true, issue: data.number, url: data.html_url }, 200, cors);
    }

    // ── GET /api/pending: list pending issues (for agent polling) ──
    if (request.method === 'GET' && path === '/api/pending') {
      const { ok, data } = await gh('GET', '/issues?state=open&labels=pending&per_page=10', env);
      if (!ok) return json({ ok: false, error: 'github_failed', detail: data }, 502, cors);

      const issues = (Array.isArray(data) ? data : []).filter(i => !i.pull_request);
      const result = await Promise.all(issues.map(async (issue) => {
        // Get comments to check if already processing
        const { data: comments } = await gh('GET', `/issues/${issue.number}/comments?per_page=5`, env);
        const diagStatus = extractDiagnosisFromComments(comments);
        const execStatus = extractExecutionFromComments(comments);

        // Extract summary from issue body
        const body = issue.body || '';
        const summaryMatch = body.match(/```\n?([\s\S]*?)```/);
        const summary = summaryMatch ? summaryMatch[1].trim() : body.slice(0, 1000);

        return {
          number: issue.number,
          title: issue.title,
          state: issue.state,
          created_at: issue.created_at,
          updated_at: issue.updated_at,
          labels: issue.labels.map(l => l.name),
          summary: summary.slice(0, 2000),
          diagnosis: diagStatus,
          execution: execStatus,
        };
      }));

      return json({ ok: true, count: result.length, issues: result }, 200, cors);
    }

    // ── GET /api/pending/count: lightweight count check ──
    if (request.method === 'GET' && path === '/api/pending/count') {
      const { ok, data } = await gh('GET', '/issues?state=open&labels=pending&per_page=1', env);
      if (!ok) return json({ ok: false, error: 'github_failed' }, 502, cors);
      const count = Array.isArray(data) ? data.length : 0;
      return json({ ok: true, count }, 200, cors);
    }

    // ── GET /api/diagnosis/:issue: get diagnosis for an issue ──
    const diagnosisMatch = path.match(/^\/api\/diagnosis\/(\d+)$/);
    if (request.method === 'GET' && diagnosisMatch) {
      const issueNum = parseInt(diagnosisMatch[1], 10);
      const { ok, data: comments } = await gh('GET', `/issues/${issueNum}/comments?per_page=10&sort=created&direction=desc`, env);
      if (!ok) return json({ ok: false, error: 'github_failed', detail: comments }, 502, cors);

      const diagStatus = extractDiagnosisFromComments(comments);
      const execStatus = extractExecutionFromComments(comments);

      if (diagStatus && diagStatus.url) {
        // Fetch actual diagnosis HTML content
        try {
          const htmlRes = await fetch(diagStatus.url);
          const html = await htmlRes.text();
          return json({
            ok: true,
            issue: issueNum,
            stage: 'diagnosis_done',
            url: diagStatus.url,
            html: html.slice(0, 80000), // send full HTML as text
            execution: execStatus,
          }, 200, cors);
        } catch (_) {
          return json({
            ok: true,
            issue: issueNum,
            stage: 'diagnosis_done',
            url: diagStatus.url,
            html: null,
            execution: execStatus,
          }, 200, cors);
        }
      }

      // Check issue state when no diagnosis comment found
      const { data: issue } = await gh('GET', `/issues/${issueNum}`, env);
      const labels = (issue.labels || []).map(l => l.name);

      if (labels.includes('diagnosed') || labels.includes('executed')) {
        return json({
          ok: true, issue: issueNum, stage: 'completed',
          labels, execution: execStatus,
        }, 200, cors);
      }

      if (labels.includes('cloud-blocked')) {
        return json({
          ok: true, issue: issueNum, stage: 'blocked',
          labels, execution: execStatus,
        }, 200, cors);
      }

      return json({
        ok: true, issue: issueNum, stage: 'pending',
        labels, execution: execStatus,
      }, 200, cors);
    }

    // ── GET /api/issue/:issue: get issue metadata + status ──
    const issueMatch = path.match(/^\/api\/issue\/(\d+)$/);
    if (request.method === 'GET' && issueMatch) {
      const issueNum = parseInt(issueMatch[1], 10);
      const { ok, data } = await gh('GET', `/issues/${issueNum}`, env);
      if (!ok) return json({ ok: false, error: 'github_failed', detail: data }, 502, cors);

      return json({
        ok: true,
        number: data.number,
        title: data.title,
        state: data.state,
        labels: data.labels.map(l => l.name),
        created_at: data.created_at,
        html_url: data.html_url,
      }, 200, cors);
    }

    // ── Health check ──
    if (request.method === 'GET' && path === '/api/health') {
      return json({ ok: true, status: 'healthy', repo }, 200, cors);
    }

    // ── Fallback ──
    return json({ ok: false, error: 'not_found', path }, 404, cors);
  },
};