#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V21 人工审核标准检查脚本：防止“内容补强页/工作底稿/附录页”冒充“定稿页”。

用途：
  - 审核 V21 单国家单项目页与多项目融合页 HTML。
  - 生成机器初筛结果 + 人工复核清单。
  - 重点检查模板形态、章节硬门槛、图形/视觉风险、iframe 单项目模块路径。

示例：
  python3 scripts/audit-v21-human-standard.py fusion-11country-v21-template-final-review-v5.html
  python3 scripts/audit-v21-human-standard.py final-single/manual/sg-ep-pic-v21-beautified-readable.html --md-report output/verification/audit-sg.md
  python3 scripts/audit-v21-human-standard.py *.html --json

判定说明：
  - 本脚本是“硬门槛初筛 + 人工审核模板”，不能替代人工逐章阅读。
  - 任一 P0 FAIL：不得命名/发布为 final，只能 internal-review / candidate-review / structure-preview / draft。
  - WARNING 不一定阻断，但需要人工说明原因、截图或修复记录。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from html import unescape
from pathlib import Path
from typing import Iterable, List, Dict, Tuple, Optional

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/family-plan-v21-final/SKILL.md"
REGISTRY = ROOT / "template-registry/template-registry.json"
STANDARD = ROOT / "template-registry/v21-final-exec-standard.md"
TEMPLATE_DIR = ROOT / "template-v21-20260614"
FUSION_MASTER = TEMPLATE_DIR / "index.html"
SAMPLES = [
    TEMPLATE_DIR / "sg-ep-pic-single.html",
    TEMPLATE_DIR / "au-482-single.html",
    TEMPLATE_DIR / "tr-fund-single.html",
]

DEGRADE_TERMS = [
    "内容补强", "补强说明", "补强页", "整改说明", "修复说明", "生成说明", "差距说明",
    "附录页", "附录说明", "工作底稿", "底稿", "过程稿", "过程页", "中间页", "临时页",
    "占位", "占位符", "placeholder", "TODO", "TBD", "draft only", "not final",
    "结构预览", "候选预览", "内部预览", "内部审核", "candidate-review", "internal-review", "structure-preview",
    "待补强", "后续补充", "详见源页", "仅供测试", "测试页", "fallback", "V20Plus"
]

UNRESOLVED_TERMS = ["待确认", "按官方", "以官方为准", "根据实际情况", "视情况", "后续补充", "详见源页"]

CHAPTERS = {
    1: ["一、客户家庭基本信息", "客户家庭基本信息"],
    2: ["二、核心策略", "核心策略"],
    3: ["三、合规清理详细方案", "合规清理详细方案"],
    4: ["四、境外资金归集与投资架构", "境外资金归集", "投资架构"],
    5: ["五、投资使用建议", "资格使用建议", "投资/资格使用建议"],
    6: ["六、财富架构搭建方案", "财富架构"],
    7: ["七、税务分析", "税务分析"],
    8: ["八、资金跨境合规方案", "资金跨境合规"],
    9: ["九、身份路径规划", "身份路径"],
    10: ["十、教育规划", "教育规划"],
    11: ["十一、福利居住国规划", "福利居住国"],
    12: ["十二、预算明细汇总", "预算明细", "费用总表"],
    13: ["十三、执行时间轴", "执行时间轴", "时间轴"],
    14: ["十四、财税执行策划案全文", "财税执行策划案全文"],
    15: ["十五、重要风险声明与条款级法案附件", "重要风险声明", "条款级法案附件"],
}

DIAGRAM_WORDS = ["架构图", "流程图", "路径图", "闭环图", "时间轴", "示意图", "Mermaid", "svg", "<svg", "graphic", "flow"]
CH6_ARCH_WORDS = ["财富架构", "税务", "资金流", "利润流", "SPV", "信托", "保险", "投资账户", "CRS", "CFC", "FATCA", "FBAR", "ODI", "37号文", "DTA", "预提税"]
CH9_PATH_WORDS = ["身份路径", "申请", "获批", "续签", "永居", "PR", "公民", "入籍", "护照", "阶段"]
CH13_FLOW_WORDS = ["执行时间轴", "阶段", "第", "周", "月", "递交", "获批", "责任人", "里程碑"]
CH12_WORDS = ["预算", "官方费", "政府费", "律师", "顾问", "第三方", "材料", "公证", "翻译", "生活", "总计"]
CH14_WORDS = ["财税", "税务居民", "个人所得税", "公司税", "CRS", "CFC", "申报", "资金来源", "税率", "执行动作"]
CH15_WORDS = ["风险", "条款", "法案", "法规", "政策", "官方链接", "适用", "禁止", "红线", "免责声明"]

