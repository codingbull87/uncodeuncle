#!/usr/bin/env python3
"""
Theme and recommendation-source resolution helpers for md2report assembly.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from recommendation_loader import resolve_recommendation_source


PALETTE_ALIASES: dict[str, str] = {
    "consulting-classic": "green",
    "institutional-carbon": "blue",
    "banker-monochrome": "black",
    "financial-blue": "blue",
    "burgundy-editorial": "wine",
    "consulting-navy": "green",
    "institutional-blue": "blue",
    "corporate-neutral": "blue",
    "financial-trust": "blue",
    "boardroom-green": "green",
    "monochrome-executive": "black",
    "mckinsey-blue": "green",
    "modern-slate": "blue",
    "warm-clay": "warm",
    "forest-green": "green",
    "minimal-light": "black",
}


def read_file(path: str, encoding: str = "utf-8") -> str:
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def read_json_if_exists(path: str) -> Any:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_design_brief_payload(report_dir: str) -> dict[str, Any]:
    payload = read_json_if_exists(os.path.join(report_dir, "DESIGN_BRIEF.json"))
    return payload if isinstance(payload, dict) else {}


def resolve_color_scheme_info(report_dir: str) -> dict[str, Any]:
    brief = load_design_brief_payload(report_dir)
    requested = str(brief.get("color_scheme", "green") or "green").strip().lower()
    resolved = PALETTE_ALIASES.get(requested, requested or "green")
    return {
        "source": "DESIGN_BRIEF.json" if brief else "default",
        "requested_color_scheme": requested or "green",
        "resolved_color_scheme": resolved or "green",
        "color_confirmed": brief.get("color_confirmed") is True,
        "color_selected_by": str(brief.get("color_selected_by", "")).strip(),
    }


def recommendation_source_info(report_dir: str) -> dict[str, Any]:
    source_info = resolve_recommendation_source(report_dir)
    return {
        "source": source_info["source"],
        "authoritative": bool(source_info.get("authoritative")),
        "supported": bool(source_info.get("supported")),
        "reason": str(source_info.get("reason", "")).strip(),
    }


def anchor_index_summary(report_dir: str) -> dict[str, Any]:
    payload = read_json_if_exists(os.path.join(report_dir, "ANCHOR_INDEX.json"))
    if not isinstance(payload, dict):
        return {"present": False, "count": 0}
    items = payload.get("items", [])
    return {
        "present": True,
        "count": len(items) if isinstance(items, list) else 0,
        "schema": str(payload.get("schema", "")),
    }


def build_legacy_token_bridge(color_scheme: str) -> str:
    return """
:root {
  --color-primary: var(--chart-1);
  --color-primary-dark: var(--accent-strong);
  --color-positive: var(--semantic-positive);
  --color-negative: var(--semantic-negative);
  --color-accent: var(--accent-tertiary);
  --color-secondary: var(--text-muted);
  --color-border: var(--border-subtle);
  --color-bg: #ffffff;
  --color-surface: #ffffff;
  --color-text: var(--text-primary);
  --color-text-secondary: var(--text-muted);

  --ink: var(--text-secondary);
  --ink-strong: var(--text-primary);
  --muted: var(--text-muted);
  --soft: var(--text-muted);
  --line: var(--border-subtle);
  --line-strong: var(--border-strong);
  --paper: #ffffff;
  --wash: var(--report-subtle);
  --wash-2: var(--accent-soft);
  --brand: var(--accent-primary);
  --brand-dark: var(--accent-strong);
  --brand-soft: var(--accent-soft);
  --green: var(--semantic-positive);
  --red: var(--semantic-negative);
  --amber: var(--semantic-warning);
  --blue: var(--semantic-info);
  --graphite: var(--text-secondary);
  --table-header-bg: var(--style-header-fill);
  --table-header-text: var(--text-primary);
  --shadow: 0 2px 12px rgba(17, 24, 39, 0.06);
}
html,
body,
.page {
  background: #ffffff;
}
"""


def load_color_palette(skill_dir: str, color_scheme: str) -> str:
    palette_path = os.path.join(skill_dir, "references", "color-palettes.md")
    if not os.path.exists(palette_path):
        print("[WARN] 找不到 color-palettes.md，使用默认配色")
        return ""

    content = read_file(palette_path)
    normalized_scheme = PALETTE_ALIASES.get(color_scheme, color_scheme)
    scheme_keys = {
        "green": "A. Green",
        "warm": "B. Warm",
        "wine": "C. Wine",
        "black": "D. Black",
        "blue": "E. Blue",
    }
    target = scheme_keys.get(normalized_scheme, "A. Green")
    pattern = re.compile(
        r"(^## " + re.escape(target) + r" — .*?)\n(.*?)(?=^##\s+[A-E]\.|^## 旧方案兼容|^## 变量说明|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        print(f"[WARN] 在 color-palettes.md 中未找到 '{target}'，使用默认")
        return ""

    section_body = match.group(2)
    css_block_pattern = re.compile(r"```css\s*([\s\S]*?)```", re.MULTILINE)
    css_match = css_block_pattern.search(section_body)
    if not css_match:
        return ""

    css_text = css_match.group(1).strip()
    root_match = re.search(r"(:root\s*\{[\s\S]*?\})", css_text)
    if root_match:
        return "\n" + root_match.group(1) + "\n"
    return "\n" + css_text + "\n"


def load_color_scheme_css(skill_dir: str, report_dir: str) -> str:
    theme_info = resolve_color_scheme_info(report_dir)
    color_scheme = theme_info["resolved_color_scheme"]
    print(f"[INFO] 配色方案：{color_scheme}")
    palette_css = load_color_palette(skill_dir, color_scheme)
    return palette_css + build_legacy_token_bridge(color_scheme)
