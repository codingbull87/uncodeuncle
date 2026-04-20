#!/usr/bin/env python3
"""
Conservatively normalize fragment HTML so common contract drift is auto-repaired.

Usage:
  python3 scripts/normalize_fragments.py <report_dir> [--ids C1,C2]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from report_contract import normalize_chart_id
from theme_resolver import build_legacy_token_bridge, load_color_palette


ROOT_SELECTOR = re.compile(r":root\s*\{", flags=re.IGNORECASE)
ECHARTS_INIT = re.compile(r"echarts\.init\s*\(", flags=re.IGNORECASE)
REQUIRED_VARS = (
    "--color-primary",
    "--color-secondary",
    "--color-positive",
    "--color-negative",
    "--color-accent",
    "--color-border",
    "--color-text",
)

def parse_id_filter(raw: str) -> set[str]:
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return {normalize_chart_id(item) for item in items if normalize_chart_id(item)}


def resolve_color_scheme(report_dir: Path) -> str:
    brief_path = report_dir / "DESIGN_BRIEF.json"
    if not brief_path.exists():
        return "green"
    try:
        payload = json.loads(brief_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return "green"
    if not isinstance(payload, dict):
        return "green"
    return str(payload.get("color_scheme", "green")).strip().lower() or "green"


def palette_root_css(report_dir: Path) -> str:
    skill_dir = Path(__file__).resolve().parents[1]
    color_scheme = resolve_color_scheme(report_dir)
    palette = load_color_palette(str(skill_dir), color_scheme)
    bridge = build_legacy_token_bridge(color_scheme)
    payload = (palette + "\n" + bridge).strip()
    return payload + "\n" if payload else ""


def has_required_vars(text: str) -> bool:
    return all(token in text for token in REQUIRED_VARS)


def wrap_title_block(text: str, wrapper_class: str, title_class: str, kicker_class: str) -> tuple[str, bool]:
    if wrapper_class in text or title_class not in text:
        return text, False
    pattern = re.compile(
        rf"((?:<div[^>]*class=[\"'][^\"']*\b{kicker_class}\b[^\"']*[\"'][^>]*>.*?</div>\s*)?<div[^>]*class=[\"'][^\"']*\b{title_class}\b[^\"']*[\"'][^>]*>.*?</div>)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return text, False
    replacement = f'<div class="{wrapper_class}"><div>{match.group(1)}</div></div>'
    return text[: match.start()] + replacement + text[match.end() :], True


def normalize_fragment_text(text: str, report_dir: Path) -> tuple[str, list[str]]:
    changes: list[str] = []
    updated = text

    if "kpi-strip" in updated:
        updated = re.sub(r"\bkpi-strip\b", "kpi-block", updated)
        changes.append("canonicalized kpi-strip -> kpi-block")

    updated, changed = wrap_title_block(updated, "chart-header", "chart-title", "chart-kicker")
    if changed:
        changes.append("wrapped chart-title with chart-header")

    updated, changed = wrap_title_block(updated, "figure-header", "figure-title", "figure-kicker")
    if changed:
        changes.append("wrapped figure-title with figure-header")

    if ECHARTS_INIT.search(updated) and (not ROOT_SELECTOR.search(updated) or not has_required_vars(updated)):
        palette_css = palette_root_css(report_dir)
        if palette_css:
            updated = f"<style>\n{palette_css}</style>\n" + updated
            changes.append("prepended self-contained palette :root block for ECharts")

    return updated, changes


def normalize_fragments(report_dir: Path, id_filter: set[str] | None = None) -> dict[str, object]:
    fragments_dir = report_dir / "chart-fragments"
    files = sorted(path for path in fragments_dir.glob("C*.html") if path.is_file()) if fragments_dir.exists() else []
    results: list[dict[str, object]] = []
    changed_count = 0

    for path in files:
        chart_id = normalize_chart_id(path.stem)
        if id_filter and chart_id not in id_filter:
            continue
        original = path.read_text(encoding="utf-8", errors="ignore")
        updated, changes = normalize_fragment_text(original, report_dir)
        if changes and updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_count += 1
        results.append({"id": chart_id, "changed": bool(changes), "changes": changes})

    payload = {
        "schema": "report-illustrator-fragment-normalization:v1",
        "changed": changed_count,
        "items": results,
    }
    (report_dir / "FRAGMENT_NORMALIZATION.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Normalize md2report fragments")
    parser.add_argument("report_dir", help="Report workspace directory")
    parser.add_argument("--ids", help="Optional comma-separated fragment ids")
    args = parser.parse_args(argv[1:])

    report_dir = Path(args.report_dir).expanduser().resolve()
    if not report_dir.exists() or not report_dir.is_dir():
        print(f"[ERROR] 报告目录不存在：{report_dir}")
        return 1

    payload = normalize_fragments(report_dir, parse_id_filter(args.ids) if args.ids else None)
    print(f"[DONE] 片段规范化：changed={payload.get('changed', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
