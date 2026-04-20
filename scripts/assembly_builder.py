#!/usr/bin/env python3
from __future__ import annotations

import glob
import os
import re
import sys
from typing import Any, Callable

from fragment_sanitizer import clean_fragment
from report_contract import normalize_chart_id, strip_tags
from theme_resolver import anchor_index_summary, load_color_scheme_css, recommendation_source_info, resolve_color_scheme_info


def fragment_sort_key(path: str) -> tuple[int, str]:
    name = os.path.basename(path)
    match = re.search(r"C(\d+)", name, flags=re.IGNORECASE)
    if match:
        return (int(match.group(1)), name)
    return (10**9, name)


def load_fragments(
    fragments_dir: str,
    *,
    read_file: Callable[[str], str],
    emit: Callable[[str], None] = print,
) -> dict[str, str]:
    fragment_map: dict[str, str] = {}
    pattern = os.path.join(fragments_dir, "C*.html")
    for fpath in sorted(glob.glob(pattern), key=fragment_sort_key):
        chart_id = normalize_chart_id(os.path.splitext(os.path.basename(fpath))[0])
        fragment_map[chart_id] = clean_fragment(read_file(fpath))
        emit(f"[OK] 清洗片段：{chart_id}")
    return fragment_map


def has_renderable_fragment(fragment: str) -> bool:
    return bool(
        re.search(
            r'echarts\.init|<svg\b|<table\b|kpi-val|consulting-|class="(?:scorecard|driver-tree|range-band|timeline|matrix|heatmap)',
            fragment,
            re.I,
        )
    )


def build_report_meta(
    blockquote_html: str,
    *,
    html_escape: Callable[[str], str],
) -> str:
    pairs: list[tuple[str, str]] = []
    pattern = re.compile(r"<strong>(.*?)</strong>\s*:?\s*(.*?)(?=<strong>|</p>|</blockquote>|$)", re.I | re.DOTALL)
    for key, value in pattern.findall(blockquote_html):
        clean_key = strip_tags(key)
        clean_value = strip_tags(value).strip(" :：")
        if clean_key and clean_value:
            pairs.append((clean_key, clean_value))

    if not pairs:
        clean = strip_tags(blockquote_html)
        return f'<div class="report-meta report-meta-freeform">{html_escape(clean)}</div>'

    spans = []
    for key, value in pairs:
        spans.append(f'<span class="report-meta-key">{html_escape(key)}</span>')
        spans.append(f'<span class="report-meta-value">{html_escape(value)}</span>')
    return '<div class="report-meta">\n' + "\n".join(spans) + "\n</div>"


