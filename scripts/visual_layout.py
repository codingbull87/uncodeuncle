#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Callable


def row_should_equal_height(recs: list[dict[str, Any]], *, parse_bool: Callable[[Any, bool], bool]) -> bool:
    for rec in recs:
        if "equal_height" in rec:
            return parse_bool(rec.get("equal_height"), default=False)
        row_align = str(rec.get("row_align", "")).strip().lower()
        if row_align in ("stretch", "equal", "equal-height", "equal_height", "同高"):
            return True
    return False


def wrap_fragment(
    rec: dict[str, Any],
    fragment: str,
    *,
    normalize_chart_id: Callable[[Any], str],
    normalize_layout: Callable[[Any], str],
    normalize_size: Callable[[Any], str],
    parse_bool: Callable[[Any, bool], bool],
    infer_page_role: Callable[[dict[str, Any]], str],
    rec_keep_with_next: Callable[[dict[str, Any]], bool],
    rec_can_shrink: Callable[[dict[str, Any]], bool],
    rec_max_shrink_ratio: Callable[[dict[str, Any]], float],
    html_escape: Callable[[str], str],
    nested: bool = False,
) -> str:
    chart_id = normalize_chart_id(rec.get("id"))
    layout = normalize_layout(rec.get("layout"))
    size = normalize_size(rec.get("size"))
    vtype = str(rec.get("type", "")).strip()
    classes = ["visual-block", f"visual-{layout}", f"visual-size-{size}"]
    if parse_bool(rec.get("print_compact"), default=False):
        classes.append("page-fit-compact")
    if nested:
        classes.append("visual-block-nested")
    attrs = [
        f'class="{" ".join(classes)}"',
        f'data-chart-id="{html_escape(chart_id)}"',
        f'data-layout="{html_escape(layout)}"',
        f'data-size="{html_escape(size)}"',
        f'data-page-role="{html_escape(infer_page_role(rec))}"',
        f'data-keep-with-next="{str(rec_keep_with_next(rec)).lower()}"',
        f'data-can-shrink="{str(rec_can_shrink(rec)).lower()}"',
        f'data-max-shrink-ratio="{rec_max_shrink_ratio(rec):.2f}"',
        f'data-print-compact="{str(parse_bool(rec.get("print_compact"), default=False)).lower()}"',
    ]
    if vtype:
        attrs.append(f'data-visual-type="{html_escape(vtype)}"')
    return f'<div {" ".join(attrs)}>\n{fragment}\n</div>'


def diagnose_group_assembly(
    insertions: list[Any],
    *,
    normalize_layout: Callable[[Any], str],
    normalize_chart_id: Callable[[Any], str],
    injection_result_factory: Callable[[str, str, str, str], Any],
) -> list[Any]:
    grouped: dict[str, list[Any]] = {}
    for item in insertions:
        group = str(item.rec.get("group", "")).strip()
        layout = normalize_layout(item.rec.get("layout"))
        if group and layout in ("half", "third", "quarter", "compact"):
            grouped.setdefault(group, []).append(item)

    diagnostics: list[Any] = []
    for group, items in sorted(grouped.items()):
        if len(items) < 2:
            continue
        positions = {item.pos for item in items}
        if len(positions) > 1:
            chart_ids = ", ".join(normalize_chart_id(item.rec.get("id")) for item in items)
            anchors = "；".join(sorted({item.anchor for item in items}))
            diagnostics.append(
                injection_result_factory(
                    "GROUP",
                    group,
                    "WARN",
                    f"group 未形成并排：{chart_ids} 的插入位置不同。请使用共同 anchor/position 或显式 group_anchor。anchors={anchors}",
                )
            )
    return diagnostics


