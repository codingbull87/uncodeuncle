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

from assemble_engine import (
    apply_layout_overrides,
    normalize_chart_id,
    normalize_layout,
    normalize_size,
    parse_recommendations,
    parse_recommendations_base,
    visual_type,
)


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
    chart_id = normalize_chart_id(item.get("target_chart_id"))
    if chart_id:
        targets.append(chart_id)
    for raw in item.get("target_member_chart_ids", []) or []:
        cid = normalize_chart_id(raw)
        if cid and cid not in targets:
            targets.append(cid)
    return targets


def current_effective_recommendations(report_dir: Path, current_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = parse_recommendations_base(str(report_dir))
    return apply_layout_overrides(raw_items, current_payload)


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


def rec_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for rec in items:
        cid = normalize_chart_id(rec.get("id"))
        if cid:
            idx[cid] = rec
    return idx


def apply_suggestions(effective_items: list[dict[str, Any]], diagnosis: dict[str, Any]) -> list[dict[str, Any]]:
    index = rec_index(effective_items)
    touched: list[str] = []
    for sparse in diagnosis.get("sparsePages", []):
        for suggestion in sparse.get("suggestions", []):
            action = str(suggestion.get("action", "")).strip()
            targets = normalize_targets(suggestion)
            for chart_id in targets:
                rec = index.get(chart_id)
                if not rec:
                    continue
                if action in {"compact_trailing_visual", "compact_next_visual"}:
                    apply_compact_mutation(rec)
                elif action == "move_trailing_visual_to_section_end":
                    apply_section_end_mutation(rec)
                elif action == "split_trailing_row":
                    apply_split_row_mutation(rec)
                else:
                    continue
                touched.append(f"{action}:{chart_id}")
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
    payload, changed = build_payload(raw_items, effective_items, diagnosis)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[LAYOUT_REPAIR] diagnosis={diagnosis_path}")
    print(f"[LAYOUT_REPAIR] output={output_path}")
    print(f"[LAYOUT_REPAIR] changed={changed} sparse_pages={len(diagnosis.get('sparsePages', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
