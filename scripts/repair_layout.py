#!/usr/bin/env python3
"""
Generate/refresh LAYOUT_OVERRIDES.json based on LAYOUT_DIAGNOSIS.json.

Usage:
  python3 scripts/repair_layout.py <report_dir> [diagnosis_json] [output_json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from assemble_engine import normalize_chart_id, parse_recommendations


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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def rec_index(report_dir: Path) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for rec in parse_recommendations(str(report_dir)):
        cid = normalize_chart_id(rec.get("id"))
        if cid:
            idx[cid] = rec
    return idx


def merge_patch(target: dict[str, Any], patch: dict[str, Any]) -> int:
    changed = 0
    for key, value in patch.items():
        if target.get(key) != value:
            target[key] = value
            changed += 1
    return changed


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


def build_overrides(report_dir: Path, diagnosis: dict[str, Any], existing: dict[str, Any]) -> tuple[dict[str, Any], int]:
    recs = rec_index(report_dir)
    payload = existing if isinstance(existing, dict) else {}
    payload.setdefault("schema", "report-illustrator-layout-overrides:v1")
    payload.setdefault("generated_by", "repair_layout.py")
    payload.setdefault("by_chart_id", {})
    payload.setdefault("by_group", {})
    by_chart = payload["by_chart_id"]

    changed = 0
    for sparse in diagnosis.get("sparsePages", []):
        for suggestion in sparse.get("suggestions", []):
            action = str(suggestion.get("action", "")).strip()
            targets = normalize_targets(suggestion)
            for chart_id in targets:
                patch: dict[str, Any] = {
                    "can_shrink": True,
                    "max_shrink_ratio": 0.30,
                    "print_compact": True,
                    "keep_with_next": False,
                }
                rec = recs.get(chart_id, {})
                vtype = str(rec.get("type", "")).strip().lower()
                layout = str(rec.get("layout", "full")).strip().lower()
                size = str(rec.get("size", "medium")).strip().lower()

                if action in {"compact_trailing", "compact_next", "tighten_trailing"}:
                    if size in {"medium", "large"}:
                        patch["size"] = "small"
                    elif size == "small":
                        patch["size"] = "compact"

                if action == "tighten_trailing" and vtype in LOW_INFO_TYPES and layout == "full":
                    patch["layout"] = "compact"

                slot = by_chart.setdefault(chart_id, {})
                changed += merge_patch(slot, patch)

    payload["last_sparse_pages"] = [
        {"page": item.get("page"), "blankRatio": item.get("blankRatio")} for item in diagnosis.get("sparsePages", [])
    ]
    return payload, changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build layout overrides from diagnosis JSON")
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
    existing = read_json(output_path) if output_path.exists() else {}
    payload, changed = build_overrides(report_dir, diagnosis, existing)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[LAYOUT_REPAIR] diagnosis={diagnosis_path}")
    print(f"[LAYOUT_REPAIR] output={output_path}")
    print(f"[LAYOUT_REPAIR] changed={changed} sparse_pages={len(diagnosis.get('sparsePages', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
