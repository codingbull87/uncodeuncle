#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any, Callable


VISUAL_BLOCK_REGEX = re.compile(
    r'<div\b[^>]*class=["\'][^"\']*\bvisual-(?:row|block)\b[^"\']*["\']',
    flags=re.IGNORECASE,
)
COVER_SECTION_REGEX = re.compile(
    r'<section\b[^>]*class=["\'][^"\']*\breport-cover\b[^"\']*["\'][^>]*>.*?</section>',
    flags=re.IGNORECASE | re.DOTALL,
)


def extract_report_title(content_html: str, fallback: str, *, strip_tags: Callable[[str], str]) -> str:
    title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", content_html, flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        title = strip_tags(title_match.group(1))
        if title:
            return title
    return fallback


def find_duplicate_chart_ids(html: str) -> list[str]:
    ids = re.findall(r'\bid=["\'](chart-C\d+)["\']', html, flags=re.IGNORECASE)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in ids:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)


def cover_is_protected(final_html: str) -> bool:
    cover_match = COVER_SECTION_REGEX.search(final_html)
    if not cover_match:
        return False
    if VISUAL_BLOCK_REGEX.search(final_html[:cover_match.start()]):
        return False
    if VISUAL_BLOCK_REGEX.search(cover_match.group(0)):
        return False
    return True


def compute_validation_summary(final_html: str, injection_results: list[Any]) -> dict[str, Any]:
    residual_p_block = len(re.findall(r"<p>\s*<(?:div|script|table|svg)", final_html, re.IGNORECASE))
    residual_download = len(re.findall(r"chart-download|downloadChart|html2canvas|jspdf", final_html, re.IGNORECASE))
    duplicate_ids = find_duplicate_chart_ids(final_html)
    visual_rows = len(re.findall(r'<div\s+class="visual-row(?:\s|")', final_html, re.IGNORECASE))
    cover_present = COVER_SECTION_REGEX.search(final_html) is not None
    cover_protected = cover_is_protected(final_html)
    injected = sum(1 for result in injection_results if result.status == "OK")
    warnings = [result for result in injection_results if result.status != "OK"]
    return {
        "injected": injected,
        "warnings": warnings,
        "residual_p_block": residual_p_block,
        "residual_download": residual_download,
        "duplicate_ids": duplicate_ids,
        "visual_rows": visual_rows,
        "cover_present": cover_present,
        "cover_protected": cover_protected,
        "all_passed": cover_protected and residual_p_block == 0 and residual_download == 0 and not duplicate_ids and not warnings,
    }


def print_validation_summary(
    output_path: str,
    injection_results: list[Any],
    recommendation_count: int,
    fragment_count: int,
    *,
    read_file: Callable[[str], str],
    emit: Callable[[str], None] = print,
) -> None:
    final = read_file(output_path)
    summary = compute_validation_summary(final, injection_results)

    emit("[验证] recommendations：{}，fragments：{}，已注入：{}".format(recommendation_count, fragment_count, summary["injected"]))
    for result in injection_results:
        prefix = "[OK]" if result.status == "OK" else "[WARN]"
        chart_label = result.chart_id or "(unknown)"
        emit(f"{prefix} {chart_label} / {result.anchor} / {result.message}")
    emit(f"[验证] <p> 包裹块级元素残留：{summary['residual_p_block']}")
    emit(f"[验证] 下载/截图旧逻辑残留：{summary['residual_download']}")
    emit(f"[验证] 重复 chart id：{', '.join(summary['duplicate_ids']) if summary['duplicate_ids'] else '无'}")
    emit(f"[验证] 并排视觉行：{summary['visual_rows']}")
    if summary["cover_protected"]:
        cover_status = "通过"
    elif summary["cover_present"]:
        cover_status = "失败"
    else:
        cover_status = "未检测到封面"
    emit(f"[验证] 封面保护：{cover_status}")

    if summary["all_passed"]:
        emit("[验证] 全部通过")
    else:
        emit("[WARN] 存在需要检查的问题")


def build_assembly_diagnostics(
    *,
    report_title: str,
    output_name: str,
    recommendations: list[dict[str, Any]],
    fragment_map: dict[str, str],
    theme_info: dict[str, Any],
    recommendation_source: dict[str, Any],
    anchor_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "report-illustrator-assembly-diagnostics:v1",
        "report_title": report_title,
        "output_html": output_name,
        "recommendation_count": len(recommendations),
        "fragment_count": len(fragment_map),
        "theme": theme_info,
        "recommendation_source": recommendation_source,
        "anchor_index": anchor_summary,
    }


def compose_final_html(
    *,
    report_title: str,
    content_with_charts: str,
    base_css: str,
    color_css: str,
    echarts_js: str,
    pdf_js: str,
    theme_info: dict[str, Any],
    recommendation_source: dict[str, Any],
    anchor_summary: dict[str, Any],
    html_escape: Callable[[str], str],
) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="report-color-scheme" content="{html_escape(theme_info['requested_color_scheme'])}">
  <meta name="report-color-scheme-resolved" content="{html_escape(theme_info['resolved_color_scheme'])}">
  <meta name="report-recommendations-source" content="{html_escape(recommendation_source['source'])}">
  <meta name="report-anchor-index-count" content="{html_escape(str(anchor_summary['count']))}">
  <title>{html_escape(report_title)}</title>
  <style>
{base_css}
{color_css}
  </style>
  <script>
{echarts_js}
  </script>
</head>
<body>
  <main class="page">
{content_with_charts}
  </main>
  <button id="pdf-export-btn" type="button">打印 / 导出 PDF</button>
  <script>
{pdf_js}
  </script>
</body>
</html>
"""
