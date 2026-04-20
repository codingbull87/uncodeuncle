#!/usr/bin/env python3
"""
Legacy compatibility wrapper for the supported md2report assembly modules.

This file intentionally re-exports the maintained implementations instead of
carrying a second copy of the assembler logic.
"""

from __future__ import annotations

import html as html_lib
import sys
from typing import Any

import assembly_service
from assembly_builder import (
    build_report_meta as _build_report_meta,
    fragment_sort_key,
    get_cover_span,
    has_renderable_fragment,
    load_echarts_js as _load_echarts_js,
    load_fragments as _load_fragments,
    load_static_css as _load_static_css,
    normalize_cover_content as _normalize_cover_content,
)
from assembly_output import (
    build_assembly_diagnostics,
    compose_final_html,
    extract_report_title as _extract_report_title,
    find_duplicate_chart_ids,
    print_validation_summary as _print_validation_summary,
)
from assembly_types import InjectionResult, LayoutBlock, PlannedInsertion
from insertion_planner import (
    find_insert_position,
    first_top_level_paragraph_end,
    iter_heading_matches as _iter_heading_matches,
    iter_top_level_block_spans,
    section_end_position,
)
from recommendation_loader import (
    normalize_recommendation_payload,
    parse_json_blocks_from_markdown,
    parse_recommendations_base,
    parse_storyboard_markdown,
)
from recommendation_state import (
    apply_layout_overrides as _apply_layout_overrides,
    load_layout_overrides as _load_layout_overrides,
    parse_recommendations as _parse_recommendations,
)
from report_contract import (
    default_max_shrink_ratio,
    infer_page_role,
    normalize_anchor,
    normalize_chart_id,
    normalize_layout,
    normalize_size,
    numeric_chart_id,
    parse_bool,
    parse_float,
    parse_occurrence,
    rec_can_shrink,
    rec_keep_with_next,
    rec_max_shrink_ratio,
    strip_tags,
    visual_type,
)


read_file = assembly_service.read_file
write_file = assembly_service.write_file
plan_insertions = assembly_service.plan_insertions
diagnose_group_assembly = assembly_service.diagnose_group_assembly
row_should_equal_height = assembly_service.row_should_equal_height
wrap_fragment = assembly_service.wrap_fragment
build_insertion_html = assembly_service.build_insertion_html
build_layout_plan = assembly_service.build_layout_plan
inject_charts_into_content = assembly_service.inject_charts_into_content
build_html = assembly_service.build_html


def parse_recommendations(
    report_dir: str,
    *,
    apply_generated_overrides: bool = True,
    override_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return _parse_recommendations(
        report_dir,
        normalize_chart_id=normalize_chart_id,
        read_file=read_file,
        apply_generated_overrides=apply_generated_overrides,
        override_payload=override_payload,
        emit_warning=print,
        emit_info=print,
    )


def load_layout_overrides(report_dir: str) -> dict[str, Any]:
    return _load_layout_overrides(report_dir, read_file=read_file, emit_warning=print)


def apply_layout_overrides(items: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    return _apply_layout_overrides(items, payload, normalize_chart_id=normalize_chart_id, emit_info=print)


def load_fragments(fragments_dir: str) -> dict[str, str]:
    return _load_fragments(fragments_dir, read_file=read_file, emit=print)


def normalize_cover_content(content_html: str) -> str:
    return _normalize_cover_content(content_html, html_escape=html_lib.escape)


def build_report_meta(blockquote_html: str) -> str:
    return _build_report_meta(blockquote_html, html_escape=html_lib.escape)


def iter_heading_matches(content_html: str, anchor_text: str):
    return _iter_heading_matches(content_html, anchor_text, strip_tags=strip_tags)


def load_static_css(skill_dir: str) -> str:
    return _load_static_css(skill_dir, read_file=read_file)


def load_echarts_js(skill_dir: str) -> str:
    return _load_echarts_js(skill_dir, read_file=read_file, emit=print)


def extract_report_title(content_html: str, fallback: str) -> str:
    return _extract_report_title(content_html, fallback, strip_tags=strip_tags)


def print_validation_summary(
    output_path: str,
    injection_results: list[InjectionResult],
    recommendation_count: int,
    fragment_count: int,
) -> None:
    _print_validation_summary(
        output_path,
        injection_results,
        recommendation_count,
        fragment_count,
        read_file=read_file,
        emit=print,
    )


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        print("用法：python3 scripts/assemble.py <report_dir> <output_name>")
        raise SystemExit(1)
    build_html(argv[1], argv[2])


if __name__ == "__main__":
    main(sys.argv)
