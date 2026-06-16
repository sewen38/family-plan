#!/usr/bin/env python3
"""Cloud runner for family-plan questionnaire issues.

Runs fully in GitHub Actions: scans pending questionnaire issues, generates final-standard
mobile-friendly diagnosis drafts via OpenAI-compatible API, comments result, labels diagnosed.

Required repository secrets:
- OPENAI_API_KEY
Optional:
- OPENAI_BASE_URL (default https://api.openai.com/v1)
- OPENAI_MODEL (default deepseek/deepseek-v4-flash)
"""
from __future__ import annotations
import json, os, re, sys, time, urllib.error, urllib.request
from typing import Any, Dict, List, Optional

REPO = os.environ.get("REPO", "sewen38/family-plan")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or "deepseek/deepseek-v4-flash"
MODE = os.environ.get("INPUT_MODE") or "diagnosis"
INPUT_ISSUE = os.environ.get("INPUT_ISSUE_NUMBER") or os.environ.get("EVENT_ISSUE_NUMBER") or ""

FINAL_STANDARD = """
你是跨境家庭全球规划顾问。必须按最终定稿版标准输出，禁止旧9节/旧8段/docx默认/摘要型输出。

诊断草案必须是手机端可读 Markdown（GitHub Issue 评论），结构如下：
1. 封面/摘要 + 风险雷达
2. 7步法生成路径
3. 客户基础信息速览（每项写诊断含义）
4. 待解决问题分级（编号、问题、P0-P3、具体说明、立即动作）
5. 根本判断（表面问题 vs 真实问题 + 正确处理顺序）
6. 第三国护照使用边界
7. 重要专题深度分析
8. 多方案框架设计
9. 方案综合对比与推荐
10. 财税解决方案维度
11. 立即行动计划 + 风险声明
12. 附件：法案与政策依据

重要专题深度分析必须按五段式逐条展开：当前风险 → 为什么会出事 → 需要核验材料 → 解决方案 → 最终交付物。

执行策划案相关规则：必须按 V21 最终定稿模板、release gate、完整单项目模块区、15章拆章重组；先看整体结构，再看每个单独嵌入的单国家单项目质量；单项目质量永远第一重要；图片/架构图必须根据实际客户情况有效解决问题。

输出前自检人工4重审核，并在末尾写“人工4重审核结果”：整体结构、专题/模块质量、专业有效性、视觉与交付。不得输出内部prompt、不得说自己是AI、不得出现TODO/占位符/乱码。
""".strip()


