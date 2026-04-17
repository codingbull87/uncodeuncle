#!/usr/bin/env python3
"""
QA print-layout quality from actual PDF page placement.

Usage:
  python3 scripts/qa_pdf.py <html_path> [qa_json_path]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from layout_probe import build_probe_payload


WARNING_BLANK_RATIO = 0.38
ERROR_BLANK_RATIO = 0.68
LAST_PAGE_WARNING_RATIO = 0.55


def evaluate(result: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    pages = result.get("pages", [])
    if not pages:
        errors.append("未检测到任何页面内容")
        return errors, warnings

    last_page = max(int(page.get("page", 0)) for page in pages)
    for page in pages:
        index = int(page.get("page", 0))
        blank_ratio = float(page.get("blankRatio", 0))
        blocks = int(page.get("blockCount", 0))
        visual_blocks = int(page.get("visualBlocks", 0))
        if index == last_page:
            if blank_ratio > LAST_PAGE_WARNING_RATIO and blocks <= 4:
                warnings.append(f"第 {index} 页内容偏少，页底空白约 {blank_ratio:.0%}")
            continue
        if blank_ratio > ERROR_BLANK_RATIO:
            errors.append(f"第 {index} 页页底空白过大，约 {blank_ratio:.0%}")
        elif blank_ratio > WARNING_BLANK_RATIO:
            warnings.append(f"第 {index} 页页底空白偏大，约 {blank_ratio:.0%}")
        if visual_blocks == 1 and blocks <= 3 and blank_ratio > 0.35:
            warnings.append(f"第 {index} 页疑似单视觉块低密度页")

    missing_markers = result.get("missingMarkers", []) or []
    if missing_markers:
        warnings.append(f"有 {len(missing_markers)} 个 block 未能完成 PDF marker 映射")
    return errors, warnings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="QA PDF print layout from assembled HTML")
    parser.add_argument("html_path", help="Assembled report HTML path")
    parser.add_argument("qa_json_path", nargs="?", help="Optional QA JSON output path")
    args = parser.parse_args(argv[1:])

    html_path = Path(args.html_path).expanduser().resolve()
    if not html_path.exists():
        print(f"[ERROR] 找不到 HTML 文件：{html_path}")
        return 1

    result = build_probe_payload(html_path)
    errors, warnings = evaluate(result)
    result["errors"] = errors
    result["warnings"] = warnings

    qa_json_path = Path(args.qa_json_path).expanduser().resolve() if args.qa_json_path else html_path.with_name("PDF_QA.json")
    qa_json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[PDF_QA] html={html_path}")
    print(f"[PDF_QA] output={qa_json_path}")
    for item in warnings:
        print(f"[WARN] {item}")
    for item in errors:
        print(f"[ERROR] {item}")
    if errors:
        print("[FAIL] PDF QA 未通过")
        return 1
    print("[PASS] PDF QA 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
