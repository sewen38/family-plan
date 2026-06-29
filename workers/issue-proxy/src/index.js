const json = (data, status = 200, headers = {}) => new Response(JSON.stringify(data), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', ...headers },
});


function mobileQuestionnaireHtml(request) {
  const origin = new URL(request.url).origin;
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>快速版问卷 · 手机专用</title>
<style>
*{box-sizing:border-box}body{margin:0;padding:14px;background:#f6f7fb;color:#172033;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',Arial,sans-serif}.wrap{max-width:720px;margin:0 auto}.hero{background:linear-gradient(135deg,#0f4c81,#1565c0);color:#fff;border-radius:18px;padding:20px;margin-bottom:12px;box-shadow:0 8px 20px rgba(21,101,192,.18)}h1{font-size:22px;margin:0 0 6px}.sub{font-size:13px;opacity:.9;line-height:1.6}.card{background:#fff;border-radius:16px;padding:15px;margin:12px 0;box-shadow:0 2px 10px rgba(15,23,42,.06)}label{display:block;font-size:14px;font-weight:800;margin:13px 0 6px;color:#253044}.req{color:#e53935}input,textarea,select{width:100%;border:1px solid #d9e2ef;border-radius:12px;padding:12px;font-size:16px;background:#fbfdff}textarea{min-height:78px;resize:vertical}.btn{width:100%;border:0;border-radius:14px;padding:15px 14px;background:#1565c0;color:#fff;font-size:17px;font-weight:900;margin:14px 0 6px}.btn.secondary{background:#eef5ff;color:#1565c0}.hint{font-size:12px;color:#667085;line-height:1.6}.ok{background:#ecfdf5;border:1px solid #bbf7d0;color:#065f46;border-radius:14px;padding:12px;margin:12px 0}.warn{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;border-radius:14px;padding:12px;margin:12px 0}.mono{white-space:pre-wrap;background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:12px;max-height:260px;overflow:auto;font-size:13px}.hide{display:none}a{color:#1565c0;font-weight:800}</style></head><body><div class="wrap"><div class="hero"><h1>⚡ 家庭全球规划 · 快速版问卷</h1><div class="sub">手机专用直连版 · 不需要 GitHub 登录 · 提交后自动生成诊断草案</div></div>
<div id="status" class="card hide"></div>
<form id="f" class="card" method="POST" action="${origin}/">
<input type="hidden" name="redirect" value="${origin}/mobile.html"><input type="hidden" name="summary" id="summary">
<label>姓名/代号 <span class="req">*</span></label><input name="name" required placeholder="例如：王总家庭">
<label>家庭成员</label><textarea name="family" placeholder="如：夫43岁-企业主 / 妻40岁 / 女儿12岁"></textarea>
<label>现有国籍/护照/永居</label><textarea name="nationality" placeholder="如：均中国籍，无第二护照/绿卡"></textarea>
<label>当前居住国家/城市</label><input name="residence" placeholder="如：中国深圳">
<label>税务居民国</label><input name="tax_resident" placeholder="如：中国 / 美国 / 不确定">
<label>企业所在地 & 行业</label><textarea name="business" placeholder="如：深圳 / 跨境电商、供应链出口"></textarea>
<label>企业年营收</label><select name="revenue"><option value="">请选择</option><option>500万以下</option><option>500万-2000万</option><option>2000万-5000万</option><option>5000万-1亿</option><option>1亿-5亿</option><option>5亿以上</option></select>
<label>家庭资产规模</label><select name="assets"><option value="">请选择</option><option>500万以下</option><option>500万-1500万</option><option>1500万-3000万</option><option>3000万-5000万</option><option>5000万-1亿</option><option>1亿以上</option></select>
<label>主要资产构成</label><textarea name="asset_structure" placeholder="房产、企业股权、存款、股票基金、保险、境外资产等"></textarea>
<label>意向移民国家/地区 <span class="req">*</span></label><textarea name="target_countries" required placeholder="如：新加坡、香港、土耳其、澳大利亚、美国"></textarea>
<label>核心诉求</label><textarea name="goals" placeholder="身份规划、税务优化、子女教育、资产安全、企业出海等"></textarea>
<label>预算</label><select name="budget"><option value="">请选择</option><option>50万以下</option><option>50万-200万</option><option>200万-500万</option><option>500万-1500万</option><option>1500万+</option><option>无明确上限</option></select>
<label>紧迫度</label><select name="urgency"><option value="">请选择</option><option>1个月内</option><option>3个月内</option><option>6个月内</option><option>1年内</option><option>不着急</option></select>
<label>是否必须保留中国国籍？</label><select name="keep_cn"><option value="">请选择</option><option>必须保留</option><option>可放弃</option><option>待定</option></select>
<label>资金跨境/海外资产/其他限制</label><textarea name="constraints" placeholder="已有海外账户、资金出境、已有计划、其他限制等"></textarea>
<button class="btn" type="submit">📤 提交问卷并生成诊断草案</button><div class="hint">提交成功后会显示 Issue 编号，并自动等待诊断草案生成。</div></form>
<div class="card"><button class="btn secondary" onclick="copySummary()">📋 复制已填问卷文本备用</button><div id="copyBox" class="mono hide"></div></div></div>
<script>
const labels={name:'姓名/代号',family:'家庭成员',nationality:'现有国籍/护照/永居',residence:'当前居住国家/城市',tax_resident:'税务居民国',business:'企业所在地&行业',revenue:'企业年营收',assets:'家庭资产规模',asset_structure:'主要资产构成',target_countries:'意向移民国家/地区',goals:'核心诉求',budget:'预算',urgency:'紧迫度',keep_cn:'是否必须保留中国国籍',constraints:'资金跨境/海外资产/其他限制'};
function buildSummary(){const fd=new FormData(document.getElementById('f'));let lines=[];Object.keys(labels).forEach(k=>{let v=(fd.get(k)||'').toString().trim();if(v)lines.push(labels[k]+'：'+v)});return lines.join('\n')||'姓名/代号：未填';}
function copySummary(){const t='【财税方案快速问卷提交】\n请直接生成诊断草案。\n\n【原始问卷数据】\n'+buildSummary();navigator.clipboard&&navigator.clipboard.writeText(t);document.getElementById('copyBox').classList.remove('hide');document.getElementById('copyBox').textContent=t;}
document.getElementById('f').addEventListener('submit',()=>{document.getElementById('summary').value=buildSummary();});
function showStatus(html){document.getElementById('f').classList.add('hide');const st=document.getElementById('status');st.classList.remove('hide');st.innerHTML=html;}
async function poll(issue){showStatus('<div class="ok"><b>✅ 问卷已提交：Issue #'+issue+'</b><br>诊断草案生成中，请稍候。<br><a target="_blank" href="https://github.com/sewen38/family-plan/issues/'+issue+'">查看提交记录</a></div>');try{const r=await fetch('/api/diagnosis/'+issue);const j=await r.json();if(j.ok&&(j.stage==='diagnosis_done'||j.stage==='completed')){showStatus('<div class="ok"><b>✅ 诊断草案已生成</b><br><a target="_blank" href="https://sewen38.github.io/family-plan/cloud-output/diagnosis-draft-issue-'+issue+'.html">打开诊断草案</a><br><br><a target="_blank" href="https://github.com/sewen38/family-plan/issues/'+issue+'">查看 GitHub 记录</a></div>');return}}catch(e){}setTimeout(()=>poll(issue),8000)}
const u=new URL(location.href);const issue=u.searchParams.get('issue');if(issue){poll(issue)}
</script></body></html>`;
}

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
    if (request.method === 'GET' && (path === '/mobile.html' || path === '/mobile' || path === '/phone')) {
      return new Response(mobileQuestionnaireHtml(request), { status: 200, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store, max-age=0' } });
    }

    if (request.method === 'GET' && (path === '/start.html' || path === '/start' || path === '/questionnaire')) {
      return serveQuestionnaire(request);
    }

    // ── POST / (default): create issue from questionnaire ──
    if (request.method === 'POST' && (path === '/' || path === '' || path === '/api/create-issue')) {
      let input = {};
      let formMode = false;
      const ctype = request.headers.get('content-type') || '';
      try {
        if (ctype.includes('application/json')) {
          input = await request.json();
        } else if (ctype.includes('application/x-www-form-urlencoded') || ctype.includes('multipart/form-data')) {
          formMode = true;
          const fd = await request.formData();
          input = Object.fromEntries(fd.entries());
        } else {
          input = await request.json();
        }
      } catch (_) { return json({ ok: false, error: 'invalid_input' }, 400, cors); }

      const summary = cleanText(input.summary, 18000);
      const name = cleanText(input.name, 80) || '未知';
      if (!summary || summary.length < 20) return formMode
        ? Response.redirect(`https://sewen38.github.io/family-plan/start.html?stage=submit_failed&v=form-empty`, 303)
        : json({ ok: false, error: 'empty_summary' }, 400, cors);

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

      if (formMode) {
        const redirectBase = cleanText(input.redirect || 'https://sewen38.github.io/family-plan/start.html', 500);
        const u = new URL(redirectBase);
        u.searchParams.set('issue', data.number);
        u.searchParams.set('stage', 'diagnosis');
        u.searchParams.set('v', 'form-post-fallback');
        return Response.redirect(u.toString(), 303);
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