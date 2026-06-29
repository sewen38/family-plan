const json = (data, status = 200, cors = {}) => new Response(JSON.stringify(data), {
  status,
  headers: {
    'content-type': 'application/json; charset=utf-8',
    ...cors,
  },
});

function corsHeaders(request, env) {
  const origin = request.headers.get('origin') || '';
  const allowed = env.ALLOWED_ORIGIN || 'https://sewen38.github.io';
  const ok = origin === allowed || origin === 'https://sewen38.github.io';
  return {
    'access-control-allow-origin': ok ? origin : allowed,
    'access-control-allow-methods': 'POST, OPTIONS',
    'access-control-allow-headers': 'content-type',
    'access-control-max-age': '86400',
  };
}

function cleanText(value, max = 20000) {
  return String(value || '').replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').slice(0, max);
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request, env);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    if (request.method !== 'POST') return json({ ok: false, error: 'method_not_allowed' }, 405, cors);
    if (!env.GITHUB_TOKEN) return json({ ok: false, error: 'missing_server_token' }, 500, cors);

    let input;
    try { input = await request.json(); } catch (_) { return json({ ok: false, error: 'invalid_json' }, 400, cors); }

    const summary = cleanText(input.summary, 18000);
    const name = cleanText(input.name, 80) || '未知';
    if (!summary || summary.length < 20) return json({ ok: false, error: 'empty_summary' }, 400, cors);

    const title = `📋 ${name} · ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`;
    const body = `## 原始问卷数据\n\n\`\`\`\n${summary}\n\`\`\`\n\n---\n📅 ${new Date().toISOString()}\n来源：family-plan-issue-proxy`;

    const repo = env.GITHUB_REPO || 'sewen38/family-plan';
    const gh = await fetch(`https://api.github.com/repos/${repo}/issues`, {
      method: 'POST',
      headers: {
        'authorization': `Bearer ${env.GITHUB_TOKEN}`,
        'accept': 'application/vnd.github+json',
        'content-type': 'application/json; charset=utf-8',
        'user-agent': 'family-plan-issue-proxy',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify({ title, body, labels: ['questionnaire', 'pending'] }),
    });

    const data = await gh.json().catch(() => ({}));
    if (!gh.ok || !data.number) return json({ ok: false, error: 'github_failed', detail: data }, 502, cors);
    return json({ ok: true, issue: data.number, url: data.html_url }, 200, cors);
  },
};
