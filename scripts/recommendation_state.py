#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Any, Callable

from recommendation_loader import parse_recommendations_base


LAYOUT_OVERRIDE_FIELDS = {
    "layout",
    "size",
    "page_role",
    "keep_with_next",
    "can_shrink",
    "max_shrink_ratio",
    "equal_height",
    "row_align",
    "print_compact",
    "position",
    "group",
    "row_title",
    "group_title",
    "group_anchor",
    "row_anchor",
    "anchor",
    "anchor_occurrence",
}


def load_layout_overrides(
    report_dir: str,
    *,
    read_file: Callable[[str], str],
    emit_warning: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    path = os.path.join(report_dir, "LAYOUT_OVERRIDES.json")
    if not os.path.exists(path):
        return {}
    try:
        payload = json.loads(read_file(path))
    except json.JSONDecodeError as exc:
        if emit_warning is not None:
            emit_warning(f"[WARN] LAYOUT_OVERRIDES.json 解析失败：{exc}")
        return {}
    return payload if isinstance(payload, dict) else {}


def apply_layout_overrides(
    items: list[dict[str, Any]],
    payload: dict[str, Any],
    *,
    normalize_chart_id: Callable[[Any], str],
    emit_info: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    if not payload:
        return items
    by_chart = payload.get("by_chart_id", {})
    by_group = payload.get("by_group", {})
    if not isinstance(by_chart, dict):
        by_chart = {}
    if not isinstance(by_group, dict):
        by_group = {}

    changed = 0
    result: list[dict[str, Any]] = []
    for item in items:
        rec = dict(item)
        chart_id = normalize_chart_id(rec.get("id"))
        group = str(rec.get("group", "")).strip()
        chart_patch = by_chart.get(chart_id, {}) if chart_id else {}
        group_patch = by_group.get(group, {}) if group else {}
        if isinstance(group_patch, dict):
            for key, value in group_patch.items():
                if key in LAYOUT_OVERRIDE_FIELDS:
                    rec[key] = value
                    changed += 1
        if isinstance(chart_patch, dict):
            for key, value in chart_patch.items():
                if key in LAYOUT_OVERRIDE_FIELDS:
                    rec[key] = value
                    changed += 1
        result.append(rec)
    if changed and emit_info is not None:
        emit_info(f"[INFO] 应用布局覆盖项：{changed}")
    return result


def parse_recommendations(
    report_dir: str,
    *,
    normalize_chart_id: Callable[[Any], str],
    read_file: Callable[[str], str],
    apply_generated_overrides: bool = True,
    override_payload: dict[str, Any] | None = None,
    emit_warning: Callable[[str], None] | None = None,
    emit_info: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    items = parse_recommendations_base(report_dir)
    if not apply_generated_overrides:
        return items
    payload = override_payload if override_payload is not None else load_layout_overrides(
        report_dir,
        read_file=read_file,
        emit_warning=emit_warning,
    )
    return apply_layout_overrides(items, payload, normalize_chart_id=normalize_chart_id, emit_info=emit_info)