def gh(method: str, path: str, data: Optional[dict] = None) -> Any:
    if not GH_TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{REPO}{path}"
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {GH_TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub API {method} {path} failed: {e.code} {detail}")


def labels(issue: dict) -> List[str]:
    return [x.get("name", "") for x in issue.get("labels", [])]


def list_targets() -> List[dict]:
    if INPUT_ISSUE:
        issue = gh("GET", f"/issues/{INPUT_ISSUE}")
        return [issue]
    issues = gh("GET", "/issues?state=open&labels=pending&per_page=20")
    return [i for i in issues if "pull_request" not in i]


def add_labels(num: int, names: List[str]) -> None:
    gh("POST", f"/issues/{num}/labels", {"labels": names})


def set_labels(num: int, names: List[str]) -> None:
    gh("PATCH", f"/issues/{num}", {"labels": names})


def comment(num: int, body: str) -> None:
    gh("POST", f"/issues/{num}/comments", {"body": body})


def close_issue(num: int) -> None:
    gh("PATCH", f"/issues/{num}", {"state": "closed"})


def extract_questionnaire(body: str) -> str:
    # Prefer fenced questionnaire if present; else entire body.
    blocks = re.findall(r"```(?:json|text|markdown|md)?\s*([\s\S]*?)```", body or "")
    if blocks:
        return max(blocks, key=len).strip()
    return (body or "").strip()


def load_knowledge_excerpt(q: str) -> str:
    # Keep deterministic and repo-local; cloud runner does not rely on local machine.
    files = [
        "references/美加移民政策对比研究-2026.md",
        "references/immigration-policies-2025-2026.md",
        "references/immigration-research-uk-au-nz-2025.md",
        "references/europe-immigration-policies-2026.md",
        "references/immigration-research-tr-vu-dm-ge-2026.md",
        "references/immigration-research-uae-china-2025.md",
        "references/final-output-standards/v21-final-exec-standard.md",
    ]
    text = []
    qlow = q.lower()
    for fp in files:
        p = os.path.join(os.getcwd(), fp)
        if os.path.exists(p):
            data = open(p, encoding="utf-8", errors="ignore").read()
            # Include all small files; otherwise first 6000 chars to control token size.
            text.append(f"\n## {fp}\n" + data[:6000])
    return "\n".join(text)[:30000]


def call_model(prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY repository secret. Configure GitHub repo secret OPENAI_API_KEY before enabling cloud generation.")
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": FINAL_STANDARD},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(f"{OPENAI_BASE_URL}/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Model API failed: {e.code} {detail[:1000]}")


def validate_output(text: str) -> List[str]:
    errors = []
    required = ["风险雷达", "根本判断", "第三国护照", "重要专题", "当前风险", "为什么会出事", "需要核验材料", "解决方案", "最终交付物", "方案", "立即行动", "风险声明", "法案", "人工4重审核"]
    for r in required:
        if r not in text:
            errors.append(f"missing required phrase: {r}")
    forbidden = ["TODO", "待生成", "Lorem", "乱码", "�", "作为AI", "prompt"]
    for f in forbidden:
        if f in text:
            errors.append(f"forbidden phrase: {f}")
    if len(text) < 6000:
        errors.append("output too short for final diagnosis standard (<6000 chars)")
    return errors


def process(issue: dict) -> None:
    num = issue["number"]
    labs = labels(issue)
    if "diagnosed" in labs:
        print(f"Issue #{num} already diagnosed, skip")
        return
    if "in-progress" in labs:
        print(f"Issue #{num} already in-progress, skip")
        return
    add_labels(num, ["in-progress"])
    q = extract_questionnaire(issue.get("body", ""))
    knowledge = load_knowledge_excerpt(q)
    prompt = f"""
请根据以下问卷生成最终定稿版《跨境家庭全球规划诊断草案》。

要求：严格遵守系统里的最终标准；客户视角；手机端可读 Markdown；底部附方案 A/B/C/D 选择项和结构化 JSON，供下一阶段识别国家/项目。

【问卷内容】
{q}

【知识库摘录】
{knowledge}
""".strip()
    try:
        result = call_model(prompt)
        errors = validate_output(result)
        if errors:
            body = "## 云端生成已阻塞：未通过人工4重审核前置检查\n\n" + "\n".join(f"- {e}" for e in errors) + "\n\n请人工复核后重新运行 workflow。"
            comment(num, body)
            # Keep pending, remove in-progress
            set_labels(num, [x for x in labs if x != "in-progress"] + ["pending", "cloud-blocked"])
            return
        comment(num, result + "\n\n---\n云端执行器：GitHub Actions family-plan-cloud-runner")
        set_labels(num, sorted(set([x for x in labs if x not in ("pending", "in-progress", "cloud-blocked")] + ["questionnaire", "diagnosed"])))
        close_issue(num)
        print(f"Issue #{num} diagnosed and closed")
    except Exception as e:
        comment(num, f"## 云端执行器未完成\n\n原因：`{str(e)}`\n\n如果是缺少 `OPENAI_API_KEY`，请在 GitHub 仓库 Settings → Secrets and variables → Actions 中配置后重新运行。")
        set_labels(num, sorted(set([x for x in labs if x != "in-progress"] + ["pending", "cloud-blocked"])))
        raise


def main() -> int:
    targets = list_targets()
    if not targets:
        print("No pending questionnaire issues")
        return 0
    for issue in targets:
        process(issue)
        time.sleep(1)
    return 0

if __name__ == "__main__":
    sys.exit(main())
