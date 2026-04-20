#!/usr/bin/env python3
"""
Build a machine-readable anchor index from content.html.

Usage:
  python3 scripts/build_anchor_index.py <report_dir>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from report_contract import normalize_anchor

HEADING_PATTERN = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", flags=re.IGNORECASE | re.DOTALL)


def build_anchor_index_from_html(content_html: str) -> dict[str, Any]:
    by_text_count: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    heading_number = 0

    for match in HEADING_PATTERN.finditer(content_html):
        heading_number += 1
        level = int(match.group(1))
        text = normalize_anchor(match.group(2))
        if not text:
            continue
        by_text_count[text] = by_text_count.get(text, 0) + 1
        occurrence = by_text_count[text]
        anchor_id = f"h{level}_{heading_number}"
        items.append(
            {
                "anchor_id": anchor_id,
                "level": level,
                "text": text,
                "normalized_text": text,
                "occurrence": occurrence,
                "start": match.start(),
                "end": match.end(),
            }
        )

    return {
        "schema": "report-illustrator-anchor-index:v1",
        "count": len(items),
        "items": items,
    }


def build_anchor_index(report_dir: Path) -> dict[str, Any]:
    content_path = report_dir / "content.html"
    if not content_path.exists():
        raise SystemExit(f"[ERROR] 找不到正文文件：{content_path}")
    payload = build_anchor_index_from_html(content_path.read_text(encoding="utf-8", errors="ignore"))
    output_path = report_dir / "ANCHOR_INDEX.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def load_anchor_index(report_dir: Path) -> dict[str, Any]:
    path = report_dir / "ANCHOR_INDEX.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            return payload
    return build_anchor_index(report_dir)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build md2report anchor index")
    parser.add_argument("report_dir", help="Report workspace directory")
    args = parser.parse_args(argv[1:])

    report_dir = Path(args.report_dir).expanduser().resolve()
    if not report_dir.exists() or not report_dir.is_dir():
        print(f"[ERROR] 报告目录不存在：{report_dir}")
        return 1

    payload = build_anchor_index(report_dir)
    print(f"[DONE] 锚点索引：{report_dir / 'ANCHOR_INDEX.json'}")
    print(f"[INFO] headings={payload.get('count', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
