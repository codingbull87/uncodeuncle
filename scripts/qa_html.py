#!/usr/bin/env python3
"""
QA assembled report HTML for structural layout regressions.

Usage:
  python3 scripts/qa_html.py <report_dir> [html_path]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from assemble_engine import normalize_chart_id, normalize_layout, parse_recommendations
from lint_fragments import ECHARTS_CSS_VAR_STRING, classes_in


DOC_ALLOWED_CLASSES = {
    "page",
    "report-cover",
    "report-meta",
    "report-meta-freeform",
    "report-meta-key",
    "report-meta-value",
    "visual-block",
    "visual-full",
    "visual-half",
    "visual-third",
    "visual-quarter",
    "visual-compact",
    "visual-size-small",
    "visual-size-medium",
    "visual-size-large",
    "visual-size-compact",
    "visual-block-nested",
    "visual-row",
    "visual-row-half",
    "visual-row-third",
    "visual-row-quarter",
    "visual-row-equal",
    "visual-row-title",
    "chapter-page-break",
    "compact-print",
    "page-fit-compact",
    "pdf-export-mode",
    "charts-ready",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def find_html(report_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.exists() else None
    candidates = sorted(report_dir.glob("*_illustrated.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def expected_group_counts(recommendations: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rec in recommendations:
        group = str(rec.get("group", "")).strip()
        layout = normalize_layout(rec.get("layout"))
        if group and layout in {"half", "third", "quarter", "compact"}:
            counts[group] = counts.get(group, 0) + 1
    return {group: count for group, count in counts.items() if count >= 2}


def actual_group_counts(html: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for group in re.findall(r'<div\s+[^>]*class=["\'][^"\']*\bvisual-row\b[^"\']*["\'][^>]*data-group=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
        counts[group] = counts.get(group, 0) + 1
    return counts


def duplicate_chart_ids(html: str) -> list[str]:
    ids = re.findall(r'\bid=["\'](chart-C\d+)["\']', html, flags=re.IGNORECASE)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in ids:
        normalized = item.upper()
        if normalized in seen:
            duplicates.add(item)
        seen.add(normalized)
    return sorted(duplicates)


def visual_ids(html: str) -> set[str]:
    return {normalize_chart_id(item) for item in re.findall(r'data-chart-id=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)}


def run_qa(report_dir: Path, html_path: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    html = read_text(html_path)
    recommendations = parse_recommendations(str(report_dir))

    if not re.search(r'<section\b[^>]*class=["\'][^"\']*\breport-cover\b', html, flags=re.IGNORECASE):
        warnings.append("未检测到 .report-cover")
    cover_match = re.search(r'<section\b[^>]*class=["\'][^"\']*\breport-cover\b[^>]*>(.*?)</section>', html, flags=re.IGNORECASE | re.DOTALL)
    if cover_match and re.search(r'<div\b[^>]*class=["\'][^"\']*\bvisual-block\b', cover_match.group(1), flags=re.IGNORECASE):
        errors.append(".report-cover 内部包含 visual-block")
    if re.search(r"<p>\s*<(?:div|script|table|svg)", html, flags=re.IGNORECASE):
        errors.append("存在 <p> 包裹块级元素的非法嵌套")
    if re.search(r"html2canvas|jspdf|downloadChart", html, flags=re.IGNORECASE):
        errors.append("存在截图式 PDF 或下载残留逻辑")

    duplicates = duplicate_chart_ids(html)
    if duplicates:
        errors.append("存在重复 chart DOM id：" + ", ".join(duplicates))

    expected_ids = {normalize_chart_id(rec.get("id")) for rec in recommendations if rec.get("id")}
    missing_ids = sorted(expected_ids - visual_ids(html))
    if missing_ids:
        errors.append("recommendation 未注入到 HTML：" + ", ".join(missing_ids))

    expected_groups = expected_group_counts(recommendations)
    actual_groups = actual_group_counts(html)
    for group, count in expected_groups.items():
        if actual_groups.get(group, 0) == 0:
            errors.append(f"group '{group}' 有 {count} 个并排候选，但最终未生成 visual-row")

    if ECHARTS_CSS_VAR_STRING.search(html):
        errors.append("最终 HTML 中 ECharts option 仍直接传入 CSS 变量字符串")

    unknown_classes = sorted(cls for cls in classes_in(html) if cls not in DOC_ALLOWED_CLASSES)
    # Fragment classes are validated by lint_fragments; here only catch known generator drift classes.
    bad_generator_classes = [cls for cls in unknown_classes if cls in {"tree-level", "tree-node", "high-impact", "medium-impact", "low-impact", "high-probability", "medium-probability", "low-probability"}]
    if bad_generator_classes:
        errors.append("最终 HTML 含组件协议外关键类：" + ", ".join(sorted(set(bad_generator_classes))))

    visual_blocks = len(re.findall(r'class=["\'][^"\']*\bvisual-block\b', html, flags=re.IGNORECASE))
    visual_rows = len(re.findall(r'class=["\'][^"\']*\bvisual-row\b', html, flags=re.IGNORECASE))
    details = {
        "html_path": str(html_path),
        "recommendations": len(recommendations),
        "visual_blocks": visual_blocks,
        "visual_rows": visual_rows,
        "expected_groups": expected_groups,
        "actual_groups": actual_groups,
        "errors": errors,
        "warnings": warnings
    }
    return errors, warnings, details


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="QA assembled report HTML")
    parser.add_argument("report_dir", help="Report workspace directory")
    parser.add_argument("html_path", nargs="?", help="Optional assembled HTML path")
    parser.add_argument("--json", action="store_true", help="Print JSON details")
    args = parser.parse_args(argv[1:])

    report_dir = Path(args.report_dir).expanduser().resolve()
    html_path = find_html(report_dir, args.html_path)
    if not html_path:
        print(f"[ERROR] 未找到可 QA 的 *_illustrated.html：{report_dir}")
        return 1

    errors, warnings, details = run_qa(report_dir, html_path)
    if args.json:
        print(json.dumps(details, ensure_ascii=False, indent=2))
    else:
        print(f"[HTML_QA] html={html_path}")
        for item in warnings:
            print(f"[WARN] {item}")
        for item in errors:
            print(f"[ERROR] {item}")

    if errors:
        print("[FAIL] HTML QA 未通过")
        return 1
    print("[PASS] HTML QA 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
