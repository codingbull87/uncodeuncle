#!/usr/bin/env python3
from __future__ import annotations

import html as html_lib
import re
from typing import Any


def normalize_chart_id(raw_id: Any) -> str:
    text = str(raw_id or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"C\d+", text, flags=re.IGNORECASE):
        return "C" + re.search(r"\d+", text).group(0)
    if re.fullmatch(r"\d+", text):
        return "C" + text
    return text


def numeric_chart_id(raw_id: Any) -> str:
    chart_id = normalize_chart_id(raw_id)
    match = re.search(r"\d+", chart_id)
    return match.group(0) if match else chart_id


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = html_lib.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_anchor(anchor: Any) -> str:
    text = str(anchor or "").strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = strip_tags(text)
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return text


def heading_level(tag: Any) -> int | None:
    text = str(tag or "").strip().lower()
    if re.fullmatch(r"h[1-6]", text):
        return int(text[1])
    return None


def is_heading_tag(tag: Any) -> bool:
    return heading_level(tag) is not None


def parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("false", "no", "off", "0", "disabled", "skip", "否", "停用"):
        return False
    if text in ("true", "yes", "on", "1", "enabled", "是", "启用"):
        return True
    return default


def parse_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number


def parse_occurrence(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 1
    return max(number, 1)


def normalize_layout(value: Any) -> str:
    text = str(value or "full").strip().lower()
    if text in ("half", "third", "quarter", "compact", "full"):
        return text
    return "full"


def normalize_size(value: Any) -> str:
    text = str(value or "medium").strip().lower()
    if text in ("small", "medium", "large", "compact"):
        return text
    return "medium"


def visual_type(rec: dict[str, Any]) -> str:
    return str(rec.get("type", "")).strip().lower()


def infer_page_role(rec: dict[str, Any]) -> str:
    explicit = str(rec.get("page_role", "") or rec.get("page_role_hint", "")).strip().lower()
    if explicit:
        return explicit
    layout = normalize_layout(rec.get("layout"))
    vtype = visual_type(rec)
    if layout in ("half", "third", "quarter", "compact"):
        return "paired_visual"
    if "table" in vtype:
        return "table_visual"
    if "kpi" in vtype:
        return "kpi_visual"
    return "figure_text"


def default_max_shrink_ratio(rec: dict[str, Any]) -> float:
    size = normalize_size(rec.get("size"))
    layout = normalize_layout(rec.get("layout"))
    if layout in ("half", "third", "quarter", "compact"):
        return 0.18
    if size == "large":
        return 0.16
    if size == "small":
        return 0.22
    if size == "compact":
        return 0.14
    return 0.25


def rec_can_shrink(rec: dict[str, Any]) -> bool:
    if "can_shrink" in rec:
        return parse_bool(rec.get("can_shrink"), default=True)
    if "shrink" in rec:
        return parse_bool(rec.get("shrink"), default=True)
    vtype = visual_type(rec)
    if "table" in vtype:
        return False
    return True


def rec_keep_with_next(rec: dict[str, Any]) -> bool:
    if "keep_with_next" in rec:
        return parse_bool(rec.get("keep_with_next"), default=True)
    if "keep" in rec:
        return parse_bool(rec.get("keep"), default=True)
    return normalize_layout(rec.get("layout")) == "full"


def rec_max_shrink_ratio(rec: dict[str, Any]) -> float:
    ratio = parse_float(rec.get("max_shrink_ratio"), default_max_shrink_ratio(rec))
    return min(max(ratio, 0.0), 0.35)
