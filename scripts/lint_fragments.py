#!/usr/bin/env python3
"""
Lint chart fragments for minimum visual quality.

Usage:
  python3 scripts/lint_fragments.py <report_dir>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


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
CLASS_ATTR = re.compile(r'class=["\']([^"\']+)["\']', flags=re.IGNORECASE)
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
ECHARTS_CSS_VAR_STRING = re.compile(r"['\"]var\(--[^)]+\)['\"]")
ECHARTS_INIT = re.compile(r"echarts\.init\s*\(", flags=re.IGNORECASE)
SVG_RENDERER = re.compile(r"renderer\s*:\s*['\"]svg['\"]", flags=re.IGNORECASE)
CHART_ID = re.compile(r'id=["\'](chart-C\d+)["\']', flags=re.IGNORECASE)
STYLE_BLOCK = re.compile(r"<style\b[^>]*>.*?</style>", flags=re.IGNORECASE | re.DOTALL)
HOST_SELECTOR = re.compile(r":host\b", flags=re.IGNORECASE)
ROOT_SELECTOR = re.compile(r":root\s*\{", flags=re.IGNORECASE)
FIXED_HEIGHT_GRID_INLINE = re.compile(
    r'class=["\'][^"\']*\b(?:kpi-block|kpi-strip|insight-grid|framework-grid|scorecard-grid|swimlane-track)\b[^"\']*["\'][^>]*style=["\'][^"\']*height\s*:',
    flags=re.IGNORECASE,
)

ALLOWED_STRUCTURAL_CLASSES = {
    "chart-container",
    "chart-header",
    "chart-title",
    "chart-kicker",
    "chart-annotation",
    "chart-src",
    "consulting-figure",
    "figure-header",
    "figure-title",
    "figure-kicker",
    "figure-note",
    "figure-src",
    "component-src",
    "kpi-block",
    "kpi-strip",
    "kpi-card",
    "kpi-label",
    "kpi-val",
    "kpi-unit",
    "kpi-sub",
    "green",
    "red",
    "amber",
    "blue",
    "insight-grid",
    "insight-card",
    "insight-card-title",
    "insight-card-body",
    "framework-grid",
    "framework-card",
    "framework-card-title",
    "framework-card-body",
    "scorecard-grid",
    "scorecard-item",
    "scorecard-score",
    "scorecard-title",
    "scorecard-body",
    "matrix-2x2",
    "matrix-cell",
    "matrix-cell-title",
    "matrix-cell-body",
    "emphasis",
    "risk-matrix",
    "risk-cell",
    "risk-title",
    "risk-body",
    "heatmap-grid",
    "heatmap-cell",
    "heatmap-title",
    "heatmap-body",
    "high",
    "mid",
    "low",
    "matrix",
    "timeline",
    "timeline-item",
    "timeline-date",
    "timeline-title",
    "timeline-body",
    "value-chain",
    "process-chain",
    "chain-step",
    "chain-step-title",
    "chain-step-body",
    "driver-tree",
    "driver-root",
    "driver-branches",
    "driver-branch",
    "driver-title",
    "driver-body",
    "range-band",
    "football-field",
    "range-row",
    "range-label",
    "range-track",
    "range-fill",
    "range-marker",
    "range-value",
    "swimlane-roadmap",
    "swimlane",
    "swimlane-label",
    "swimlane-track",
    "swimlane-milestone",
    "decision-tree",
    "decision-node",
    "decision-title",
    "decision-body",
    "primary",
    "lollipop-list",
    "lollipop-row",
    "lollipop-label",
    "lollipop-track",
    "lollipop-dot",
    "lollipop-value",
}


def strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", text).strip()


def skill_dir_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def load_contracts() -> dict[str, Any]:
    path = skill_dir_from_script() / "references" / "component-contracts.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"contracts": {}, "shared": {}}
    return payload if isinstance(payload, dict) else {"contracts": {}, "shared": {}}


def load_recommendation_types(report_dir: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    path = report_dir / "RECOMMENDATIONS.normalized.json"
    if not path.exists():
        path = report_dir / "RECOMMENDATIONS.json"
    if not path.exists():
        return mapping
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return mapping
    if not isinstance(payload, list):
        return mapping
    for item in payload:
        if not isinstance(item, dict):
            continue
        raw_id = str(item.get("id", "")).strip()
        if not raw_id:
            continue
        match = re.search(r"\d+", raw_id)
        chart_id = "C" + match.group(0) if match else raw_id
        mapping[chart_id] = str(item.get("type", "")).strip().lower()
    return mapping


def classes_in(text: str) -> set[str]:
    result: set[str] = set()
    for attr in CLASS_ATTR.findall(text):
        result.update(cls for cls in re.split(r"\s+", attr.strip()) if cls)
    return result


def strip_style_blocks(text: str) -> str:
    return STYLE_BLOCK.sub("", text)


def has_required_palette_vars(text: str) -> bool:
    required = (
        "--color-primary",
        "--color-secondary",
        "--color-positive",
        "--color-negative",
        "--color-accent",
        "--color-border",
        "--color-text",
    )
    return all(token in text for token in required)


def count_class(text: str, class_name: str) -> int:
    count = 0
    for attr in CLASS_ATTR.findall(text):
        if class_name in re.split(r"\s+", attr.strip()):
            count += 1
    return count


def lint_contract(path: Path, text: str, visual_type: str, contracts_payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not visual_type:
        return errors, warnings

    contracts = contracts_payload.get("contracts", {})
    contract = contracts.get(visual_type)
    if not isinstance(contract, dict):
        warnings.append(f"{path.name}: 未知图表类型，无法执行组件协议检查（{visual_type}）")
        return errors, warnings

    present = classes_in(text)
    required_any = contract.get("required_any", [])
    if required_any and not any(cls in present for cls in required_any):
        errors.append(f"{path.name}: {visual_type} 缺少必需根/布局类之一：{', '.join(required_any)}")

    for cls in contract.get("required_descendants", []):
        if cls not in present:
            errors.append(f"{path.name}: {visual_type} 缺少必需子类：{cls}")

    for pattern in contract.get("required_patterns", []):
        if pattern not in text:
            errors.append(f"{path.name}: {visual_type} 缺少必需片段：{pattern}")

    exact_items = contract.get("exact_items")
    min_items = contract.get("min_items")
    max_items = contract.get("max_items")
    item_class = None
    for candidate in (
        "kpi-card",
        "risk-cell",
        "matrix-cell",
        "timeline-item",
        "chain-step",
        "range-row",
        "heatmap-cell",
        "scorecard-item",
        "decision-node",
        "insight-card",
    ):
        if candidate in contract.get("required_descendants", []):
            item_class = candidate
            break
    if item_class:
        item_count = count_class(text, item_class)
        if exact_items is not None and item_count != int(exact_items):
            errors.append(f"{path.name}: {visual_type} 需要 {exact_items} 个 {item_class}，实际 {item_count}")
        if min_items is not None and item_count < int(min_items):
            errors.append(f"{path.name}: {visual_type} 的 {item_class} 数量过少：{item_count} < {min_items}")
        if max_items is not None and item_count > int(max_items):
            warnings.append(f"{path.name}: {visual_type} 的 {item_class} 数量偏多：{item_count} > {max_items}")

    for cls in contract.get("forbidden_cell_modifiers", []):
        if cls in present:
            errors.append(f"{path.name}: {visual_type} 使用了未受样式支持的语义类：{cls}")

    for cls in contracts_payload.get("shared", {}).get("forbidden_classes", []):
        if cls in present:
            errors.append(f"{path.name}: 使用了组件协议禁止的类：{cls}")

    return errors, warnings


def has_renderable_fragment(fragment: str) -> bool:
    return bool(
        re.search(
            r"echarts\.init|<svg\b|<table\b|kpi-val|consulting-|class=\"(?:scorecard|driver-tree|range-band|timeline|matrix|heatmap)",
            fragment,
            re.IGNORECASE,
        )
    )


def lint_fragment(path: Path, visual_type: str = "", contracts_payload: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    contracts_payload = contracts_payload or load_contracts()

    if PLACEHOLDER_ANCHOR.search(text):
        errors.append(f"{path.name}: 包含占位锚点文本（如 CH2_SECTION_2_2）")

    if not has_renderable_fragment(text):
        errors.append(f"{path.name}: 片段疑似空壳，未检测到可渲染图/表/结构组件")

    present_classes = classes_in(text)
    unknown = sorted(cls for cls in present_classes if cls not in ALLOWED_STRUCTURAL_CLASSES and not cls.startswith("chart-C"))
    if unknown:
        errors.append(f"{path.name}: 包含未登记组件类：{', '.join(unknown)}")

    if ECHARTS_INIT.search(text):
        if not SVG_RENDERER.search(text):
            errors.append(f"{path.name}: ECharts 片段必须显式使用 renderer: 'svg'")
        if ECHARTS_CSS_VAR_STRING.search(text):
            errors.append(f"{path.name}: ECharts option 不能直接传入 CSS 变量字符串，需用 getComputedStyle 读取实际色值")
        if HOST_SELECTOR.search(text):
            errors.append(f"{path.name}: ECharts 片段禁止使用 :host 定义调色变量；当前产物不是 Shadow DOM，易导致 getComputedStyle(document.documentElement) 取空值")
        if not ROOT_SELECTOR.search(text):
            errors.append(f"{path.name}: ECharts 片段缺少 :root 调色变量定义；片段必须自包含色板，避免变量来源不明确")
        elif not has_required_palette_vars(text):
            errors.append(f"{path.name}: ECharts 片段的 :root 调色变量不完整，至少需包含 primary/secondary/positive/negative/accent/border/text")

    non_style_text = strip_style_blocks(text)
    hardcoded_hex = sorted(set(HEX_COLOR.findall(non_style_text)))
    if hardcoded_hex:
        errors.append(f"{path.name}: 片段正文/脚本含硬编码色值：{', '.join(hardcoded_hex)}")

    if re.search(r'class=["\'][^"\']*\bconsulting-figure\b[^"\']*\b(?:risk-matrix|matrix-2x2|heatmap-grid|decision-tree|driver-tree|range-band|process-chain|value-chain)\b', text, flags=re.IGNORECASE):
        errors.append(f"{path.name}: 外层 .consulting-figure 不应同时承担内部布局类")

    if "consulting-figure" in present_classes and "figure-title" in present_classes and "figure-header" not in present_classes:
        errors.append(f"{path.name}: .consulting-figure 缺少 .figure-header，易导致并排标题基线错位")
    if "chart-container" in present_classes and "chart-title" in present_classes and "chart-header" not in present_classes:
        errors.append(f"{path.name}: .chart-container 缺少 .chart-header，易导致并排标题基线错位")
    if FIXED_HEIGHT_GRID_INLINE.search(text):
        errors.append(f"{path.name}: 小组件网格存在内联 height 固定，易导致文字裁切")
    if re.search(r"height\s*:\s*100%\s*;?", text, flags=re.IGNORECASE):
        warnings.append(f"{path.name}: 检测到 height:100%，可能引发布局拉伸或溢出")

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

    contract_errors, contract_warnings = lint_contract(path, text, visual_type, contracts_payload)
    errors.extend(contract_errors)
    warnings.extend(contract_warnings)

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
    rec_types = load_recommendation_types(report_dir)
    contracts_payload = load_contracts()
    for path in files:
        chart_id = path.stem.upper()
        file_errors, file_warnings = lint_fragment(path, visual_type=rec_types.get(chart_id, ""), contracts_payload=contracts_payload)
        errors.extend(file_errors)
        warnings.extend(file_warnings)
    return errors, warnings, len(files)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lint md2report fragments")
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