def normalize_cover_content(
    content_html: str,
    *,
    html_escape: Callable[[str], str],
) -> str:
    if 'class="report-cover"' in content_html:
        return content_html

    pattern = re.compile(
        r"^\s*(<h1\b[^>]*>.*?</h1>)\s*(<blockquote\b[^>]*>.*?</blockquote>)?\s*(<hr\s*/?>)?",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(content_html)
    if not match:
        return content_html

    h1_html = match.group(1)
    blockquote_html = match.group(2) or ""
    meta_html = build_report_meta(blockquote_html, html_escape=html_escape) if blockquote_html else ""
    cover = f'<section class="report-cover">\n{h1_html}\n{meta_html}\n</section>\n'
    return cover + content_html[match.end():]


def get_cover_span(content_html: str) -> tuple[int, int] | None:
    match = re.search(r"<section\b[^>]*class=[\"'][^\"']*report-cover[^\"']*[\"'][^>]*>.*?</section>", content_html, flags=re.I | re.DOTALL)
    if match:
        return (match.start(), match.end())
    return None


def inject_charts_into_content(
    content_html: str,
    fragment_map: dict[str, str],
    recommendations: list[dict[str, Any]],
    *,
    plan_insertions: Callable[[str, dict[str, str], list[dict[str, Any]]], tuple[list[Any], list[Any]]],
    diagnose_group_assembly: Callable[[list[Any]], list[Any]],
    build_layout_plan: Callable[[list[Any]], dict[str, Any]],
    build_insertion_html: Callable[[list[Any]], str],
) -> tuple[str, list[Any], dict[str, Any]]:
    insertions, results = plan_insertions(content_html, fragment_map, recommendations)
    results.extend(diagnose_group_assembly(insertions))
    layout_plan = build_layout_plan(insertions)
    by_pos: dict[int, list[Any]] = {}
    for item in insertions:
        by_pos.setdefault(item.pos, []).append(item)

    for pos in sorted(by_pos.keys(), reverse=True):
        insertion_html = "\n" + build_insertion_html(by_pos[pos]) + "\n"
        content_html = content_html[:pos] + insertion_html + content_html[pos:]

    return content_html, results, layout_plan


def load_static_css(skill_dir: str, *, read_file: Callable[[str], str]) -> str:
    css_dir = os.path.join(skill_dir, "templates", "static", "css")
    if os.path.isdir(css_dir):
        css_files = sorted(glob.glob(os.path.join(css_dir, "*.css")))
        if css_files:
            parts = []
            for css_file in css_files:
                name = os.path.relpath(css_file, skill_dir)
                parts.append(f"/* {name} */\n{read_file(css_file)}")
            return "\n\n".join(parts)

    css_path = os.path.join(skill_dir, "templates", "static", "base-styles.css")
    return read_file(css_path)


def load_echarts_js(skill_dir: str, *, read_file: Callable[[str], str], emit: Callable[[str], None] = print) -> str:
    lib_path = os.path.join(skill_dir, "libs", "echarts.min.js")
    if not os.path.exists(lib_path):
        emit(f"[ERROR] 找不到 ECharts 运行库：{lib_path}")
        raise SystemExit(1)
    return read_file(lib_path)


def build_html(
    report_dir: str,
    output_name: str,
    *,
    read_file: Callable[[str], str],
    write_file: Callable[[str, str], None],
    parse_recommendations: Callable[[str], list[dict[str, Any]]],
    inject_charts_into_content: Callable[[str, dict[str, str], list[dict[str, Any]]], tuple[str, list[Any], dict[str, Any]]],
    extract_report_title: Callable[[str, str], str],
    build_assembly_diagnostics: Callable[..., dict[str, Any]],
    compose_final_html: Callable[..., str],
    print_validation_summary: Callable[[str, list[Any], int, int], None],
    html_escape: Callable[[str], str],
    emit: Callable[[str], None] = print,
) -> None:
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fragments_dir = os.path.join(report_dir, "chart-fragments")
    content_path = os.path.join(report_dir, "content.html")
    js_path = os.path.join(skill_dir, "templates", "static", "pdf-export.js")
    output_path = os.path.join(report_dir, output_name + ".html")
    layout_plan_path = os.path.join(report_dir, "LAYOUT_PLAN.json")
    diagnostics_path = os.path.join(report_dir, "ASSEMBLY_DIAGNOSTICS.json")
    theme_diag_path = os.path.join(report_dir, "THEME_RESOLUTION.json")

    if not os.path.exists(content_path):
        emit(f"[ERROR] 找不到正文文件：{content_path}")
        raise SystemExit(1)

    recommendations = parse_recommendations(report_dir)
    fragment_map = load_fragments(fragments_dir, read_file=read_file, emit=emit) if os.path.isdir(fragments_dir) else {}

    if recommendations and not fragment_map:
        emit(f"[WARN] 找不到片段目录或片段文件：{fragments_dir}")

    content_html = normalize_cover_content(read_file(content_path), html_escape=html_escape)
    content_with_charts, injection_results, layout_plan = inject_charts_into_content(content_html, fragment_map, recommendations)

    report_title = extract_report_title(content_with_charts, output_name)
    base_css = load_static_css(skill_dir, read_file=read_file)
    theme_info = resolve_color_scheme_info(report_dir)
    rec_source = recommendation_source_info(report_dir)
    anchor_summary = anchor_index_summary(report_dir)
    color_css = load_color_scheme_css(skill_dir, report_dir)
    echarts_js = load_echarts_js(skill_dir, read_file=read_file, emit=emit)
    pdf_js = read_file(js_path)
    diagnostics = build_assembly_diagnostics(
        report_title=report_title,
        output_name=os.path.basename(output_path),
        recommendations=recommendations,
        fragment_map=fragment_map,
        theme_info=theme_info,
        recommendation_source=rec_source,
        anchor_summary=anchor_summary,
    )

    final_html = compose_final_html(
        report_title=report_title,
        content_with_charts=content_with_charts,
        base_css=base_css,
        color_css=color_css,
        echarts_js=echarts_js,
        pdf_js=pdf_js,
        theme_info=theme_info,
        recommendation_source=rec_source,
        anchor_summary=anchor_summary,
        html_escape=html_escape,
    )

    write_file(output_path, final_html)
    write_file(layout_plan_path, json_dumps(layout_plan))
    write_file(diagnostics_path, json_dumps(diagnostics))
    write_file(theme_diag_path, json_dumps(theme_info))
    emit(f"[DONE] 输出文件：{output_path}")
    emit(f"[DONE] 页面排版计划：{layout_plan_path}")
    emit(f"[DONE] 组装诊断：{diagnostics_path}")
    print_validation_summary(output_path, injection_results, len(recommendations), len(fragment_map))


def json_dumps(payload: Any) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
