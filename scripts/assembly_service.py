#!/usr/bin/env python3
from __future__ import annotations

import html as html_lib
import os
from typing import Any

from assembly_builder import build_html as _build_html, inject_charts_into_content as _inject_charts_into_content
from assembly_output import build_assembly_diagnostics, compose_final_html, extract_report_title, print_validation_summary
from assembly_types import InjectionResult, LayoutBlock, PlannedInsertion
from insertion_planner import plan_insertions as _plan_insertions
from recommendation_state import parse_recommendations as _parse_recommendations
from report_contract import (
    infer_page_role,
    normalize_anchor,
    normalize_chart_id,
    normalize_layout,
    normalize_size,
    parse_bool,
    parse_occurrence,
    rec_can_shrink,
    rec_keep_with_next,
    rec_max_shrink_ratio,
    strip_tags,
)
from visual_layout import (
    build_insertion_html as _build_insertion_html,
    build_layout_plan as _build_layout_plan,
    diagnose_group_assembly as _diagnose_group_assembly,
    row_should_equal_height as _row_should_equal_height,
    wrap_fragment as _wrap_fragment,
)


def read_file(path: str, encoding: str = "utf-8") -> str:
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def write_file(path: str, content: str, encoding: str = "utf-8") -> None:
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def parse_recommendations(report_dir: str) -> list[dict[str, Any]]:
    return _parse_recommendations(
        report_dir,
        normalize_chart_id=normalize_chart_id,
        read_file=read_file,
        emit_warning=print,
        emit_info=print,
    )


def plan_insertions(
    content_html: str,
    fragment_map: dict[str, str],
    recommendations: list[dict[str, Any]],
):
    from assembly_builder import get_cover_span, has_renderable_fragment

    return _plan_insertions(
        content_html,
        fragment_map,
        recommendations,
        normalize_chart_id=normalize_chart_id,
        normalize_anchor=normalize_anchor,
        parse_occurrence=parse_occurrence,
        has_renderable_fragment=has_renderable_fragment,
        get_cover_span=get_cover_span,
        strip_tags=strip_tags,
        planned_insertion_factory=PlannedInsertion,
        injection_result_factory=InjectionResult,
    )


def diagnose_group_assembly(insertions: list[PlannedInsertion]) -> list[InjectionResult]:
    return _diagnose_group_assembly(
        insertions,
        normalize_layout=normalize_layout,
        normalize_chart_id=normalize_chart_id,
        injection_result_factory=InjectionResult,
    )


def row_should_equal_height(recs: list[dict[str, Any]]) -> bool:
    return _row_should_equal_height(recs, parse_bool=parse_bool)


def wrap_fragment(rec: dict[str, Any], fragment: str, nested: bool = False) -> str:
    return _wrap_fragment(
        rec,
        fragment,
        normalize_chart_id=normalize_chart_id,
        normalize_layout=normalize_layout,
        normalize_size=normalize_size,
        parse_bool=parse_bool,
        infer_page_role=infer_page_role,
        rec_keep_with_next=rec_keep_with_next,
        rec_can_shrink=rec_can_shrink,
        rec_max_shrink_ratio=rec_max_shrink_ratio,
        html_escape=html_lib.escape,
        nested=nested,
    )


def build_insertion_html(insertions: list[PlannedInsertion]) -> str:
    return _build_insertion_html(
        insertions,
        wrap_fragment_func=lambda rec, fragment: wrap_fragment(rec, fragment),
        wrap_nested_fragment_func=lambda rec, fragment: wrap_fragment(rec, fragment, nested=True),
        normalize_layout=normalize_layout,
        row_should_equal_height_func=row_should_equal_height,
        html_escape=html_lib.escape,
    )


def build_layout_plan(insertions: list[PlannedInsertion]) -> dict[str, Any]:
    return _build_layout_plan(
        insertions,
        layout_block_factory=LayoutBlock,
        normalize_chart_id=normalize_chart_id,
        normalize_layout=normalize_layout,
        normalize_size=normalize_size,
        infer_page_role=infer_page_role,
        rec_keep_with_next=rec_keep_with_next,
        rec_can_shrink=rec_can_shrink,
        rec_max_shrink_ratio=rec_max_shrink_ratio,
        row_should_equal_height_func=row_should_equal_height,
    )


def inject_charts_into_content(
    content_html: str,
    fragment_map: dict[str, str],
    recommendations: list[dict[str, Any]],
):
    return _inject_charts_into_content(
        content_html,
        fragment_map,
        recommendations,
        plan_insertions=plan_insertions,
        diagnose_group_assembly=diagnose_group_assembly,
        build_layout_plan=build_layout_plan,
        build_insertion_html=build_insertion_html,
    )


def build_html(report_dir: str, output_name: str) -> None:
    _build_html(
        report_dir,
        output_name,
        read_file=read_file,
        write_file=write_file,
        parse_recommendations=parse_recommendations,
        inject_charts_into_content=inject_charts_into_content,
        extract_report_title=lambda content_html, fallback: extract_report_title(content_html, fallback, strip_tags=strip_tags),
        build_assembly_diagnostics=build_assembly_diagnostics,
        compose_final_html=compose_final_html,
        print_validation_summary=lambda output_path, injection_results, recommendation_count, fragment_count: print_validation_summary(
            output_path,
            injection_results,
            recommendation_count,
            fragment_count,
            read_file=read_file,
            emit=print,
        ),
        html_escape=html_lib.escape,
        emit=print,
    )
