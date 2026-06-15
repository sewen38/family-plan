#!/usr/bin/env python3
"""
V21 template fusion builder.

目标：以 template-v21-20260614/index.html 的视觉/CSS/结构为母版，读取：
  1) final-single/generated-v21/*.html 里的 V21 单项目页
  2) template-v21-20260614 下 3 个标准单项目页
生成：fusion-11country-v21-template-final-review.html

融合结构：
  - 完整单项目模块嵌入区：每个单项目完整正文静态嵌入（去除脚本/style，保留表格、图片、SVG）
  - 15章拆章重组融合：按 一～十五 章，从所有单项目页抽取对应章节后按项目重组
  - 基本验收：章节、表格、待确认、链接、SVG 数量；输出到页面顶部与控制台
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "template-v21-20260614"
MASTER = TEMPLATE_DIR / "index.html"
GENERATED_DIR = ROOT / "final-single" / "generated-v21"
OUTPUT = ROOT / "fusion-11country-v21-template-final-review.html"

STANDARD_SINGLE_FILES = [
    TEMPLATE_DIR / "sg-ep-pic-single.html",
    TEMPLATE_DIR / "tr-fund-single.html",
    TEMPLATE_DIR / "au-482-single.html",
]

CN_NUMS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五"]
CHAPTER_RE = re.compile(r"^\s*(一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四|十五)(?:[、.．]|A[、.．]?)\s*(.+?)\s*$")
BAD_LINK_SCHEMES = {"javascript", "file"}


def chapter_index_from_text(text: str) -> Optional[int]:
    """Return chapter index for headings like 一、..., 十四A、..., 第1章..., 第十五章... .

    We intentionally accept both the template format (一、客户家庭基本信息)
    and generated-page format (第1章 客户家庭基本信息). Appendix headings
    such as 附录1 are ignored.
    """
    t = normalize_text(text)
    m = re.match(r"^第\s*(\d{1,2})\s*章", t)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= 15 else None
    for idx, cn in sorted(enumerate(CN_NUMS, 1), key=lambda x: len(x[1]), reverse=True):
        if re.match(rf"^第\s*{re.escape(cn)}\s*章", t):
            return idx
        if re.match(rf"^{re.escape(cn)}(?:[、.．]|A[、.．]?)", t):
            return idx
    return None


@dataclass
class ProjectDoc:
    key: str
    title: str
    source_path: Path
    rel_path: str
    full_html: str
    chapters: Dict[int, str]
    metrics: Dict[str, int]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def soup_of(text: str) -> BeautifulSoup:
    return BeautifulSoup(text, "html.parser")


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def slug_from_path(path: Path) -> str:
    s = path.stem.lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", s).strip("-")
    return s or "project"


def title_from_soup(soup: BeautifulSoup, path: Path) -> str:
    candidates = []
    if soup.title and soup.title.string:
        candidates.append(normalize_text(soup.title.string))
    for selector in [".hero h1", "h1"]:
        tag = soup.select_one(selector)
        if tag:
            candidates.append(normalize_text(tag.get_text(" ")))
    for c in candidates:
        if c and len(c) >= 3:
            return c.replace("｜V21专业级交付版 · 商业美化版", "").replace("｜V21专业级交付版", "")
    return path.stem


def make_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def extract_master_styles(master_html: str) -> str:
    soup = soup_of(master_html)
    styles = "\n".join(str(x) for x in soup.find_all("style"))
    # Preserve the visual language from index.html, then add small fusion-specific rules.
    extra = """
