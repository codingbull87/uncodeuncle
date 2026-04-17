#!/usr/bin/env python3
"""
Lint chart fragments for minimum visual quality.

Usage:
  python3 scripts/lint_fragments.py <report_dir>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PLACEHOLDER_ANCHOR = re.compile(r"\b[A-Z]{2,}_[A-Z0-9_]{2,}\b")
GENERIC_TITLE = re.compile(r"(分析|对比图|趋势图|图表|示意图|分类图|框架图)$")
INTERNAL_SOURCE = re.compile(
    r"(报告正文整理|报告执行摘要整理|正文整理|执行摘要整理|报告内(?:部)?整理|基于报告(?:正文|执行摘要)?整理)",
    flags=re.IGNORECASE,
)
TITLE_BLOCK = re.compile(
    r'<(?:div|h[1-6])[^>]*class="[^"]*(?:chart-title|figure-title)[^"]*"[^>]*>(.*?)</(?:div|h[1-6])>',
    flags=re.IGNORECASE | re.DOTALL,
)
SOURCE_BLOCK = re.compile(
    r'<div[^>]*class="[^"]*(?:chart-src|figure-src|component-src)[^"]*"[^>]*>(.*?)</div>',
    flags=re.IGNORECASE | re.DOTALL,
)
HEIGHT_PX = re.compile(r"height\s*:\s*(\d{2,4})px", flags=re.IGNORECASE)


def strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", text).strip()


def has_renderable_fragment(fragment: str) -> bool:
    return bool(
        re.search(
            r"echarts\.init|<svg\b|<table\b|kpi-val|consulting-|class=\"(?:scorecard|driver-tree|range-band|timeline|matrix|heatmap)",
            fragment,
            re.IGNORECASE,
        )
    )


def lint_fragment(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")

    if PLACEHOLDER_ANCHOR.search(text):
        errors.append(f"{path.name}: 包含占位锚点文本（如 CH2_SECTION_2_2）")

    if not has_renderable_fragment(text):
        errors.append(f"{path.name}: 片段疑似空壳，未检测到可渲染图/表/结构组件")

    titles = [strip_tags(item) for item in TITLE_BLOCK.findall(text) if strip_tags(item)]
    if not titles:
        errors.append(f"{path.name}: 缺少结论标题（.chart-title / .figure-title）")
    else:
        first = titles[0]
        if len(first) < 10 or GENERIC_TITLE.search(first):
            warnings.append(f"{path.name}: 标题结论性不足（{first}）")

    for block in SOURCE_BLOCK.findall(text):
        source_text = strip_tags(block)
        if source_text and INTERNAL_SOURCE.search(source_text):
            errors.append(f"{path.name}: 来源文案无信息量（{source_text}）")

    heights = [int(value) for value in HEIGHT_PX.findall(text)]
    for value in heights:
        if value > 560:
            errors.append(f"{path.name}: 图表高度 {value}px 超过上限 560px")
        elif value < 140:
            warnings.append(f"{path.name}: 图表高度 {value}px 过低，可能影响可读性")

    if re.search(r"<!DOCTYPE|<html\b|<head\b|<body\b", text, flags=re.IGNORECASE):
        errors.append(f"{path.name}: 片段包含完整 HTML 页面标签")

    return errors, warnings


def lint_report_dir(report_dir: Path) -> tuple[list[str], list[str], int]:
    fragments_dir = report_dir / "chart-fragments"
    if not fragments_dir.exists():
        return (["缺少 chart-fragments 目录"], [], 0)

    files = sorted(path for path in fragments_dir.glob("C*.html") if path.is_file())
    if not files:
        return (["未找到 C{id}.html 片段"], [], 0)

    errors: list[str] = []
    warnings: list[str] = []
    for path in files:
        file_errors, file_warnings = lint_fragment(path)
        errors.extend(file_errors)
        warnings.extend(file_warnings)
    return errors, warnings, len(files)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lint report-illustrator fragments")
    parser.add_argument("report_dir", help="Report workspace directory")
    args = parser.parse_args(argv[1:])

    report_dir = Path(args.report_dir).expanduser().resolve()
    if not report_dir.exists() or not report_dir.is_dir():
        print(f"[ERROR] 报告目录不存在：{report_dir}")
        return 1

    errors, warnings, count = lint_report_dir(report_dir)
    print(f"[LINT] fragments={count} report_dir={report_dir}")
    for item in warnings:
        print(f"[WARN] {item}")
    for item in errors:
        print(f"[ERROR] {item}")

    if errors:
        print("[FAIL] 片段质量检查未通过")
        return 1
    print("[PASS] 片段质量检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
