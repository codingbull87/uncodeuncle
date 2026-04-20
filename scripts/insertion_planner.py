#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any, Callable


VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

TOP_LEVEL_SECTION_TAGS = {
    "blockquote",
    "div",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "ol",
    "p",
    "section",
    "table",
    "ul",
}


def iter_top_level_block_spans(content_html: str, start: int, end: int) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    stack: list[str] = []
    root_tag = ""
    root_start = -1
    tag_pattern = re.compile(r"<(/?)([a-zA-Z0-9]+)\b[^>]*?>", flags=re.IGNORECASE)

    for match in tag_pattern.finditer(content_html, start, end):
        closing = bool(match.group(1))
        tag = match.group(2).lower()
        token = match.group(0)
        self_closing = token.rstrip().endswith("/>") or tag in VOID_TAGS

        if tag in {"script", "style"}:
            if not closing and not self_closing:
                stack.append(tag)
            elif stack and stack[-1] == tag:
                stack.pop()
            continue

        if not closing:
            if not stack and tag in TOP_LEVEL_SECTION_TAGS:
                if self_closing:
                    spans.append((tag, match.start(), match.end()))
                    continue
                root_tag = tag
                root_start = match.start()
            if not self_closing:
                stack.append(tag)
            continue

        if not stack:
            continue

        popped = stack.pop()
        if popped != tag:
            while stack and stack[-1] != tag:
                stack.pop()
            if stack and stack[-1] == tag:
                stack.pop()

        if not stack and root_tag and tag == root_tag and root_start >= 0:
            spans.append((root_tag, root_start, match.end()))
            root_tag = ""
            root_start = -1

    return spans


def section_end_position(content_html: str, heading_match: re.Match[str]) -> int:
    section_start = heading_match.end()
    current_level = int(heading_match.group(1))
    spans = iter_top_level_block_spans(content_html, section_start, len(content_html))
    for tag, span_start, _ in spans:
        if re.fullmatch(r"h[1-6]", tag) and int(tag[1]) <= current_level:
            return span_start
    return len(content_html)


def first_top_level_paragraph_end(content_html: str, heading_match: re.Match[str]) -> int | None:
    section_start = heading_match.end()
    boundary = section_end_position(content_html, heading_match)
    spans = iter_top_level_block_spans(content_html, section_start, boundary)
    for tag, _, span_end in spans:
        if tag == "p":
            return span_end
    return None


def iter_heading_matches(
    content_html: str,
    anchor_text: str,
    *,
    strip_tags: Callable[[str], str],
) -> list[re.Match[str]]:
    exact_matches: list[re.Match[str]] = []
    contains_matches: list[re.Match[str]] = []
    heading_pattern = re.compile(r"<h([1-6])\b[^>]*>.*?</h\1>", flags=re.IGNORECASE | re.DOTALL)
    anchor_text = anchor_text.replace("\u201c", '"').replace("\u201d", '"')
    for match in heading_pattern.finditer(content_html):
        heading_text = strip_tags(match.group(0))
        heading_text_cmp = heading_text.replace("\u201c", '"').replace("\u201d", '"')
        if heading_text_cmp == anchor_text:
            exact_matches.append(match)
        elif anchor_text in heading_text_cmp:
            contains_matches.append(match)
    return exact_matches or contains_matches


def find_insert_position(
    content_html: str,
    heading_match: re.Match[str],
    position: str,
    cover_span: tuple[int, int] | None,
) -> int:
    pos = str(position or "").strip().lower()
    section_start = heading_match.end()
    section_boundary = section_end_position(content_html, heading_match)

    if cover_span and cover_span[0] <= heading_match.start() < cover_span[1]:
        if any(token in pos for token in ("before", "前", "标题前", "section-before")):
            return cover_span[0]
        return cover_span[1]

    if any(token in pos for token in ("after_cover", "cover_after", "封面后", "cover-end")) and cover_span:
        return cover_span[1]

    if any(token in pos for token in ("before", "前", "标题前", "section-before")):
        return heading_match.start()

    if any(token in pos for token in ("first paragraph", "首段", "第一段", "paragraph after", "after_first_paragraph")):
        para_end = first_top_level_paragraph_end(content_html, heading_match)
        if para_end is not None:
            return para_end

    if any(token in pos for token in ("section end", "章节末", "节末", "末尾", "section_end")):
        return section_boundary

    return section_start


def plan_insertions(
    content_html: str,
    fragment_map: dict[str, str],
    recommendations: list[dict[str, Any]],
    *,
    normalize_chart_id: Callable[[Any], str],
    normalize_anchor: Callable[[Any], str],
    parse_occurrence: Callable[[Any], int],
    has_renderable_fragment: Callable[[str], bool],
    get_cover_span: Callable[[str], tuple[int, int] | None],
    strip_tags: Callable[[str], str],
    planned_insertion_factory: Callable[[int, dict[str, Any], str, str, int], Any],
    injection_result_factory: Callable[[str, str, str, str], Any],
) -> tuple[list[Any], list[Any]]:
    results: list[Any] = []
    insertions: list[Any] = []
    cover_span = get_cover_span(content_html)

    for rec in recommendations:
        chart_id = normalize_chart_id(rec.get("id"))
        anchor_text = normalize_anchor(rec.get("group_anchor") or rec.get("row_anchor") or rec.get("anchor"))

        if not chart_id:
            results.append(injection_result_factory("", anchor_text, "WARN", "缺少 id，跳过"))
            continue
        if not anchor_text:
            results.append(injection_result_factory(chart_id, "", "WARN", "缺少 anchor，跳过"))
            continue

        fragment = fragment_map.get(chart_id)
        if fragment is None:
            results.append(injection_result_factory(chart_id, anchor_text, "WARN", "找不到对应片段，跳过"))
            continue
        if not has_renderable_fragment(fragment):
            results.append(injection_result_factory(chart_id, anchor_text, "WARN", "片段疑似空壳，跳过"))
            continue

        matches = iter_heading_matches(content_html, anchor_text, strip_tags=strip_tags)
        if not matches:
            fallback = normalize_anchor(rec.get("anchor_full"))
            if fallback and fallback != anchor_text:
                matches = iter_heading_matches(content_html, fallback, strip_tags=strip_tags)
                if matches:
                    anchor_text = fallback

        if not matches:
            results.append(injection_result_factory(chart_id, anchor_text, "WARN", "找不到锚点，跳过"))
            continue

        occurrence = parse_occurrence(rec.get("anchor_occurrence", rec.get("occurrence", 1)))
        if occurrence > len(matches):
            results.append(
                injection_result_factory(
                    chart_id,
                    anchor_text,
                    "WARN",
                    f"anchor_occurrence={occurrence} 超出匹配数量 {len(matches)}，跳过",
                )
            )
            continue

        heading_match = matches[occurrence - 1]
        insert_pos = find_insert_position(content_html, heading_match, str(rec.get("position", "")), cover_span)
        insertions.append(planned_insertion_factory(insert_pos, rec, fragment, anchor_text, len(matches)))
        results.append(
            injection_result_factory(
                chart_id,
                anchor_text,
                "OK",
                f"已规划注入第 {occurrence}/{len(matches)} 个锚点",
            )
        )

    return insertions, results
