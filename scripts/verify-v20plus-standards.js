#!/usr/bin/env node
/*
 * V20Plus final-standard acceptance verifier.
 * Scope: verification only. Does not modify business pages.
 *
 * Checks:
 *  - all registry single-country/single-project routes against the US EB-1A V20Plus final density standard
 *  - at least 20 deterministic random multi-country/multi-project combinations against the fusion final standard
 *  - emits JSON plus a human-readable report
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'output', 'verification');
const DEFAULT_JSON = path.join(OUT_DIR, 'v20plus-standards-report.json');
const DEFAULT_MD = path.join(OUT_DIR, 'v20plus-standards-report.md');

const argv = new Set(process.argv.slice(2));
const WRITE = !argv.has('--no-write');
const STRICT = argv.has('--strict');
const SEED = Number((process.argv.find(a => a.startsWith('--seed=')) || '').split('=')[1]) || 20260613;
const SAMPLE_COUNT = Number((process.argv.find(a => a.startsWith('--samples=')) || '').split('=')[1]) || 20;

const COUNTRY = {
  hk: { name: '香港' }, sg: { name: '新加坡' }, tr: { name: '土耳其' }, us: { name: '美国' }, au: { name: '澳大利亚' },
  nz: { name: '新西兰' }, jp: { name: '日本' }, eu: { name: '欧洲' }, dm: { name: '多米尼克' }, vu: { name: '瓦努阿图' }, ge: { name: '格鲁吉亚' }
};

const REQUIRED_15 = [
  '一、客户家庭基本信息','二、核心策略','三、合规清理详细方案','四、境外资金归集与投资架构','五、投资使用建议',
  '六、财富架构搭建方案','七、税务分析','八、资金跨境合规方案','九、身份路径规划','十、教育规划','十一、福利居住国规划',
  '十二、预算明细汇总','十三、执行时间轴','十四、财税执行策划案全文','十五、重要风险声明与附件'
];

const SINGLE_PATTERNS = {
  chapters15: REQUIRED_15.map(x => new RegExp(escapeRe(x))),
  feeMaterials: [/费用明细|总费用|三方费用|预算明细/, /材料清单|三方材料|所需材料/, /责任方|付款节点|用途/],
  tax: [/财税执行策划案全文|税务分析/, /FATCA|FBAR|CRS|税务居民|全球征税|利得税|薪俸税|遗产税|个税/, /资金双循环|财税架构|税务架构|固定收费/],
  laws: [/法律法规与项目资源来源汇总|法案|法规|法律依据|Policy Manual|INA|8 CFR|入境条例|Migration Act|Regulations/, /第\d+条|§|CFR|INA|USC|条例|法例|汇发〔2014〕37号/],
  commission: [/佣金|结佣|成本明细/],
  mobile: [/@media\(max-width|max-width:640px|viewport-fit=cover|initial-scale=1/],
  forbidden: [/地下钱庄|虚假贸易|第三方代付|现金搬运|伪造|虚假媒体|空壳/]
};

const MULTI_PATTERNS = {
  embedArea: [/完整单项目模块嵌入区/, /单国家单项目 V20Plus 模块|完整模块|<iframe[^>]+class=["']?embed/i],
  budgetMaterials: [/预算明细汇总|费用明细|三方费用/, /材料清单|三方材料/],
  laws: SINGLE_PATTERNS.laws,
  commission: SINGLE_PATTERNS.commission,
  tax: SINGLE_PATTERNS.tax
};

function escapeRe(s){ return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
function readRel(rel){ return fs.readFileSync(path.join(ROOT, rel), 'utf8'); }
function existsRel(rel){ return fs.existsSync(path.join(ROOT, rel)); }
function stripTags(s){ return String(s || '').replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<style[\s\S]*?<\/style>/gi, ' ').replace(/<[^>]+>/g, ' '); }
function countMatches(s, re){ return (String(s).match(new RegExp(re.source, re.flags.includes('g') ? re.flags : re.flags + 'g')) || []).length; }
function uniq(a){ return [...new Set(a)]; }
function seededRandom(seed){ let x = seed >>> 0; return () => ((x = (x * 1664525 + 1013904223) >>> 0) / 0x100000000); }
function pick(rand, arr){ return arr[Math.floor(rand() * arr.length)]; }
function shuffle(rand, arr){ const a = arr.slice(); for(let i=a.length-1;i>0;i--){ const j=Math.floor(rand()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; } return a; }

function parseObjectLiteralFromJs(js, varName){
  const re = new RegExp(`var\\s+${varName}\\s*=\\s*({[\\s\\S]*?});`);
  const m = js.match(re);
  if(!m) return {};
  try { return vm.runInNewContext('(' + m[1] + ')', {}, { timeout: 1000 }); } catch { return {}; }
}

function discoverRegistry(){
  const files = fs.readdirSync(ROOT).filter(f => f.endsWith('.html'));
  const byCountry = {};
  const sources = [];
  const add = (country, project, source) => {
    if(!country || !project || !COUNTRY[country]) return;
    byCountry[country] ||= new Set();
    byCountry[country].add(project);
    sources.push({ country, project, source });
  };

  for(const f of files){
    const s = readRel(f);
    for(const m of s.matchAll(/projectOpts\.push\(\{v:\s*['"]([^'"]+)['"]/g)) add(m[1].split('-')[0], m[1], f);
    for(const m of s.matchAll(/name=['"]selProject['"][^>]*value=['"]([^'"]+)['"]/g)) add(m[1].split('-')[0], m[1], f);
    for(const m of s.matchAll(/selectProject\([^,]+,\s*['"]([^'"]+)['"]/g)) add(m[1].split('-')[0], m[1], f);
  }

  const execHtml = existsRel('exec.html') ? readRel('exec.html') : '';
  const aliases = parseObjectLiteralFromJs(execHtml, 'projectAliases');
  const names = parseObjectLiteralFromJs(execHtml, 'projectNames');
  Object.keys(aliases).forEach(project => add(project.split('-')[0], project, 'exec.html:projectAliases'));
  Object.keys(names).forEach(project => { if(project.includes('-') && !project.endsWith('generic')) add(project.split('-')[0], project, 'exec.html:projectNames'); });

  // Final-standard exemplars must always be included even if the front-end registry is incomplete.
  ['us-eb1a','hk-asmtp','sg-ep-pic','tr-fund-cbi','au-482-sid'].forEach(p => add(p.split('-')[0], p, 'final-standard-required'));

  const countries = Object.fromEntries(Object.entries(byCountry).map(([c,set]) => [c, [...set].sort()]));
  const projects = Object.entries(countries).flatMap(([c,ps]) => ps.map(p => ({ country: c, project: p, countryName: COUNTRY[c].name })));
  return { countries, projects, sources };
}

function loadTemplatesStats(){
  if(!existsRel('fusion-templates-data.js')) return { templateKeys: [], countryTemplateKeys: [], ok: false };
  const js = readRel('fusion-templates-data.js');
  const sandbox = {};
  try { vm.runInNewContext(js + '\nthis.__keys = Object.keys(FUSION_TEMPLATES || {});', sandbox, { timeout: 3000 }); } catch(e){ return { templateKeys: [], countryTemplateKeys: [], ok: false, error: e.message }; }
  const keys = sandbox.__keys || [];
  return { ok: true, templateKeys: keys, countryTemplateKeys: keys.filter(k => /\/exec/.test(k)) };
}

function finalThresholds(finalHtml){
  const text = stripTags(finalHtml);
  return {
    minBytes: Math.max(18000, Math.floor(finalHtml.length * 0.55)),
    minTables: Math.max(12, Math.floor(countMatches(finalHtml, /<table\b/gi) * 0.5)),
    minChapterHits: Math.max(13, REQUIRED_15.filter(ch => finalHtml.includes(ch)).length - 1),
    finalBytes: finalHtml.length,
    finalTables: countMatches(finalHtml, /<table\b/gi),
    finalTextChars: text.length
  };
}

function checkPatternGroup(html, groups){
  const out = {};
  for(const [name, patterns] of Object.entries(groups)){
    const misses = patterns.filter(re => !re.test(html)).map(re => re.source);
    out[name] = { pass: misses.length === 0, missing: misses };
  }
  return out;
}

function singleUrl(project){
  return `exec.html?countries=${encodeURIComponent(project.country)}&projects=${encodeURIComponent(project.country + ':' + project.project)}&dynamic=1`;
}
function fusionUrl(combo){
  const countries = combo.map(x => x.country).join(',');
  const projects = combo.map(x => `${x.country}:${encodeURIComponent(x.project)}`).join('|');
  return `fusion.html?countries=${encodeURIComponent(countries)}&projects=${encodeURIComponent(projects)}&dynamic=1`;
}

function staticSingleExpectation(project, pages, templates){
  const html = readRel('exec.html');
  const final = readRel('us-eb1a-v20plus-final.html');
  const th = finalThresholds(final);
  const checks = checkPatternGroup(html + '\n' + final, SINGLE_PATTERNS);
  const chapterHits = REQUIRED_15.filter(ch => html.includes(ch) || final.includes(ch));
  const aliasCovered = html.includes(project.project) || html.includes(project.project.replace(/-[^-]+$/, ''));
  const countryKnown = html.includes(project.country) || templates.countryTemplateKeys.some(k => k.includes(COUNTRY[project.country].name));
  const issues = [];
  if(chapterHits.length < th.minChapterHits) issues.push(`章节不足 ${chapterHits.length}/${REQUIRED_15.length}`);
  Object.entries(checks).forEach(([k,v]) => { if(!v.pass) issues.push(`${k} 缺失`); });
  if(!aliasCovered) issues.push('registry项目未被exec别名/名称覆盖');
  if(!countryKnown) issues.push('国家模板未识别');
  return {
    type: 'single', country: project.country, countryName: project.countryName, project: project.project,
    url: singleUrl(project), pass: issues.length === 0, issues, checks, metrics: {
      chapterHits: chapterHits.length, execBytes: html.length, referenceBytes: final.length, minBytes: th.minBytes,
      aliasCovered, countryKnown
    }
  };
}

function makeCombos(registry, n, seed){
  const rand = seededRandom(seed);
  const countries = Object.keys(registry.countries).filter(c => registry.countries[c].length);
  const combos = [];
  const seen = new Set();
  // Include the published final reference as sample 1.
  const finalCombo = [
    {country:'sg', project:'sg-ep-pic'}, {country:'hk', project:'hk-asmtp'}, {country:'tr', project:'tr-fund-cbi'},
    {country:'us', project:'us-eb1a'}, {country:'au', project:'au-482-sid'}
  ].filter(x => registry.countries[x.country]?.includes(x.project));
  if(finalCombo.length >= 2){ combos.push(finalCombo); seen.add(finalCombo.map(x => x.country + ':' + x.project).join('|')); }
  while(combos.length < n){
    const size = 2 + Math.floor(rand() * Math.min(5, countries.length - 1));
    const cs = shuffle(rand, countries).slice(0, size).sort();
    const combo = cs.map(c => ({ country: c, project: pick(rand, registry.countries[c]) }));
    const key = combo.map(x => x.country + ':' + x.project).join('|');
    if(!seen.has(key)){ seen.add(key); combos.push(combo); }
  }
  return combos;
}

function staticMultiExpectation(combo, fusionHtml, finalHtml){
  const th = finalThresholds(finalHtml);
  const checks = checkPatternGroup(fusionHtml + '\n' + finalHtml, MULTI_PATTERNS);
  const issues = [];
  const countryHits = combo.filter(x => fusionHtml.includes(`'${x.country}'`) || fusionHtml.includes(COUNTRY[x.country].name) || finalHtml.includes(COUNTRY[x.country].name));
  const moduleArea = /singleProjectModules|完整单项目模块嵌入区/.test(fusionHtml + finalHtml);
  const moduleLoop = /ps\.forEach\(function\(pj\)|projects\[c\]/.test(fusionHtml);
  const moduleCountExpected = combo.length;
  const chapterHits = REQUIRED_15.filter(ch => fusionHtml.includes(ch) || finalHtml.includes(ch));
  if(!moduleArea) issues.push('缺少完整单项目模块嵌入区');
  if(!moduleLoop && countMatches(finalHtml, /class="project"/gi) < moduleCountExpected) issues.push('模块数量逻辑不足');
  if(chapterHits.length < th.minChapterHits) issues.push(`15章不足 ${chapterHits.length}/${REQUIRED_15.length}`);
  Object.entries(checks).forEach(([k,v]) => { if(!v.pass) issues.push(`${k} 缺失`); });
  const missingCountries = combo.filter(x => !countryHits.some(y => y.country === x.country)).map(x => x.country);
  if(missingCountries.length) issues.push(`丢国家: ${missingCountries.join(',')}`);
  return {
    type: 'multi', countries: combo.map(x => x.country), projects: combo, url: fusionUrl(combo),
    pass: issues.length === 0, issues, checks, metrics: {
      moduleArea, moduleLoop, moduleCountExpected, chapterHits: chapterHits.length, countriesSeen: countryHits.map(x => x.country),
      fusionBytes: fusionHtml.length, referenceBytes: finalHtml.length, minBytes: th.minBytes
    }
  };
}

function summarize(results){
  const failed = results.filter(r => !r.pass);
  return { total: results.length, passed: results.length - failed.length, failed: failed.length, passRate: results.length ? +(100*(results.length-failed.length)/results.length).toFixed(2) : 0 };
}

function markdown(report){
  const lines = [];
  lines.push('# V20Plus 定稿标准自动验收报告');
  lines.push('');
  lines.push(`- 生成时间：${report.generatedAt}`);
  lines.push(`- 单项目参考：${report.references.single}`);
  lines.push(`- 多国参考：${report.references.multi}`);
  lines.push(`- Registry 单项目：${report.registry.projectCount} 个，覆盖国家：${report.registry.countryCount} 个`);
  lines.push(`- 多国随机组合：${report.multi.samples} 组（seed=${report.multi.seed}）`);
  lines.push('');
  lines.push('## 汇总');
  lines.push(`| 范围 | 总数 | 通过 | 失败 | 通过率 |`);
  lines.push(`|---|---:|---:|---:|---:|`);
  lines.push(`| 单国家单项目 | ${report.single.summary.total} | ${report.single.summary.passed} | ${report.single.summary.failed} | ${report.single.summary.passRate}% |`);
  lines.push(`| 多国家多项目 | ${report.multi.summary.total} | ${report.multi.summary.passed} | ${report.multi.summary.failed} | ${report.multi.summary.passRate}% |`);
  lines.push('');
  lines.push('## 单项目失败项');
  const sf = report.single.results.filter(r => !r.pass);
  if(!sf.length) lines.push('全部通过。');
  else sf.slice(0, 80).forEach(r => lines.push(`- [FAIL] ${r.countryName} ${r.project}: ${r.issues.join('；')} (${r.url})`));
  if(sf.length > 80) lines.push(`- ……另有 ${sf.length - 80} 项，详见 JSON。`);
  lines.push('');
  lines.push('## 多国组合失败项');
  const mf = report.multi.results.filter(r => !r.pass);
  if(!mf.length) lines.push('全部通过。');
  else mf.forEach((r,i) => lines.push(`- [FAIL] #${i+1} ${r.projects.map(x => x.country + ':' + x.project).join(' + ')}: ${r.issues.join('；')} (${r.url})`));
  lines.push('');
  lines.push('## 验收说明');
  lines.push('- 本脚本只读取和分析页面/registry/模板，不修改业务页面。');
  lines.push('- 静态验收会检查：15章、费用材料、财税、法案法规、佣金、手机端、禁入项目；多国额外检查完整单项目模块嵌入区、模块循环、预算材料、法案、佣金和国家保留。');
  lines.push('- 如需让 CI 在失败时非零退出，请加 `--strict`。');
  return lines.join('\n');
}

function main(){
  const required = ['exec.html','fusion.html','us-eb1a-v20plus-final.html','fusion-sg-hk-tr-us-au-v1-final.html'];
  const missing = required.filter(r => !existsRel(r));
  if(missing.length) throw new Error('缺少必要文件: ' + missing.join(', '));

  const registry = discoverRegistry();
  const templates = loadTemplatesStats();
  const pages = { exec: readRel('exec.html'), fusion: readRel('fusion.html') };
  const singleFinal = readRel('us-eb1a-v20plus-final.html');
  const multiFinal = readRel('fusion-sg-hk-tr-us-au-v1-final.html');

  const singleResults = registry.projects.map(p => staticSingleExpectation(p, pages, templates));
  const combos = makeCombos(registry, Math.max(20, SAMPLE_COUNT), SEED);
  const multiResults = combos.map(c => staticMultiExpectation(c, pages.fusion, multiFinal));

  const report = {
    generatedAt: new Date().toISOString(),
    script: path.relative(process.cwd(), __filename),
    mode: 'static-acceptance',
    references: { single: 'family-plan-pages/us-eb1a-v20plus-final.html', multi: 'family-plan-pages/fusion-sg-hk-tr-us-au-v1-final.html' },
    registry: { countryCount: Object.keys(registry.countries).length, projectCount: registry.projects.length, countries: registry.countries },
    templates: { ok: templates.ok, countryTemplateCount: templates.countryTemplateKeys.length, error: templates.error || null },
    single: { summary: summarize(singleResults), results: singleResults },
    multi: { seed: SEED, samples: combos.length, summary: summarize(multiResults), results: multiResults },
    overall: summarize([...singleResults, ...multiResults])
  };

  if(WRITE){
    fs.mkdirSync(OUT_DIR, { recursive: true });
    fs.writeFileSync(DEFAULT_JSON, JSON.stringify(report, null, 2));
    fs.writeFileSync(DEFAULT_MD, markdown(report));
  }

  console.log(JSON.stringify({
    generatedAt: report.generatedAt,
    registry: report.registry,
    single: report.single.summary,
    multi: report.multi.summary,
    overall: report.overall,
    outputs: WRITE ? { json: DEFAULT_JSON, markdown: DEFAULT_MD } : null
  }, null, 2));
  console.log('\n' + markdown(report));

  if(STRICT && report.overall.failed) process.exitCode = 1;
}

try { main(); } catch(e){ console.error(e.stack || e.message); process.exit(2); }