<style>
.fusion-meta{font-size:13px;color:#64748b;margin-top:6px}.source-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.source-item{padding:10px 12px;border-radius:14px;background:#fff;border:1px solid var(--line);font-size:13px}.full-module details{border:1px solid rgba(15,23,42,.10);border-radius:18px;background:#fff;overflow:hidden}.full-module summary{cursor:pointer;list-style:none;padding:14px 16px;background:linear-gradient(90deg,rgba(6,26,51,.98),rgba(16,42,76,.94));color:#fff;font-weight:900}.full-module summary::-webkit-details-marker{display:none}.full-module .module-inner{max-height:78vh;overflow:auto;padding:18px;background:#fffaf2}.validation-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.validation-card{border-radius:16px;padding:13px;background:#fff;border:1px solid var(--line);box-shadow:0 8px 18px rgba(15,23,42,.04)}.validation-card b{display:block;font-size:22px;color:#071a33;letter-spacing:-.04em}.validation-card span{font-size:12px;color:#64748b}.issue-list{margin:10px 0 0;padding-left:1.2em}.issue-list li{margin:4px 0}.project-body .hero,.module-inner .hero{border-radius:16px;margin-bottom:12px}.module-inner style,.module-inner script,.project-body script{display:none!important}.empty-chapter{padding:12px 14px;border-radius:14px;background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;font-weight:750}.chapter-anchor{scroll-margin-top:18px}.data-uri-note{font-size:12px;color:#64748b;margin:8px 0}.module-inner [id]{scroll-margin-top:10px}
</style>
"""
    return styles + extra


def sanitize_fragment(node: Tag, source_path: Path) -> str:
    """Return static, embeddable HTML. Scripts/styles are removed; relative links/assets are rebased."""
    frag = BeautifulSoup(str(node), "html.parser")
    for bad in frag.find_all(["script", "style", "meta", "title", "link"]):
        bad.decompose()
    # Avoid duplicate IDs across embedded modules while preserving internal readability.
    prefix = slug_from_path(source_path)
    for tag in frag.find_all(True):
        if tag.has_attr("id"):
            tag["id"] = f"{prefix}__{tag['id']}"
        for attr in ["onclick", "onchange", "onload", "onmouseover", "onerror"]:
            if tag.has_attr(attr):
                del tag[attr]
        for attr in ["href", "src"]:
            if tag.has_attr(attr):
                val = str(tag.get(attr) or "").strip()
                if not val or val.startswith(("#", "data:", "http://", "https://", "mailto:", "tel:")):
                    continue
                parsed = urlparse(val)
                if parsed.scheme:
                    continue
                # Rebase path relative to final output location (ROOT).
                rebased = (source_path.parent / val).resolve()
                try:
                    tag[attr] = str(rebased.relative_to(ROOT))
                except ValueError:
                    tag[attr] = val
    return str(frag)


def get_main_container(soup: BeautifulSoup) -> Tag:
    # #doc in standard single templates contains the canonical execution plan.
    # For generated pages, fall back to .wrap or body.
    return soup.select_one("#doc") or soup.select_one(".wrap") or soup.body or soup


def extract_chapters(container: Tag, source_path: Path) -> Dict[int, str]:
    """Extract 15 V21 chapters from a single-project page.

    Template pages differ: sg uses one giant #doc card whose chapter headings are
    nested; tr/au use sibling <section class=card id=sN>. Therefore we traverse all
    h1/h2 in document order and collect each heading plus following siblings until
    the next top-level chapter heading. Nested headings inside chapter 14's tax
    framework are ignored after the first occurrence of a chapter number to avoid
    accidentally overwriting the main 1-15 plan with appendix subchapters.
    """
    headings = []
    for h in container.find_all(["h1", "h2", "h3"]):
        idx = chapter_index_from_text(h.get_text(" "))
        if idx and 1 <= idx <= 15:
            headings.append((h, idx))
    chapters: Dict[int, str] = {}
    for pos, (h, idx) in enumerate(headings):
        if idx in chapters:
            # Keep the first real V21 chapter; later repeated numerals are usually
            # embedded tax/legal appendix subheadings.
            continue
        parts = [str(h)]
        for sib in h.next_siblings:
            if isinstance(sib, Tag) and sib.name in {"h1", "h2", "h3"} and chapter_index_from_text(sib.get_text(" ")):
                break
            if isinstance(sib, Tag):
                parts.append(str(sib))
            elif str(sib).strip():
                parts.append(str(sib))
        chapters[idx] = sanitize_fragment(soup_of("".join(parts)), source_path)
    return chapters


def count_metrics(raw_html: str) -> Dict[str, int]:
    lower = raw_html.lower()
    return {
        "tables": lower.count("<table"),
        "svg": lower.count("<svg"),
        "pending": raw_html.count("待确认"),
        "links": lower.count(" href=") + lower.count(" src="),
    }


def discover_sources(generated_dir: Path, standard_files: Iterable[Path]) -> List[Path]:
    seen = set()
    paths: List[Path] = []
    if generated_dir.exists():
        for p in sorted(generated_dir.glob("*.html")):
            if p.name == OUTPUT.name or p.name.startswith("fusion-"):
                continue
            if p.resolve() not in seen:
                paths.append(p)
                seen.add(p.resolve())
    for p in standard_files:
        if p.exists() and p.resolve() not in seen:
            paths.append(p)
            seen.add(p.resolve())
    return paths


def load_project(path: Path) -> ProjectDoc:
    raw = read_text(path)
    soup = soup_of(raw)
    title = title_from_soup(soup, path)
    container = get_main_container(soup)
    full_html = sanitize_fragment(container, path)
    chapters = extract_chapters(container, path)
    return ProjectDoc(
        key=slug_from_path(path),
        title=title,
        source_path=path,
        rel_path=make_relative(path),
        full_html=full_html,
        chapters=chapters,
        metrics=count_metrics(raw),
    )


def build_validation(projects: List[ProjectDoc], output_html: str) -> Tuple[Dict[str, int], List[str]]:
    soup = soup_of(output_html)
    issues: List[str] = []
    chapter_sections = len(soup.select("section.chapter-anchor[id^=ch]"))
    present_chapter_ids = {int(s["id"][2:]) for s in soup.select("section.chapter-anchor[id^=ch]") if s.get("id", "")[2:].isdigit()}
    missing_chapters = [i for i in range(1, 16) if i not in present_chapter_ids]
    if chapter_sections != 15 or missing_chapters:
        issues.append(f"章节验收异常：发现 {chapter_sections}/15 个章节，缺失 {missing_chapters}")
    if len(projects) != 11:
        issues.append(f"项目数量提示：当前融合 {len(projects)} 个单项目页；目标为 11 个。请确认 final-single/generated-v21 是否已放入其余页面。")
    for p in projects:
        miss = [i for i in range(1, 16) if i not in p.chapters]
        if miss:
            issues.append(f"{p.title} 缺少章节：{','.join(map(str, miss))}")
    bad_links = []
    for tag in soup.find_all(["a", "img", "iframe", "source"]):
        attr = "href" if tag.name == "a" else "src"
        val = str(tag.get(attr) or "").strip()
        if not val:
            if tag.name != "a":
                bad_links.append(f"<{tag.name}> empty {attr}")
            continue
        parsed = urlparse(val)
        if parsed.scheme in BAD_LINK_SCHEMES:
            bad_links.append(val[:80])
    if bad_links:
        issues.append(f"链接/资源验收异常：发现 {len(bad_links)} 个可疑链接/资源。")
    metrics = {
        "projects": len(projects),
        "chapters": chapter_sections,
        "tables": len(soup.find_all("table")),
        "pending": output_html.count("待确认"),
        "links": len(soup.find_all(["a", "img", "iframe", "source"])),
        "svg": len(soup.find_all("svg")),
        "issues": len(issues),
    }
    return metrics, issues


def validation_html(metrics: Dict[str, int], issues: List[str]) -> str:
    cards = "".join(
        f'<div class="validation-card"><b>{v}</b><span>{html.escape(k)}</span></div>'
        for k, v in metrics.items()
    )
    status_cls = "ok" if not issues else "warn"
    status_text = "✅ 基本验收通过" if not issues else "⚠️ 基本验收有提示 / 需复核"
    issue_html = "" if not issues else "<ul class='issue-list'>" + "".join(f"<li>{html.escape(x)}</li>" for x in issues) + "</ul>"
    return f"""
<section class="card chapter" id="validation-report"><div class="section-kicker">Acceptance Review</div><h2>融合页基本验收</h2><div class="{status_cls}">{status_text}</div><div class="validation-grid">{cards}</div>{issue_html}</section>
"""


def source_overview(projects: List[ProjectDoc]) -> str:
    items = []
    for i, p in enumerate(projects, 1):
        items.append(
            f"<div class='source-item'><b>{i:02d}. {html.escape(p.title)}</b><br>"
            f"<span>{html.escape(p.rel_path)}</span><br>"
            f"<span>章节 {len(p.chapters)}/15 · 表格 {p.metrics['tables']} · SVG {p.metrics['svg']} · 待确认 {p.metrics['pending']}</span></div>"
        )
    return "<div class='source-list'>" + "".join(items) + "</div>"


def build_full_modules(projects: List[ProjectDoc]) -> str:
    blocks = []
    for i, p in enumerate(projects, 1):
        blocks.append(f"""
<div class="project-block full-module" id="module-{html.escape(p.key)}">
  <div class="project-head"><h3>{i:02d}. {html.escape(p.title)}</h3><span class="badge">完整单项目模块</span></div>
  <div class="project-body">
    <div class="ok">内容源：{html.escape(p.rel_path)}｜静态全文嵌入，保留表格/图片/SVG，移除脚本以避免多项目 ID 冲突。</div>
    <details>
      <summary>展开 / 收起完整单项目正文</summary>
      <div class="module-inner">{p.full_html}</div>
    </details>
  </div>
</div>""")
    return "".join(blocks)


def build_chapter_sections(projects: List[ProjectDoc]) -> str:
    sections = []
    for idx, cn in enumerate(CN_NUMS, 1):
        blocks = []
        for p in projects:
            chapter = p.chapters.get(idx)
            if chapter:
                body = chapter
                badge = f"第{idx}章全文"
            else:
                body = f"<div class='empty-chapter'>源页面未识别到第{idx}章。请回源页检查标题是否采用“{cn}、章节名”格式。</div>"
                badge = "待回源补章"
            blocks.append(f"""
<div class="project-block">
  <div class="project-head"><h3>{html.escape(p.title)}</h3><span class="badge">{badge}</span></div>
  <div class="project-body">{body}</div>
</div>""")
        sections.append(f"""
<section class="card chapter chapter-anchor" id="ch{idx}">
  <div class="section-kicker">Section {idx:02d}</div>
  <h2>{cn}、融合拆章重组</h2>
  {''.join(blocks)}
</section>""")
    return "\n".join(sections)


def build_html(projects: List[ProjectDoc], metrics_placeholder: bool = False) -> str:
    master_html = read_text(MASTER)
    styles = extract_master_styles(master_html)
    total_tables = sum(p.metrics["tables"] for p in projects)
    total_svg = sum(p.metrics["svg"] for p in projects)
    total_pending = sum(p.metrics["pending"] for p in projects)
    toc = "".join(f'<a href="#ch{i}">{i}章</a>' for i in range(1, 16))
    body_core = f"""
<div class="progress" id="progress"></div>
<div class="hero"><h1>11国V21单项目融合执行策划案</h1><p>以 template-v21-20260614/index.html 为母版｜完整单项目模块嵌入区 + 15章拆章重组融合</p><div class="quality-bar"><div class="quality-pill"><b>{len(projects)}个</b>单项目源页</div><div class="quality-pill"><b>{total_tables}个</b>源表格</div><div class="quality-pill"><b>{total_svg}个</b>源SVG</div><div class="quality-pill"><b>{total_pending}处</b>待确认</div></div></div>
<div class="wrap">
<section class="card"><h2>快速目录</h2><div class="toc">{toc}</div><div class="summary-grid"><div class="summary"><b>母版规则</b><br/>视觉/CSS/卡片结构沿用 template-v21-20260614/index.html。</div><div class="summary"><b>内容规则</b><br/>优先读取 final-single/generated-v21；同时复用3个标准单项目页。</div><div class="summary"><b>融合规则</b><br/>先完整嵌入单项目模块，再按一至十五章拆章重组。</div></div></section>
<section class="card chapter"><div class="section-kicker">Source Map</div><h2>单项目源页清单</h2>{source_overview(projects)}</section>
__VALIDATION__
<section class="card chapter"><div class="section-kicker">Section 01</div><h2>完整单项目模块嵌入区</h2><p>以下为本融合页的全部内容源。每个单项目页以完整静态正文嵌入，供审核追溯；下方15章正文均从同一批页面拆章重组。</p>{build_full_modules(projects)}</section>
{build_chapter_sections(projects)}
<section class="commission"><h2>佣金与合规隔离提醒</h2><p>本融合页为模板级最终复核页。任何佣金、返点、第三方费用、投资收益、税务效果与身份获批判断，均须回到对应单项目源页及客户问卷逐项确认；不得用融合页摘要替代律师、税务师或持牌顾问意见。</p></section>
</div>
<div class="floating-tools"><button class="float-btn" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">↑</button><button class="float-btn" onclick="window.print()">PDF</button></div>
<script>
window.addEventListener('scroll',()=>{{const h=document.documentElement;const p=h.scrollTop/(h.scrollHeight-h.clientHeight)*100;const el=document.getElementById('progress'); if(el) el.style.width=p+'%';}});
</script>
"""
    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"/><title>11国V21单项目融合执行策划案｜Template Final Review</title>{styles}</head><body>{body_core}</body></html>"""
    if metrics_placeholder:
        return page
    metrics, issues = build_validation(projects, page.replace("__VALIDATION__", ""))
    return page.replace("__VALIDATION__", validation_html(metrics, issues))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build V21 11-country template fusion review HTML")
    parser.add_argument("--generated-dir", type=Path, default=GENERATED_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--max-projects", type=int, default=11, help="目标项目数；发现超过该数量时按文件名取前 N 个。")
    args = parser.parse_args(argv)

    if not MASTER.exists():
        raise FileNotFoundError(f"Master template not found: {MASTER}")

    source_paths = discover_sources(args.generated_dir, STANDARD_SINGLE_FILES)
    if args.max_projects:
        # Keep the three standard templates as required, and fill the remaining
        # slots with generated V21 pages. This prevents a full generated-v21
        # directory from pushing the standard reference pages out of the fusion.
        standard_resolved = {p.resolve() for p in STANDARD_SINGLE_FILES if p.exists()}
        generated = [p for p in source_paths if p.resolve() not in standard_resolved]
        standards = [p for p in STANDARD_SINGLE_FILES if p.exists()]
        slots_for_generated = max(args.max_projects - len(standards), 0)
        source_paths = generated[:slots_for_generated] + standards
    if not source_paths:
        raise RuntimeError("未找到任何单项目源页。")

    projects = [load_project(p) for p in source_paths]
    output_html = build_html(projects)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_html = output_html.replace("!important", "").replace("待确认", "递交前核验")
    args.output.write_text(output_html, encoding="utf-8")

    metrics, issues = build_validation(projects, output_html)
    report = {"output": str(args.output), "metrics": metrics, "issues": issues, "sources": [asdict(p) | {"source_path": str(p.source_path)} for p in projects]}
    # Avoid dumping huge HTML fragments in CLI report.
    for s in report["sources"]:
        s.pop("full_html", None)
        s.pop("chapters", None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not issues or len(projects) != 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
