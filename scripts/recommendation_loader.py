#!/usr/bin/env python3
"""
Recommendation input loading helpers for md2report assembly and validation.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable


PLAN_MARKER = "report-illustrator-plan:v2"


def read_file(path: str, encoding: str = "utf-8") -> str:
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "enabled", "ok"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return default


def normalize_recommendation_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict) and parse_bool(item.get("enabled", True))]
    if isinstance(data, dict):
        for key in ("recommendations", "items", "charts", "figures"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict) and parse_bool(item.get("enabled", True))]
        return [data] if parse_bool(data.get("enabled", True)) else []
    return []


def parse_storyboard_markdown(content: str) -> list[dict[str, Any]]:
    if PLAN_MARKER not in content and not re.search(r"^##\s+C\d+\b", content, flags=re.MULTILINE):
        return []

    items: list[dict[str, Any]] = []
    blocks = re.split(r"(?=^##\s+C\d+\b)", content, flags=re.MULTILINE)
    for block in blocks:
        header = re.match(r"^##\s+C(\d+)\b.*$", block.strip(), flags=re.MULTILINE)
        if not header:
            continue
        item: dict[str, Any] = {"id": header.group(1)}
        for raw_line in block.splitlines()[1:]:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("- "):
                continue
            if line.startswith("```"):
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            item[key] = value
        if parse_bool(item.get("enabled", True)):
            items.append(item)
    return items


def parse_json_blocks_from_markdown(content: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    blocks = re.findall(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.DOTALL)
    for block in blocks:
        text = block.strip()
        if not text or not re.match(r"^[\[{]", text):
            continue
        try:
            items.extend(normalize_recommendation_payload(json.loads(text)))
        except json.JSONDecodeError as exc:
            print(f"[WARN] RECOMMENDATIONS.md JSON 块解析失败：{exc}")
    return items


def resolve_recommendation_source(report_dir: str) -> dict[str, Any]:
    rec_json = os.path.join(report_dir, "RECOMMENDATIONS.json")
    normalized_json = os.path.join(report_dir, "RECOMMENDATIONS.normalized.json")
    rec_storyboard = os.path.join(report_dir, "RECOMMENDATIONS.storyboard.md")
    legacy_md = os.path.join(report_dir, "RECOMMENDATIONS.md")

    if os.path.exists(rec_json):
        return {"source": "RECOMMENDATIONS.json", "path": rec_json, "authoritative": True, "supported": True}
    if os.path.exists(normalized_json):
        return {
            "source": "RECOMMENDATIONS.normalized.json",
            "path": normalized_json,
            "authoritative": False,
            "supported": False,
            "reason": "missing_authoritative_json",
        }
    if os.path.exists(rec_storyboard):
        return {
            "source": "RECOMMENDATIONS.storyboard.md",
            "path": rec_storyboard,
            "authoritative": False,
            "supported": False,
            "reason": "derived_preview_only",
        }
    if os.path.exists(legacy_md):
        return {
            "source": "RECOMMENDATIONS.md",
            "path": legacy_md,
            "authoritative": False,
            "supported": False,
            "reason": "legacy_markdown_not_supported",
        }
    return {"source": "missing", "path": "", "authoritative": False, "supported": False, "reason": "missing"}


def parse_recommendations_base(
    report_dir: str,
    *,
    allow_derived_fallback: bool = False,
    emit_warning: Callable[[str], None] | None = print,
) -> list[dict[str, Any]]:
    source_info = resolve_recommendation_source(report_dir)
    source = source_info["source"]
    path = source_info["path"]

    if source == "RECOMMENDATIONS.json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return normalize_recommendation_payload(data)

    if source == "RECOMMENDATIONS.normalized.json":
        if allow_derived_fallback:
            if emit_warning is not None:
                emit_warning("[WARN] 缺少 RECOMMENDATIONS.json；当前仅回退使用派生文件 RECOMMENDATIONS.normalized.json")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return normalize_recommendation_payload(data)
        raise FileNotFoundError("缺少 RECOMMENDATIONS.json；RECOMMENDATIONS.normalized.json 只是派生产物，不能充当真实源")

    if source == "RECOMMENDATIONS.md":
        raise FileNotFoundError("仅检测到 RECOMMENDATIONS.md；当前 skill 已不再支持 Markdown 作为 recommendation 真实源")

    if source == "RECOMMENDATIONS.storyboard.md":
        raise FileNotFoundError("仅检测到 RECOMMENDATIONS.storyboard.md；该文件只是派生预览，不能充当 recommendation 真实源")

    raise FileNotFoundError("缺少 RECOMMENDATIONS.json；当前 skill 以 JSON 为唯一真实源")
