#!/usr/bin/env python3
"""
Generate a fresh LAYOUT_OVERRIDES.json from the current layout diagnosis.

The file is treated as a derived artifact, not a cumulative state bag:
- start from raw recommendations
- apply the current override payload to understand the current effective state
- apply bounded repair actions from diagnosis
- diff effective recommendations back against the raw baseline

Usage:
  python3 scripts/repair_layout.py <report_dir> [diagnosis_json] [output_json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from recommendation_loader import parse_recommendations_base
from recommendation_state import apply_layout_overrides
from report_contract import normalize_chart_id, normalize_layout, normalize_size, visual_type


LOW_INFO_TYPES = {
    "kpi_strip",
    "insight_cards",
    "framework_cards",
    "scorecard",
    "risk_matrix",
    "heatmap",
    "timeline",
    "value_chain",
    "process_chain",
    "driver_tree",
    "decision_tree",
    "football_field",
    "range_band",
    "swimlane",
}

PATCH_FIELDS = {
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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def compact_state(rec: dict[str, Any]) -> int:
    score = 0
    if normalize_layout(rec.get("layout")) == "compact":
        score += 2
    if normalize_size(rec.get("size")) in {"small", "compact"}:
        score += 1
    if truthy(rec.get("print_compact")):
        score += 1
    return score


def normalize_targets(item: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    chart_id = normalize_chart_id(item.get("target_chart_id") or item.get("chartId"))
    if chart_id:
        targets.append(chart_id)
    raw_members = item.get("target_member_chart_ids", []) or item.get("memberChartIds", []) or []
    for raw in raw_members:
        cid = normalize_chart_id(raw)
        if cid and cid not in targets:
            targets.append(cid)
    return targets


def heading_anchor_text(block: dict[str, Any] | None) -> str:
    if not isinstance(block, dict):
        return ""
    tag = str(block.get("tag") or "").strip().lower()
    text = str(block.get("text") or "").strip()
    if len(tag) == 2 and tag.startswith("h") and tag[1].isdigit() and text:
        return text
    return ""


def current_effective_recommendations(report_dir: Path, current_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = parse_recommendations_base(str(report_dir))
    return apply_layout_overrides(raw_items, current_payload, normalize_chart_id=normalize_chart_id)


def apply_compact_mutation(rec: dict[str, Any]) -> None:
    try:
        ratio = float(rec.get("max_shrink_ratio") or 0.0)
    except (TypeError, ValueError):
        ratio = 0.0
    rec["can_shrink"] = True
    rec["max_shrink_ratio"] = max(0.30, ratio)
    rec["print_compact"] = True
    rec["keep_with_next"] = False

    size = normalize_size(rec.get("size"))
    if size in {"large", "medium"}:
        rec["size"] = "small"
    elif size == "small":
        rec["size"] = "compact"
    else:
        rec["size"] = "compact"

    vtype = visual_type(rec)
    if vtype in LOW_INFO_TYPES and compact_state(rec) >= 2 and normalize_layout(rec.get("layout")) == "full":
        rec["layout"] = "compact"


def apply_section_end_mutation(rec: dict[str, Any]) -> None:
    rec["position"] = "section_end"
    rec["keep_with_next"] = False
    if visual_type(rec) in LOW_INFO_TYPES and compact_state(rec) < 2:
        apply_compact_mutation(rec)


def apply_split_row_mutation(rec: dict[str, Any]) -> None:
    rec["group"] = ""
    if normalize_layout(rec.get("layout")) in {"half", "third", "quarter"}:
        rec["layout"] = "full"
    if normalize_size(rec.get("size")) == "large":
        rec["size"] = "medium"
    rec["keep_with_next"] = False


def restore_raw_fields(rec: dict[str, Any], raw_rec: dict[str, Any]) -> None:
    for field in PATCH_FIELDS:
        rec[field] = raw_rec.get(field)


def rec_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for rec in items:
        cid = normalize_chart_id(rec.get("id"))
        if cid:
            idx[cid] = rec
    return idx


def group_index(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for rec in items:
        chart_id = normalize_chart_id(rec.get("id"))
        group = str(rec.get("group", "")).strip()
        if not chart_id or not group:
            continue
        members = idx.setdefault(group, [])
        if chart_id not in members:
            members.append(chart_id)
    return idx


def expand_group_targets(
    target_ids: list[str],
    raw_index: dict[str, dict[str, Any]],
    effective_index: dict[str, dict[str, Any]],
    raw_groups: dict[str, list[str]],
    effective_groups: dict[str, list[str]],
) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()

    def add(chart_id: str) -> None:
        if chart_id and chart_id not in seen:
            seen.add(chart_id)
            expanded.append(chart_id)

    for chart_id in target_ids:
        add(chart_id)
        for rec in (effective_index.get(chart_id), raw_index.get(chart_id)):
            if not rec:
                continue
            group = str(rec.get("group", "")).strip()
            if not group:
                continue
            for member_id in raw_groups.get(group, []) + effective_groups.get(group, []):
                add(member_id)
    return expanded


def apply_suggestions(effective_items: list[dict[str, Any]], diagnosis: dict[str, Any]) -> list[dict[str, Any]]:
    index = rec_index(effective_items)
    touched: list[str] = []
    all_sparse = list(diagnosis.get("sparsePages", [])) + list(diagnosis.get("terminalSparsePages", []))
    for sparse in all_sparse:
        terminal_heading = heading_anchor_text(sparse.get("first_terminal_block"))
        for suggestion in sparse.get("suggestions", []):
            action = str(suggestion.get("action", "")).strip()
            targets = normalize_targets(suggestion)
            for chart_id in targets:
                rec = index.get(chart_id)
                if not rec:
                    continue
                if action in {"compact_trailing_visual", "compact_next_visual", "compact_prev_page_visual"}:
                    apply_compact_mutation(rec)
                elif action == "move_trailing_visual_to_section_end":
                    if terminal_heading:
                        continue
                    apply_section_end_mutation(rec)
                elif action == "split_trailing_row":
                    apply_split_row_mutation(rec)
                else:
                    continue
                touched.append(f"{action}:{chart_id}")
    diagnosis["appliedActions"] = touched
    return effective_items


def repair_terminal_sparse_pages(
    raw_items: list[dict[str, Any]],
    effective_items: list[dict[str, Any]],
    diagnosis: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_index = rec_index(raw_items)
    effective_index = rec_index(effective_items)
    touched: list[str] = list(diagnosis.get("appliedActions", []))

    for sparse in diagnosis.get("terminalSparsePages", []):
        page_blocks = sparse.get("pageBlocks", []) or []
        if len(page_blocks) != 1:
            continue
        block = page_blocks[0]
        chart_id = normalize_chart_id(block.get("chartId"))
        if not chart_id:
            continue
        raw_rec = raw_index.get(chart_id)
        rec = effective_index.get(chart_id)
        if not raw_rec or not rec:
            continue
        if visual_type(rec) not in LOW_INFO_TYPES:
            continue

        current_position = str(rec.get("position") or "").strip()
        raw_position = str(raw_rec.get("position") or "").strip()
        if current_position != "section_end":
            continue
        if not raw_position or raw_position == current_position:
            continue

        restore_raw_fields(rec, raw_rec)
        touched.append(f"restore_terminal_visual_to_raw_position:{chart_id}")

    diagnosis["appliedActions"] = touched
    return effective_items


def reflow_prev_visual_into_terminal_heading(
    raw_items: list[dict[str, Any]],
    effective_items: list[dict[str, Any]],
    diagnosis: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_index = rec_index(raw_items)
    effective_index = rec_index(effective_items)
    raw_groups = group_index(raw_items)
    effective_groups = group_index(effective_items)
    touched: list[str] = list(diagnosis.get("appliedActions", []))

    for sparse in diagnosis.get("terminalSparsePages", []):
        prev_visual = sparse.get("previous_page_trailing_visual") or {}
        anchor_text = heading_anchor_text(sparse.get("first_terminal_block"))
        target_ids = expand_group_targets(
            normalize_targets(prev_visual),
            raw_index,
            effective_index,
            raw_groups,
            effective_groups,
        )
        if not target_ids or not anchor_text:
            continue
        target_recs = [effective_index[chart_id] for chart_id in target_ids if chart_id in effective_index]
        if not target_recs:
            continue
        if any(visual_type(rec) not in LOW_INFO_TYPES for rec in target_recs):
            continue

        for chart_id in target_ids:
            raw_rec = raw_index.get(chart_id)
            rec = effective_index.get(chart_id)
            if not raw_rec or not rec:
                continue

            restore_raw_fields(rec, raw_rec)
            rec["anchor"] = anchor_text
            rec["anchor_occurrence"] = 1
            group = str(rec.get("group") or raw_rec.get("group") or "").strip()
            if group or str(rec.get("group_anchor") or raw_rec.get("group_anchor") or "").strip():
                rec["group_anchor"] = anchor_text
            if group or str(rec.get("row_anchor") or raw_rec.get("row_anchor") or "").strip():
                rec["row_anchor"] = anchor_text
            rec["position"] = "after_heading"
            rec["keep_with_next"] = False
            rec["can_shrink"] = True
            try:
                ratio = float(rec.get("max_shrink_ratio") or 0.0)
            except (TypeError, ValueError):
                ratio = 0.0
            rec["max_shrink_ratio"] = max(0.30, ratio)
            touched.append(f"reflow_prev_visual_after_terminal_heading:{chart_id}")

    diagnosis["appliedActions"] = touched
    return effective_items


def build_payload(raw_items: list[dict[str, Any]], effective_items: list[dict[str, Any]], diagnosis: dict[str, Any]) -> tuple[dict[str, Any], int]:
    raw_index = rec_index(raw_items)
    effective_index = rec_index(effective_items)
    by_chart: dict[str, dict[str, Any]] = {}
    changes = 0

    for chart_id, raw_rec in raw_index.items():
        effective = effective_index.get(chart_id)
        if not effective:
            continue
        patch: dict[str, Any] = {}
        for field in PATCH_FIELDS:
            if raw_rec.get(field) != effective.get(field):
                patch[field] = effective.get(field)
        if patch:
            by_chart[chart_id] = patch
            changes += len(patch)

    payload = {
        "schema": "report-illustrator-layout-overrides:v2",
        "generated_by": "repair_layout.py",
        "derived": True,
        "by_chart_id": by_chart,
        "by_group": {},
        "last_sparse_pages": [
            {"page": item.get("page"), "blankRatio": item.get("blankRatio")}
            for item in diagnosis.get("sparsePages", [])
        ],
        "applied_actions": diagnosis.get("appliedActions", []),
    }
    return payload, changes


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build fresh layout overrides from diagnosis JSON")
    parser.add_argument("report_dir", help="Report workspace directory")
    parser.add_argument("diagnosis_json", nargs="?", help="Optional diagnosis JSON path")
    parser.add_argument("output_json", nargs="?", help="Optional output overrides JSON path")
    args = parser.parse_args(argv[1:])

    report_dir = Path(args.report_dir).expanduser().resolve()
    if not report_dir.exists() or not report_dir.is_dir():
        print(f"[ERROR] 报告目录不存在：{report_dir}")
        return 1

    diagnosis_path = Path(args.diagnosis_json).expanduser().resolve() if args.diagnosis_json else report_dir / "LAYOUT_DIAGNOSIS.json"
    output_path = Path(args.output_json).expanduser().resolve() if args.output_json else report_dir / "LAYOUT_OVERRIDES.json"

    if not diagnosis_path.exists():
        print(f"[ERROR] 找不到诊断文件：{diagnosis_path}")
        return 1

    diagnosis = read_json(diagnosis_path)
    current_payload = read_json(output_path) if output_path.exists() else {}

    raw_items = parse_recommendations_base(str(report_dir))
    effective_items = current_effective_recommendations(report_dir, current_payload if isinstance(current_payload, dict) else {})
    effective_items = apply_suggestions(effective_items, diagnosis)
    effective_items = reflow_prev_visual_into_terminal_heading(raw_items, effective_items, diagnosis)
    effective_items = repair_terminal_sparse_pages(raw_items, effective_items, diagnosis)
    payload, changed = build_payload(raw_items, effective_items, diagnosis)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[LAYOUT_REPAIR] diagnosis={diagnosis_path}")
    print(f"[LAYOUT_REPAIR] output={output_path}")
    print(f"[LAYOUT_REPAIR] changed={changed} sparse_pages={len(diagnosis.get('sparsePages', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
