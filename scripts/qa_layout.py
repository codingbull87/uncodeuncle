#!/usr/bin/env python3
"""
Diagnose print-layout quality from actual PDF page placement.

- Builds a DOM registry with stable block ids.
- Injects block markers into a temporary HTML and exports a temporary PDF.
- Maps each block back to real printed pages using marker positions from the PDF.
- Flags sparse pages and emits bounded repair suggestions.

Usage:
  python3 scripts/qa_layout.py <html_path> [output_json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from layout_probe import build_probe_payload


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


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def compact_state(block: dict[str, Any]) -> int:
    score = 0
    if str(block.get("layout", "")).strip().lower() == "compact":
        score += 2
    if str(block.get("size", "")).strip().lower() in {"small", "compact"}:
        score += 1
    if truthy(str(block.get("printCompact", ""))):
        score += 1
    return score


def block_ref(block: dict[str, Any] | None) -> dict[str, Any] | None:
    if not block:
        return None
    keys = [
        "blockId",
        "domIndex",
        "kind",
        "tag",
        "chartId",
        "memberChartIds",
        "layout",
        "size",
        "pageRole",
        "visualType",
        "text",
        "pdfPageStart",
        "pdfPageEnd",
        "pdfLocalTop",
        "pdfLocalBottom",
        "canShrink",
        "keepWithNext",
        "printCompact",
    ]
    return {key: block.get(key) for key in keys if key in block}


def blocks_on_page(blocks: list[dict[str, Any]], page: int) -> list[dict[str, Any]]:
    return [
        block for block in blocks
        if int(block.get("pdfPageStart", 0)) <= page <= int(block.get("pdfPageEnd", 0))
    ]


def local_top(block: dict[str, Any], page: int) -> float:
    if int(block.get("pdfPageStart", 0)) == page:
        return float(block.get("pdfLocalTop", 0.0))
    return 0.0


def local_bottom(block: dict[str, Any], page: int, page_height_px: int) -> float:
    start_page = int(block.get("pdfPageStart", 0))
    end_page = int(block.get("pdfPageEnd", 0))
    if start_page <= page < end_page:
        return float(page_height_px)
    return float(block.get("pdfLocalBottom", 0.0))


def trailing_visual(blocks: list[dict[str, Any]], page: int, page_height_px: int) -> dict[str, Any] | None:
    visuals = [block for block in blocks if str(block.get("kind", "")).startswith("visual")]
    if not visuals:
        return None
    return max(visuals, key=lambda block: (local_bottom(block, page, page_height_px), int(block.get("domIndex", 0))))


def first_visual(blocks: list[dict[str, Any]], page: int) -> dict[str, Any] | None:
    visuals = [block for block in blocks if str(block.get("kind", "")).startswith("visual")]
    if not visuals:
        return None
    return min(visuals, key=lambda block: (local_top(block, page), int(block.get("domIndex", 0))))


def first_block(blocks: list[dict[str, Any]], page: int) -> dict[str, Any] | None:
    if not blocks:
        return None
    return min(blocks, key=lambda block: (local_top(block, page), int(block.get("domIndex", 0))))


def has_following_text_after_visual(page_blocks: list[dict[str, Any]], visual: dict[str, Any]) -> bool:
    after = False
    visual_index = int(visual.get("domIndex", -1))
    for block in sorted(page_blocks, key=lambda item: int(item.get("domIndex", 0))):
        dom_index = int(block.get("domIndex", 0))
        if dom_index <= visual_index:
            continue
        tag = str(block.get("tag", "")).strip().lower()
        if tag in {"h1", "h2", "h3"}:
            return after
        if str(block.get("kind", "")) == "text" and tag in {"p", "ul", "ol", "table", "blockquote"}:
            after = True
    return after


def diagnose(payload: dict[str, Any]) -> dict[str, Any]:
    blocks = sorted(payload.get("blocks", []), key=lambda item: int(item.get("domIndex", 0)))
    pages = sorted(payload.get("pages", []), key=lambda item: int(item.get("page", 0)))
    page_height_px = int(payload.get("pageHeightPx", 0) or 1)

    sparse_pages: list[dict[str, Any]] = []
    terminal_sparse_pages: list[dict[str, Any]] = []
    last_page = max((int(page.get("page", 0)) for page in pages), default=0)
    for page in pages:
        index = int(page.get("page", 0))
        blank_ratio = float(page.get("blankRatio", 0))
        if index == last_page or blank_ratio <= 0.38:
            continue

        current_blocks = blocks_on_page(blocks, index)
        next_blocks = blocks_on_page(blocks, index + 1)
        trailing_block = max(
            current_blocks,
            key=lambda block: (local_bottom(block, index, page_height_px), int(block.get("domIndex", 0))),
            default=None,
        )
        trailing_page_visual = trailing_visual(current_blocks, index, page_height_px)
        next_first_block = first_block(next_blocks, index + 1)
        next_first_visual = first_visual(next_blocks, index + 1)

        suggestions: list[dict[str, Any]] = []
        reason_parts: list[str] = []

        if next_first_block and str(next_first_block.get("tag", "")).lower() in {"h2", "h3"} and local_top(next_first_block, index + 1) <= 90:
            reason_parts.append("next page begins with heading")
        if trailing_block and str(trailing_block.get("tag", "")).lower() in {"h2", "h3"}:
            reason_parts.append("current page ends on heading")

        if trailing_page_visual:
            if truthy(str(trailing_page_visual.get("canShrink", ""))):
                suggestions.append({
                    "action": "compact_trailing_visual",
                    "target_block_id": trailing_page_visual.get("blockId", ""),
                    "target_chart_id": trailing_page_visual.get("chartId", ""),
                    "target_member_chart_ids": trailing_page_visual.get("memberChartIds", []),
                    "reason": "last visual on sparse page can shrink",
                })
            vtype = str(trailing_page_visual.get("visualType", "")).strip().lower()
            if vtype in LOW_INFO_TYPES and has_following_text_after_visual(current_blocks, trailing_page_visual):
                suggestions.append({
                    "action": "move_trailing_visual_to_section_end",
                    "target_block_id": trailing_page_visual.get("blockId", ""),
                    "target_chart_id": trailing_page_visual.get("chartId", ""),
                    "target_member_chart_ids": trailing_page_visual.get("memberChartIds", []),
                    "reason": "low-info visual has following text in same section",
                })
            if str(trailing_page_visual.get("kind", "")) == "visual-row" and trailing_page_visual.get("memberChartIds"):
                suggestions.append({
                    "action": "split_trailing_row",
                    "target_block_id": trailing_page_visual.get("blockId", ""),
                    "target_chart_id": trailing_page_visual.get("chartId", ""),
                    "target_member_chart_ids": trailing_page_visual.get("memberChartIds", []),
                    "reason": "paired visual row is last visual on sparse page",
                })
        if next_first_visual and truthy(str(next_first_visual.get("canShrink", ""))):
            suggestions.append({
                "action": "compact_next_visual",
                "target_block_id": next_first_visual.get("blockId", ""),
                "target_chart_id": next_first_visual.get("chartId", ""),
                "target_member_chart_ids": next_first_visual.get("memberChartIds", []),
                "reason": "next page begins with a shrinkable visual",
            })

        if trailing_page_visual and compact_state(trailing_page_visual) >= 2:
            reason_parts.append("trailing visual already compact")
        if trailing_page_visual and str(trailing_page_visual.get("visualType", "")).strip().lower() in LOW_INFO_TYPES:
            reason_parts.append("trailing visual is low-info figure")

        sparse_pages.append({
            "page": index,
            "blankRatio": blank_ratio,
            "blankPx": int(page.get("blankPx", 0)),
            "usedPx": int(page.get("usedPx", 0)),
            "textChars": int(page.get("textChars", 0)),
            "reason": "; ".join(reason_parts) if reason_parts else "print-page usage indicates sparse page",
            "trailing_block": block_ref(trailing_block),
            "trailing_visual": block_ref(trailing_page_visual),
            "next_page_first_block": block_ref(next_first_block),
            "next_page_first_visual": block_ref(next_first_visual),
            "pageBlocks": [block_ref(block) for block in current_blocks],
            "suggestions": suggestions,
        })

    if last_page:
        last_page_item = next((page for page in pages if int(page.get("page", 0)) == last_page), None)
        prev_page_item = next((page for page in pages if int(page.get("page", 0)) == last_page - 1), None)
        if last_page_item:
            last_blank = float(last_page_item.get("blankRatio", 0))
            last_blocks = int(last_page_item.get("blockCount", 0))
            if last_blank > 0.55 and last_blocks <= 4 and prev_page_item:
                prev_blocks = blocks_on_page(blocks, last_page - 1)
                terminal_blocks = blocks_on_page(blocks, last_page)
                prev_trailing_visual = trailing_visual(prev_blocks, last_page - 1, page_height_px)
                first_terminal_block = first_block(terminal_blocks, last_page)
                suggestions: list[dict[str, Any]] = []
                reason_parts: list[str] = ["terminal page is underfilled"]
                if prev_trailing_visual and truthy(str(prev_trailing_visual.get("canShrink", ""))):
                    suggestions.append({
                        "action": "compact_prev_page_visual",
                        "target_block_id": prev_trailing_visual.get("blockId", ""),
                        "target_chart_id": prev_trailing_visual.get("chartId", ""),
                        "target_member_chart_ids": prev_trailing_visual.get("memberChartIds", []),
                        "reason": "previous page trailing visual can absorb terminal text overflow",
                    })
                    if str(prev_trailing_visual.get("visualType", "")).strip().lower() in LOW_INFO_TYPES:
                        reason_parts.append("previous trailing visual is low-info")
                terminal_sparse_pages.append({
                    "page": last_page,
                    "blankRatio": last_blank,
                    "blankPx": int(last_page_item.get("blankPx", 0)),
                    "usedPx": int(last_page_item.get("usedPx", 0)),
                    "textChars": int(last_page_item.get("textChars", 0)),
                    "reason": "; ".join(reason_parts),
                    "previous_page_trailing_visual": block_ref(prev_trailing_visual),
                    "first_terminal_block": block_ref(first_terminal_block),
                    "pageBlocks": [block_ref(block) for block in terminal_blocks],
                    "suggestions": suggestions,
                })

    payload["blocks"] = blocks
    payload["pages"] = pages
    payload["sparsePages"] = sparse_pages
    payload["terminalSparsePages"] = terminal_sparse_pages
    payload["summary"] = {
        "totalPages": len(pages),
        "sparsePages": len(sparse_pages),
        "terminalSparsePages": len(terminal_sparse_pages),
        "maxBlankRatio": max((float(page.get("blankRatio", 0)) for page in pages), default=0.0),
        "missingMarkers": len(payload.get("missingMarkers", [])),
    }
    return payload


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Diagnose print layout via actual PDF page mapping")
    parser.add_argument("html_path", help="Assembled report HTML path")
    parser.add_argument("output_json", nargs="?", help="Optional output JSON path")
    args = parser.parse_args(argv[1:])

    html_path = Path(args.html_path).expanduser().resolve()
    if not html_path.exists():
        print(f"[ERROR] 找不到 HTML：{html_path}")
        return 1

    payload = diagnose(build_probe_payload(html_path))
    output_path = Path(args.output_json).expanduser().resolve() if args.output_json else html_path.with_name("LAYOUT_DIAGNOSIS.json")
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[LAYOUT_QA] html={html_path}")
    print(f"[LAYOUT_QA] output={output_path}")
    summary = payload.get("summary", {})
    print(
        f"[LAYOUT_QA] pages={summary.get('totalPages', 0)} "
        f"sparse_pages={summary.get('sparsePages', 0)} "
        f"terminal_sparse_pages={summary.get('terminalSparsePages', 0)} "
        f"max_blank={summary.get('maxBlankRatio', 0):.0%}"
    )
    missing_markers = payload.get("missingMarkers", [])
    if missing_markers:
        preview = ", ".join(missing_markers[:8])
        suffix = " ..." if len(missing_markers) > 8 else ""
        print(f"[WARN] 缺少 PDF marker 的 block: {preview}{suffix}")
    for item in payload.get("sparsePages", []):
        print(
            f"[WARN] 第 {item.get('page')} 页空白约 {float(item.get('blankRatio', 0)):.0%} "
            f"/ {item.get('reason', '')}"
        )
    for item in payload.get("terminalSparsePages", []):
        print(
            f"[WARN] 末页 {item.get('page')} 空白约 {float(item.get('blankRatio', 0)):.0%} "
            f"/ {item.get('reason', '')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