@dataclass
class Check:
    code: str
    title: str
    status: str  # PASS / FAIL / WARN / REVIEW
    severity: str  # P0 / P1 / P2
    detail: str
    evidence: List[str]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def strip_tags(s: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    return re.sub(r"\s+", "", strip_tags(s)).lower()


def count_terms(text: str, terms: Iterable[str]) -> Dict[str, int]:
    return {t: text.count(t) for t in terms if text.count(t) > 0}


def has_any(text: str, terms: Iterable[str]) -> bool:
    return any(t.lower() in text.lower() for t in terms)


def extract_chapter(html: str, n: int) -> str:
    """Best-effort extraction from chapter n to next chapter.

    Prefer explicit id="chN" anchors before fuzzy heading terms. The old implementation
    searched generic terms such as “身份路径” and “预算明细” first, which could match
    the table of contents or earlier summary text and falsely fail chapter gates.
    """
    starts = []
    # id="ch9" / id='ch9' / id=ch9 first
    m = re.search(rf'id\s*=\s*(["\']?)ch{n}\b\1', html, flags=re.I)
    if m:
        starts.append(m.start())
    if not starts:
        heads = CHAPTERS[n]
        for h in heads:
            m = re.search(re.escape(h), html, flags=re.I)
            if m:
                starts.append(m.start())
    if not starts:
        return ""
    start = min(starts)
    next_positions = []
    for k in range(n + 1, 16):
        m = re.search(rf'id\s*=\s*(["\']?)ch{k}\b\1', html[start + 1 :], flags=re.I)
        if m:
            next_positions.append(start + 1 + m.start())
            continue
        for h in CHAPTERS[k]:
            m = re.search(re.escape(h), html[start + 1 :], flags=re.I)
            if m:
                next_positions.append(start + 1 + m.start())
    end = min(next_positions) if next_positions else len(html)
    return html[start:end]


def attr_values(html: str, tag: str, attr: str) -> List[str]:
    pattern = re.compile(rf"<{tag}\b[^>]*\s{attr}\s*=\s*([\"'])(.*?)\1", re.I | re.S)
    return [unescape(m.group(2).strip()) for m in pattern.finditer(html)]


def local_or_http_exists(ref: str, base_file: Path, timeout: float = 4.0) -> Tuple[bool, str]:
    if not ref or ref.startswith("javascript:") or ref.startswith("#"):
        return True, "skip"
    ref_no_q = ref.split("#", 1)[0]
    parsed = urllib.parse.urlparse(ref_no_q)
    clean_for_local = urllib.parse.urlunparse(("", "", parsed.path, "", "", "")) if not parsed.scheme else ref_no_q
    if parsed.scheme in ("http", "https"):
        try:
            req = urllib.request.Request(ref_no_q, method="HEAD", headers={"User-Agent": "V21Audit/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return (200 <= r.status < 400), f"HTTP {r.status}"
        except Exception as e:
            try:
                with urllib.request.urlopen(ref_no_q, timeout=timeout) as r:
                    return (200 <= r.status < 400), f"HTTP {r.status}"
            except Exception as e2:
                return False, f"HTTP error: {e2}"
    if parsed.scheme in ("data", "mailto", "tel"):
        return True, "inline/skip"
    path = Path(urllib.parse.unquote(clean_for_local))
    if not path.is_absolute():
        candidates = [
            (base_file.parent / path).resolve(),
            (ROOT / path).resolve(),
        ]
        for cand in candidates:
            if cand.exists():
                return True, str(cand)
        path = candidates[0]
    return path.exists(), str(path)


def check_file(path: Path) -> Tuple[List[Check], Dict[str, object]]:
    html = read_text(path)
    text = strip_tags(html)
    lower_html = html.lower()
    checks: List[Check] = []

    meta = {
        "file": str(path),
        "bytes": path.stat().st_size,
        "text_chars": len(text),
        "tables": len(re.findall(r"<table\b", html, flags=re.I)),
        "svg": len(re.findall(r"<svg\b", html, flags=re.I)),
        "img": len(re.findall(r"<img\b", html, flags=re.I)),
        "iframe": len(re.findall(r"<iframe\b", html, flags=re.I)),
        "links": len(re.findall(r"<a\b", html, flags=re.I)),
    }

    # A. 模板来源硬检查
    prereq_missing = [str(p) for p in [SKILL, REGISTRY, STANDARD, FUSION_MASTER, *SAMPLES] if not p.exists()]
    checks.append(Check(
        "A00", "V21 注册表/标准/模板样本可读取", "FAIL" if prereq_missing else "PASS", "P0",
        "审核必须基于 family-plan-v21-final、template-registry、v21-final-exec-standard、融合母版和三个单项目样本。",
        prereq_missing or ["全部存在"]
    ))

    # B. 降级词/补强页伪装 final
    degrade_hits = count_terms(html + "\n" + text, DEGRADE_TERMS)
    checks.append(Check(
        "B01", "不得出现补强说明/附录/工作底稿/预览降级词", "FAIL" if degrade_hits else "PASS", "P0",
        "出现这些词时，高概率是过程页、整改页或补强页，不得冒充定稿页。若确为引用样本文本，需人工逐处说明。",
        [f"{k}: {v}" for k, v in degrade_hits.items()] or ["未发现"]
    ))

    # C. Hero/目录/计算器
    has_hero = "class=\"hero" in lower_html or "class='hero" in lower_html or re.search(r"<section[^>]+hero|<div[^>]+hero", lower_html) is not None
    has_toc = any(x in text for x in ["快速目录", "目录"]) and ("#ch" in lower_html or "toc" in lower_html)
    has_calc = "计算器" in text or "calculator" in lower_html
    missing_htc = [name for name, ok in [("Hero", has_hero), ("快速目录/目录", has_toc), ("计算器", has_calc)] if not ok]
    checks.append(Check(
        "C01", "必须有 Hero / 目录 / 计算器入口或计算器模块", "FAIL" if missing_htc else "PASS", "P0",
        "V21 定稿形态不是纯正文补强报告，必须保留商业级模板结构。",
        missing_htc or ["Hero、目录、计算器均检测到"]
    ))

    # D. 15章完整性
    missing_ch = []
    chapter_sections: Dict[int, str] = {}
    for n in range(1, 16):
        sec = extract_chapter(html, n)
        chapter_sections[n] = sec
        if not sec:
            missing_ch.append(str(n))
    checks.append(Check(
        "D01", "15章结构完整", "FAIL" if missing_ch else "PASS", "P0",
        "V21 单项目与融合页都必须具备15章结构；融合页必须为拆章重组，不是摘要。",
        ["缺失章节: " + ", ".join(missing_ch)] if missing_ch else ["1-15章均检测到"]
    ))

    # E. 图形硬门槛：第6章架构图、第9/13章身份路径图/流程图
    ch6 = chapter_sections.get(6, "")
    ch9 = chapter_sections.get(9, "")
    ch13 = chapter_sections.get(13, "")
    ch6_graph = has_any(ch6, DIAGRAM_WORDS) and has_any(ch6, CH6_ARCH_WORDS)
    ch9_graph = has_any(ch9, DIAGRAM_WORDS) and has_any(ch9, CH9_PATH_WORDS)
    ch13_graph = has_any(ch13, DIAGRAM_WORDS) and has_any(ch13, CH13_FLOW_WORDS)
    graph_missing = []
    if not ch6_graph:
        graph_missing.append("第6章缺少合格财富/税务/资金架构图")
    if not ch9_graph:
        graph_missing.append("第9章缺少身份路径图/流程图")
    if not ch13_graph:
        graph_missing.append("第13章缺少执行时间轴流程图/路径图")
    checks.append(Check(
        "E01", "第6章有架构图；第9/13章有身份路径图/流程图", "FAIL" if graph_missing else "PASS", "P0",
        "架构图必须能解释税务/资金/身份问题，不能用大段文字替代图形。",
        graph_missing or ["第6/9/13章图形关键字与章节语义均检测到"]
    ))

    # F. 第12/14/15章硬门槛
    hard_chapter_issues = []
    for n, words, min_len in [(12, CH12_WORDS, 900), (14, CH14_WORDS, 1200), (15, CH15_WORDS, 1000)]:
        sec = chapter_sections.get(n, "")
        score = sum(1 for w in words if w in strip_tags(sec) or w.lower() in sec.lower())
        table_count = len(re.findall(r"<table\b", sec, flags=re.I))
        if not sec:
            hard_chapter_issues.append(f"第{n}章缺失")
        elif len(strip_tags(sec)) < min_len:
            hard_chapter_issues.append(f"第{n}章过薄：文本{len(strip_tags(sec))}字 < {min_len}")
        elif score < max(4, len(words)//2):
            hard_chapter_issues.append(f"第{n}章关键词不足：{score}/{len(words)}")
        elif n == 12 and table_count < 1:
            hard_chapter_issues.append("第12章无预算表格")
    checks.append(Check(
        "F01", "第12/14/15章合格（预算、财税全文、风险与条款附件）", "FAIL" if hard_chapter_issues else "PASS", "P0",
        "第12、14、15章是定稿硬门槛，不能以补充说明/空泛风险提示替代。",
        hard_chapter_issues or ["第12/14/15章厚度、关键词、表格初筛通过"]
    ))

    # G. 0 待确认/0 !important
    unresolved_hits = count_terms(text, UNRESOLVED_TERMS)
    important_count = html.count("!important")
    issues = []
    if unresolved_hits:
        issues.extend([f"{k}: {v}" for k, v in unresolved_hits.items()])
    if important_count:
        issues.append(f"!important: {important_count}")
    checks.append(Check(
        "G01", "0 待确认类核心占位词 / 0 !important", "FAIL" if issues else "PASS", "P0",
        "定稿页不得残留核心待确认；全局 !important 容易污染 SVG/iframe/文字颜色。样本页虽有历史残留，交付页必须清零或人工逐条豁免。",
        issues or ["待确认类词与 !important 均为 0"]
    ))

    # H. 图片/SVG 出框/黑块风险
    visual_risks = []
    if re.search(r"overflow-x\s*:\s*visible|overflow\s*:\s*visible", lower_html):
        visual_risks.append("存在 overflow visible，需检查手机端出框")
    if re.search(r"width\s*:\s*(1[2-9]\d{2}|[2-9]\d{3})px", lower_html):
        visual_risks.append("存在大于等于1200px固定宽度，需包裹横向滚动/响应式")
    if re.search(r"<svg\b(?![^>]*(viewbox|viewBox))", html):
        visual_risks.append("存在无 viewBox 的 SVG，缩放风险")
    if re.search(r"svg\s+text\s*\{[^}]*fill\s*:\s*#?0{3,6}", lower_html) or re.search(r"svg\s*\*\s*\{[^}]*fill", lower_html):
        visual_risks.append("存在全局 SVG text/* fill 覆盖风险")
    if re.search(r"<(rect|path|div)[^>]+(?:fill|background(?:-color)?)\s*[:=][^>\n]*(#000|#000000|black|rgb\(0\s*,\s*0\s*,\s*0\))", lower_html):
        visual_risks.append("存在黑色块/黑底元素，需检查是否遮字")
    broken_imgs = []
    for src in attr_values(html, "img", "src"):
        ok, note = local_or_http_exists(src, path)
        if not ok:
            broken_imgs.append(f"{src} -> {note}")
    if broken_imgs:
        visual_risks.extend(["坏图: " + x for x in broken_imgs[:20]])
    checks.append(Check(
        "H01", "图片/SVG 不出框、无黑块遮字、无坏图风险", "WARN" if visual_risks else "PASS", "P1",
        "该项需要浏览器/手机截图最终确认；脚本只做静态风险扫描。",
        visual_risks or ["未发现静态视觉高风险"]
    ))

    # I. 完整单项目模块 iframe/链接路径不404
    iframe_srcs = attr_values(html, "iframe", "src")
    # fusion template may lazy-create iframe from onclick togglePlan(..., 'path')
    toggle_paths = []
    for m in re.finditer(r"togglePlan\s*\((.*?)\)", html, flags=re.I | re.S):
        args_text = m.group(1)
        quoted = re.findall(r"([\"'])(.*?\.html(?:\?[^\"']*)?)\1", args_text, flags=re.I | re.S)
        if quoted:
            toggle_paths.append(quoted[-1][1])
    link_paths = [h for h in attr_values(html, "a", "href") if ".html" in h and ("single" in h.lower() or "final-single" in h.lower())]
    module_paths = [p for p in dict.fromkeys(iframe_srcs + toggle_paths + link_paths) if "+" not in p and "'" not in p and '"' not in p]
    is_probably_fusion = ("完整单项目模块" in text or len(module_paths) >= 2 or "fusion" in path.name.lower() or meta["iframe"] > 0)
    module_errors = []
    if is_probably_fusion and not module_paths:
        module_errors.append("融合页未检测到 iframe/togglePlan/单独打开 的单项目独立页路径")
    for ref in module_paths:
        ok, note = local_or_http_exists(ref, path)
        if not ok:
            module_errors.append(f"{ref} -> {note}")
    checks.append(Check(
        "I01", "完整单项目模块 iframe/独立页路径不404", "FAIL" if module_errors else ("PASS" if module_paths else "REVIEW"), "P0",
        "融合页必须保留单项目独立完整页入口/预览/单独打开，禁止把多个完整 DOM 静态硬嵌入造成 CSS/SVG 污染。单项目页可标记 REVIEW。",
        module_errors or ([f"OK: {p}" for p in module_paths] if module_paths else ["未检测到融合模块路径；若为单项目页可人工通过"])
    ))

    # J. 融合页 DOM 硬嵌风险
    body_count = len(re.findall(r"<body\b", html, flags=re.I))
    html_count = len(re.findall(r"<html\b", html, flags=re.I))
    repeated_ids = []
    ids = attr_values(html, "[^>]+", "id") if False else re.findall(r"\bid\s*=\s*([\"'])(.*?)\1", html, flags=re.I | re.S)
    id_values = [v for _, v in ids]
    seen = set()
    for v in id_values:
        if v in seen and v not in repeated_ids:
            repeated_ids.append(v)
        seen.add(v)
    embed_issues = []
    if body_count > 1 or html_count > 1:
        embed_issues.append(f"发现多 html/body：html={html_count}, body={body_count}")
    if len(repeated_ids) > 10:
        embed_issues.append(f"重复 id 过多：{len(repeated_ids)} 个，可能硬嵌多个单项目DOM")
    checks.append(Check(
        "J01", "不得将多个完整单项目 DOM 静态硬嵌入融合页", "FAIL" if embed_issues else "PASS", "P0",
        "完整单项目模块应通过 iframe/独立预览隔离，融合正文只做15章拆章重组。",
        embed_issues or ["未发现多 body/html 或大量重复 id 风险"]
    ))

    return checks, meta


def render_markdown(results: List[Tuple[Path, List[Check], Dict[str, object]]]) -> str:
    lines = []
    lines.append("# V21 人工审核标准检查报告")
    lines.append("")
    lines.append("用途：防止“内容补强页 / 附录页 / 工作底稿 / 结构预览页”冒充 V21 定稿页。")
    lines.append("")
    lines.append("## 判定规则")
    lines.append("- 任一 **P0 FAIL**：不得标记或发布为 `final`，只能使用 `internal-review` / `candidate-review` / `structure-preview` / `draft`。")
    lines.append("- **P1 WARN**：必须人工截图或逐项说明后才可继续。")
    lines.append("- 脚本初筛通过不等于人工通过；最终仍需按模板样本逐章阅读。")
    lines.append("")
    lines.append("## 标准来源")
    lines.append(f"- Skill: `{SKILL}`")
    lines.append(f"- Registry: `{REGISTRY}`")
    lines.append(f"- Standard: `{STANDARD}`")
    lines.append(f"- Fusion master: `{FUSION_MASTER}`")
    lines.append("- Single samples:")
    for p in SAMPLES:
        lines.append(f"  - `{p}`")
    lines.append("")

    for path, checks, meta in results:
        p0_fail = [c for c in checks if c.severity == "P0" and c.status == "FAIL"]
        warn = [c for c in checks if c.status == "WARN"]
        final_status = "BLOCKED — 不得作为定稿页" if p0_fail else ("REVIEW — 需人工确认警告项" if warn else "PASS — 可进入人工终审")
        lines.append(f"## 文件：`{path}`")
        lines.append("")
        lines.append(f"**结论：{final_status}**")
        lines.append("")
        lines.append("### 基础统计")
        lines.append("| 指标 | 值 |")
        lines.append("|---|---:|")
        for k, v in meta.items():
            if k != "file":
                lines.append(f"| {k} | {v} |")
        lines.append("")
        lines.append("### 检查项")
        lines.append("| 编号 | 严重度 | 状态 | 检查项 | 证据/处理要求 |")
        lines.append("|---|---|---|---|---|")
        for c in checks:
            ev = "<br>".join(str(x).replace("|", "\\|") for x in c.evidence[:12])
            if len(c.evidence) > 12:
                ev += f"<br>……另有 {len(c.evidence)-12} 项"
            lines.append(f"| {c.code} | {c.severity} | **{c.status}** | {c.title} | {ev} |")
        lines.append("")
        lines.append("### 人工复核签字区")
        lines.append("- [ ] 已确认不是补强说明/附录/工作底稿/过程页。")
        lines.append("- [ ] 已对照融合母版：Hero、质量指标、快速目录、完整单项目模块、15章拆章重组均存在。")
        lines.append("- [ ] 已对照三个单项目样本：单项目页厚度接近样本，不是摘要页。")
        lines.append("- [ ] 第6章架构图能说明主体、资金流、利润流、税务居民、DTA/预提税、CFC/CRS/FATCA/FBAR、37号文/ODI/FDI、禁止动作。")
        lines.append("- [ ] 第9章身份路径图、第13章执行流程图/时间轴可读且与正文一致。")
        lines.append("- [ ] 第12章预算明细、第14章财税全文、第15章风险声明与条款级法案附件逐章合格。")
        lines.append("- [ ] 页面内 `待确认` 类占位和 `!important` 已清零，或有书面逐项豁免。")
        lines.append("- [ ] 手机端/浏览器截图确认图片、SVG、表格不出框、无黑块遮字、无低对比。")
        lines.append("- [ ] 融合页完整单项目模块的 iframe/展开方案/单独打开路径均 200 或本地存在。")
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Audit V21 final human standard for single-project and fusion HTML pages.")
    ap.add_argument("paths", nargs="+", help="HTML files to audit")
    ap.add_argument("--md-report", default="", help="write markdown report to this path")
    ap.add_argument("--json", action="store_true", help="also print JSON to stdout")
    args = ap.parse_args(argv)

    targets = [Path(p).expanduser().resolve() for p in args.paths]
    missing = [str(p) for p in targets if not p.exists()]
    if missing:
        print("Missing input files:\n" + "\n".join(missing), file=sys.stderr)
        return 2

    results = []
    json_out = []
    exit_code = 0
    for p in targets:
        checks, meta = check_file(p)
        results.append((p, checks, meta))
        if any(c.severity == "P0" and c.status == "FAIL" for c in checks):
            exit_code = 1
        json_out.append({"file": str(p), "meta": meta, "checks": [asdict(c) for c in checks]})

    md = render_markdown(results)
    if args.md_report:
        out = Path(args.md_report).expanduser()
        if not out.is_absolute():
            out = (Path.cwd() / out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"Markdown report written: {out}")
    elif not args.json:
        print(md)

    if args.json:
        print(json.dumps(json_out, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
