#!/usr/bin/env python3
"""
Canonicalize recommendations into a single authoritative JSON source.

Usage:
  python3 scripts/prepare_recommendations.py <report_dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from build_anchor_index import load_anchor_index
from recommendation_loader import normalize_recommendation_payload
from report_contract import normalize_anchor, normalize_chart_id, parse_occurrence


def load_recommendations_source(report_dir: Path) -> tuple[list[dict[str, Any]], str]:
    json_path = report_dir / "RECOMMENDATIONS.json"
    if json_path.exists():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[ERROR] RECOMMENDATIONS.json 解析失败：{exc}")
        return normalize_recommendation_payload(payload), "RECOMMENDATIONS.json"

    if (report_dir / "RECOMMENDATIONS.md").exists():
        raise SystemExit("[ERROR] 仅检测到 RECOMMENDATIONS.md；当前 skill 已不再支持 Markdown 作为 recommendation 真实源，请先提供 RECOMMENDATIONS.json")

    raise SystemExit("[ERROR] 缺少 RECOMMENDATIONS.json；当前 skill 以 JSON 为唯一真实源")


def index_maps(anchor_index: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    items = [item for item in anchor_index.get("items", []) if isinstance(item, dict)]
    by_id = {str(item.get("anchor_id", "")).strip(): item for item in items if str(item.get("anchor_id", "")).strip()}
    by_text: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        text = normalize_anchor(item.get("text"))
        if text:
            by_text.setdefault(text, []).append(item)
    return by_id, by_text, items


def choose_by_occurrence(matches: list[dict[str, Any]], occurrence: int) -> dict[str, Any] | None:
    if not matches:
        return None
    for item in matches:
        if int(item.get("occurrence", 1)) == occurrence:
            return item
    if len(matches) == 1 and occurrence == 1:
        return matches[0]
    return None


def unique_defined(values: list[Any]) -> tuple[Any | None, bool]:
    present = [value for value in values if str(value).strip()]
    if not present:
        return None, False
    first = present[0]
    consistent = all(str(value) == str(first) for value in present)
    return (first if consistent else None), consistent


def stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def export_storyboard_markdown(items: list[dict[str, Any]], source_name: str) -> str:
    lines = [
        "# Recommendation Storyboard",
        "",
        "report-illustrator-plan:v3",
        "",
        f"derived_from: {source_name}",
        "authoritative_source: RECOMMENDATIONS.json",
        "note: 这是派生预览文件，不是唯一真实源。",
        "",
    ]
    preferred_keys = [
        "id",
        "type",
        "anchor_id",
        "anchor",
        "position",
        "anchor_occurrence",
        "layout",
        "size",
        "group",
        "group_anchor",
        "row_title",
        "equal_height",
        "page_role",
        "enabled",
    ]
    for item in items:
        chart_id = normalize_chart_id(item.get("id")) or str(item.get("id", "")).strip()
        lines.append(f"## {chart_id}")
        emitted: set[str] = set()
        for key in preferred_keys:
            if key not in item:
                continue
            lines.append(f"{key}: {stringify(item.get(key))}")
            emitted.add(key)
        for key in sorted(item.keys()):
            if key in emitted:
                continue
            lines.append(f"{key}: {stringify(item.get(key))}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_text_atomic(path: Path, text: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def prepare_recommendations(report_dir: Path) -> tuple[list[dict[str, Any]], list[str], list[str], str]:
    raw_items, source_name = load_recommendations_source(report_dir)
    authoritative_source = "RECOMMENDATIONS.json"
    anchor_index = load_anchor_index(report_dir)
    by_id, by_text, anchor_items = index_maps(anchor_index)

    warnings: list[str] = []
    errors: list[str] = []
    prepared: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}

    for raw in raw_items:
        rec = dict(raw)
        chart_id = normalize_chart_id(rec.get("id"))
        if not chart_id:
            errors.append("recommendation 缺少合法 id")
            continue
        rec["id"] = chart_id
        rec["anchor_occurrence"] = parse_occurrence(rec.get("anchor_occurrence", rec.get("occurrence", 1)))
        occurrence = int(rec["anchor_occurrence"])
        anchor_id = str(rec.get("anchor_id", "")).strip()
        anchor_text = normalize_anchor(rec.get("group_anchor") or rec.get("row_anchor") or rec.get("anchor"))
        resolved_item: dict[str, Any] | None = None

        if anchor_id:
            resolved_item = by_id.get(anchor_id)
            if not resolved_item:
                errors.append(f"{chart_id}: anchor_id 未命中 ANCHOR_INDEX.json（{anchor_id}）")
        elif anchor_text:
            exact_matches = by_text.get(anchor_text, [])
            resolved_item = choose_by_occurrence(exact_matches, occurrence)
            if not resolved_item:
                contains_matches = [
                    item
                    for item in anchor_items
                    if anchor_text and anchor_text in normalize_anchor(item.get("text"))
                ]
                if len(contains_matches) == 1:
                    resolved_item = contains_matches[0]
                    warnings.append(
                        f"{chart_id}: anchor 仅通过包含匹配命中，建议改为精确 heading 文本（{anchor_text} -> {resolved_item.get('text')})"
                    )
        if not resolved_item:
            errors.append(f"{chart_id}: anchor 未命中正文 heading（{anchor_text or anchor_id or '<empty>'}）")
        else:
            rec["anchor_id"] = str(resolved_item.get("anchor_id", "")).strip()
            rec["anchor"] = str(resolved_item.get("text", "")).strip()
            rec["anchor_occurrence"] = int(resolved_item.get("occurrence", occurrence))

        layout = str(rec.get("layout", "")).strip().lower()
        group = str(rec.get("group", "")).strip()
        if group and layout in {"half", "third", "quarter", "compact"}:
            grouped.setdefault(group, []).append(rec)
        prepared.append(rec)

    for group, members in sorted(grouped.items()):
        if len(members) < 2:
            continue
        for field in ("anchor_id", "anchor", "position", "anchor_occurrence"):
            value, consistent = unique_defined([item.get(field, "") for item in members])
            if not consistent:
                chart_ids = ", ".join(str(item.get("id", "")) for item in members)
                errors.append(f"group '{group}' 的字段 {field} 不一致：{chart_ids}")
                continue
            if value is None:
                continue
            for item in members:
                if not str(item.get(field, "")).strip():
                    item[field] = value
            if field in {"anchor_id", "anchor"}:
                for item in members:
                    item["group_anchor"] = str(item.get("anchor", "")).strip()

    match_report_items: list[dict[str, Any]] = []
    for rec in prepared:
        chart_id = str(rec.get("id", "")).strip()
        anchor_id = str(rec.get("anchor_id", "")).strip()
        anchor = str(rec.get("anchor", "")).strip()
        status = "resolved" if anchor_id and anchor else "unresolved"
        match_report_items.append(
            {
                "id": chart_id,
                "status": status,
                "anchor_id": anchor_id,
                "anchor": anchor,
                "position": str(rec.get("position", "")).strip(),
                "anchor_occurrence": int(rec.get("anchor_occurrence", 1)),
            }
        )

    prep_payload = {
        "schema": "report-illustrator-recommendation-prep:v1",
        "source": source_name,
        "authoritative_source": authoritative_source,
        "count": len(prepared),
        "warnings": warnings,
        "errors": errors,
    }
    prep_json = json.dumps(prep_payload, ensure_ascii=False, indent=2) + "\n"
    match_json = (
        json.dumps(
            {
                "schema": "report-illustrator-anchor-match-report:v1",
                "source": source_name,
                "authoritative_source": authoritative_source,
                "items": match_report_items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    if errors:
        write_text_atomic(report_dir / "RECOMMENDATION_PREP.json", prep_json)
        write_text_atomic(report_dir / "ANCHOR_MATCH_REPORT.json", match_json)
        return prepared, warnings, errors, authoritative_source

    canonical_json = json.dumps(prepared, ensure_ascii=False, indent=2) + "\n"
    write_text_atomic(report_dir / "RECOMMENDATIONS.json", canonical_json)
    write_text_atomic(report_dir / "RECOMMENDATIONS.normalized.json", canonical_json)
    write_text_atomic(report_dir / "RECOMMENDATIONS.storyboard.md", export_storyboard_markdown(prepared, source_name))
    write_text_atomic(report_dir / "RECOMMENDATION_PREP.json", prep_json)
    write_text_atomic(report_dir / "ANCHOR_MATCH_REPORT.json", match_json)
    return prepared, warnings, errors, authoritative_source


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Prepare md2report recommendations")
    parser.add_argument("report_dir", help="Report workspace directory")
    args = parser.parse_args(argv[1:])

    report_dir = Path(args.report_dir).expanduser().resolve()
    if not report_dir.exists() or not report_dir.is_dir():
        print(f"[ERROR] 报告目录不存在：{report_dir}")
        return 1

    items, warnings, errors, authoritative_source = prepare_recommendations(report_dir)
    print(f"[DONE] recommendation 规范化：{len(items)} 项")
    print(f"[INFO] authoritative_source={authoritative_source}")
    for item in warnings:
        print(f"[WARN] {item}")
    for item in errors:
        print(f"[ERROR] {item}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