def build_insertion_html(
    insertions: list[Any],
    *,
    wrap_fragment_func: Callable[[dict[str, Any], str], str],
    wrap_nested_fragment_func: Callable[[dict[str, Any], str], str],
    normalize_layout: Callable[[Any], str],
    row_should_equal_height_func: Callable[[list[dict[str, Any]]], bool],
    html_escape: Callable[[str], str],
) -> str:
    pieces: list[str] = []
    used = [False] * len(insertions)

    for index, planned in enumerate(insertions):
        if used[index]:
            continue
        rec = planned.rec
        group = str(rec.get("group", "")).strip()
        layout = str(rec.get("layout", "full")).strip().lower()

        if group and layout in ("half", "third", "quarter", "compact"):
            members = [
                (i, item)
                for i, item in enumerate(insertions)
                if not used[i]
                and item.pos == planned.pos
                and str(item.rec.get("group", "")).strip() == group
            ]
            if len(members) >= 2:
                layouts = {str(item.rec.get("layout", "")).lower() for _, item in members}
                if "quarter" in layouts and len(members) >= 4:
                    row_layout = "quarter"
                elif "third" in layouts and len(members) >= 3:
                    row_layout = "third"
                else:
                    row_layout = "half"
                row_title = str(rec.get("row_title", "") or rec.get("group_title", "")).strip()
                row_classes = ["visual-row", f"visual-row-{row_layout}"]
                equal_height = row_should_equal_height_func([item.rec for _, item in members])
                if equal_height:
                    row_classes.append("visual-row-equal")
                row_attrs = [
                    f'class="{" ".join(row_classes)}"',
                    f'data-group="{html_escape(group)}"',
                    f'data-row-layout="{row_layout}"',
                    f'data-equal-height="{str(equal_height).lower()}"',
                    'data-page-role="paired_visual"',
                    'data-can-shrink="true"',
                    'data-max-shrink-ratio="0.18"',
                ]
                row = [f'<div {" ".join(row_attrs)}>']
                if row_title:
                    row.append(f'  <div class="visual-row-title">{html_escape(row_title)}</div>')
                for member_index, member in members:
                    used[member_index] = True
                    row.append(wrap_nested_fragment_func(member.rec, member.fragment))
                row.append("</div>")
                pieces.append("\n".join(row))
                continue

        used[index] = True
        pieces.append(wrap_fragment_func(rec, planned.fragment))

    return "\n".join(pieces)


def build_layout_plan(
    insertions: list[Any],
    *,
    layout_block_factory: Callable[..., Any],
    normalize_chart_id: Callable[[Any], str],
    normalize_layout: Callable[[Any], str],
    normalize_size: Callable[[Any], str],
    infer_page_role: Callable[[dict[str, Any]], str],
    rec_keep_with_next: Callable[[dict[str, Any]], bool],
    rec_can_shrink: Callable[[dict[str, Any]], bool],
    rec_max_shrink_ratio: Callable[[dict[str, Any]], float],
    row_should_equal_height_func: Callable[[list[dict[str, Any]]], bool],
) -> dict[str, Any]:
    blocks: list[Any] = []
    used = [False] * len(insertions)

    for index, planned in enumerate(insertions):
        if used[index]:
            continue
        rec = planned.rec
        group = str(rec.get("group", "")).strip()
        layout = normalize_layout(rec.get("layout"))

        if group and layout in ("half", "third", "quarter", "compact"):
            members = [
                (i, item)
                for i, item in enumerate(insertions)
                if not used[i]
                and item.pos == planned.pos
                and str(item.rec.get("group", "")).strip() == group
            ]
            if len(members) >= 2:
                layouts = {normalize_layout(item.rec.get("layout")) for _, item in members}
                if "quarter" in layouts and len(members) >= 4:
                    row_layout = "quarter"
                elif "third" in layouts and len(members) >= 3:
                    row_layout = "third"
                else:
                    row_layout = "half"
                equal_height = row_should_equal_height_func([item.rec for _, item in members])
                member_ids = [normalize_chart_id(item.rec.get("id")) for _, item in members]
                for member_index, _ in members:
                    used[member_index] = True
                blocks.append(
                    layout_block_factory(
                        block_id="+".join(member_ids),
                        kind="visual-row",
                        anchor=planned.anchor,
                        layout=row_layout,
                        size="small",
                        page_role="paired_visual",
                        keep_with_next=False,
                        can_shrink=True,
                        max_shrink_ratio=0.18,
                        group=group,
                        row_layout=row_layout,
                        equal_height=equal_height,
                    )
                )
                continue

        used[index] = True
        blocks.append(
            layout_block_factory(
                block_id=normalize_chart_id(rec.get("id")),
                kind="visual-block",
                anchor=planned.anchor,
                layout=layout,
                size=normalize_size(rec.get("size")),
                page_role=infer_page_role(rec),
                keep_with_next=rec_keep_with_next(rec),
                can_shrink=rec_can_shrink(rec),
                max_shrink_ratio=rec_max_shrink_ratio(rec),
                group=group,
            )
        )

    return {
        "schema": "report-illustrator-layout-plan:v1",
        "notes": "机器生成的页面级排版计划骨架；当前用于 HTML data-* 标记和 PDF 微调护栏。",
        "rules": {
            "ordinary_page_bottom_blank_target": 0.18,
            "figure_page_bottom_blank_target": 0.22,
            "chapter_break_allows_large_blank": True,
            "max_chart_shrink_ratio_default": 0.25,
        },
        "blocks": [block.__dict__ for block in blocks],
    }
