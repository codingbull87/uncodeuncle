#!/usr/bin/env python3
"""
Report Illustrator - Phase 3 assembler

Usage:
  python3 scripts/assemble.py <report_dir> <output_name>

Inputs in report_dir:
  - content.html
  - RECOMMENDATIONS.md or RECOMMENDATIONS.json
  - chart-fragments/C{id}.html

Output:
  - {output_name}.html
"""

from __future__ import annotations

import glob
import html as html_lib
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any


PLAN_MARKER = "report-illustrator-plan:v2"

BLOCK_TAGS = (
    "article",
    "aside",
    "blockquote",
    "canvas",
    "div",
    "figure",
    "figcaption",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "ol",
    "pre",
    "script",
    "section",
    "style",
    "svg",
    "table",
    "ul",
)


@dataclass
class InjectionResult:
    chart_id: str
    anchor: str
    status: str
    message: str


@dataclass
class PlannedInsertion:
    pos: int
    rec: dict[str, Any]
    fragment: str
    anchor: str
    match_count: int


def read_file(path: str, encoding: str = "utf-8") -> str:
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def write_file(path: str, content: str, encoding: str = "utf-8") -> None:
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


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
    return strip_tags(text)


def parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("false", "no", "off", "0", "disabled", "skip", "否", "停用"):
        return False
    if text in ("true", "yes", "on", "1", "enabled", "是", "启用"):
        return True
    return default


def parse_occurrence(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 1
    return max(number, 1)


def unwrap_single_markdown_paragraph(html: str) -> str:
    block = "|".join(BLOCK_TAGS)
    html = re.sub(
        rf"<p>\s*(</?(?:{block})(?:\s|>|/))",
        r"\1",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        rf"(</(?:{block})>)\s*</p>",
        r"\1",
        html,
        flags=re.IGNORECASE,
    )
    return html


def remove_download_artifacts(html: str) -> str:
    html = re.sub(
        r"<button\b[^>]*(?:chart-download|download)[^>]*>.*?</button>",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html = re.sub(
        r"<button\b[^>]*>.*?(?:下载|download).*?</button>",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html = re.sub(
        r"window\.downloadChart\s*=\s*function\s*\([^)]*\)\s*\{.*?\}\s*;?",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html = re.sub(
        r"function\s+downloadChart\s*\([^)]*\)\s*\{.*?\}\s*",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return html


def unquote_common_formatter_functions(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        prefix = match.group(1)
        fn = match.group(2)
        try:
            fn = json.loads('"' + fn + '"')
        except json.JSONDecodeError:
            fn = fn.replace(r"\"", '"').replace(r"\n", "\n").replace(r"\t", "\t")
        return prefix + fn

    return re.sub(
        r'((?:"|\')formatter(?:"|\')\s*:\s*)"(function\s*\([^)]*\)\s*\{.*?\})"',
        replace,
        html,
        flags=re.DOTALL,
    )


def scrub_placeholder_sources(html: str) -> str:
    source_prefix = re.compile(r"^\s*数据来源[:：]\s*", flags=re.IGNORECASE)
    internal_source_phrase = re.compile(
        r"(报告(?:正文|执行摘要)?整理|正文整理|执行摘要整理|报告内(?:部)?整理|基于报告(?:正文|执行摘要)?整理|根据报告(?:正文|执行摘要)?整理)",
        flags=re.IGNORECASE,
    )
    internal_only_source = re.compile(
        r"^(?:数据来源[:：]\s*)?(?:报告正文|报告执行摘要|执行摘要|正文|本报告|原文)\s*$",
        flags=re.IGNORECASE,
    )
    report_internal_hint = re.compile(r"(报告正文|执行摘要|本文|本报告|原文)", flags=re.IGNORECASE)
    tidy_hint = re.compile(r"(整理|汇总|提炼|归纳|抽取|改写|生成)", flags=re.IGNORECASE)
    explicit_external_hint = re.compile(
        r"(年报|季报|财报|公告|招股书|wind|bloomberg|factset|同花顺|choice|ifind|国家统计局|工信部|发改委|证监会|交易所|公司披露|press release|earnings call|10-k|10-q)",
        flags=re.IGNORECASE,
    )

    def normalize_piece(text: str) -> str:
        cleaned = strip_tags(text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" |｜;；")
        return cleaned

    def is_internal_source(piece: str) -> bool:
        text = source_prefix.sub("", piece).strip()
        if not text:
            return True
        if explicit_external_hint.search(text):
            return False
        if internal_only_source.match(text):
            return True
        if internal_source_phrase.search(text):
            return True
        if report_internal_hint.search(text) and tidy_hint.search(text):
            return True
        return False

    def replace(match: re.Match[str]) -> str:
        attrs = match.group(1)
        body = match.group(2)
        pieces = [normalize_piece(piece) for piece in re.split(r"[|｜]", body)]
        filtered: list[str] = []
        for piece in pieces:
            if not piece:
                continue
            if is_internal_source(piece):
                continue
            filtered.append(piece)
        if not filtered:
            return ""
        text = " | ".join(filtered)
        return f'<div{attrs}>{html_lib.escape(text)}</div>'

    return re.sub(
        r'<div([^>]*class="[^"]*(?:chart-src|figure-src|component-src)[^"]*"[^>]*)>(.*?)</div>',
        replace,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def clean_fragment(fragment_html: str) -> str:
    fragment_html = unwrap_single_markdown_paragraph(fragment_html)
    fragment_html = remove_download_artifacts(fragment_html)
    fragment_html = unquote_common_formatter_functions(fragment_html)
    fragment_html = scrub_placeholder_sources(fragment_html)
    return fragment_html.strip()


def parse_recommendations(report_dir: str) -> list[dict[str, Any]]:
    rec_md = os.path.join(report_dir, "RECOMMENDATIONS.md")
    if os.path.exists(rec_md):
        content = read_file(rec_md)
        storyboard_items = parse_storyboard_markdown(content)
        if storyboard_items:
            return storyboard_items

    rec_json = os.path.join(report_dir, "RECOMMENDATIONS.json")
    if os.path.exists(rec_json):
        with open(rec_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        return normalize_recommendation_payload(data)

    if os.path.exists(rec_md):
        return parse_json_blocks_from_markdown(read_file(rec_md))

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


def normalize_recommendation_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict) and parse_bool(item.get("enabled", True))]
    if isinstance(data, dict):
        for key in ("recommendations", "items", "charts", "figures"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict) and parse_bool(item.get("enabled", True))]
        return [data] if parse_bool(data.get("enabled", True)) else []
    return []


def load_fragments(fragments_dir: str) -> dict[str, str]:
    fragment_map: dict[str, str] = {}
    pattern = os.path.join(fragments_dir, "C*.html")
    for fpath in sorted(glob.glob(pattern), key=fragment_sort_key):
        chart_id = normalize_chart_id(os.path.splitext(os.path.basename(fpath))[0])
        fragment_map[chart_id] = clean_fragment(read_file(fpath))
        print(f"[OK] 清洗片段：{chart_id}")
    return fragment_map


def fragment_sort_key(path: str) -> tuple[int, str]:
    name = os.path.basename(path)
    match = re.search(r"C(\d+)", name, flags=re.IGNORECASE)
    if match:
        return (int(match.group(1)), name)
    return (10**9, name)


def has_renderable_fragment(fragment: str) -> bool:
    return bool(re.search(r"echarts\.init|<svg\b|<table\b|kpi-val|consulting-|class=\"(?:scorecard|driver-tree|range-band)", fragment, re.I))


def normalize_cover_content(content_html: str) -> str:
    if 'class="report-cover"' in content_html:
        return content_html

    pattern = re.compile(
        r"^\s*(<h1\b[^>]*>.*?</h1>)\s*(<blockquote\b[^>]*>.*?</blockquote>)?\s*(<hr\s*/?>)?",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(content_html)
    if not match:
        return content_html

    h1_html = match.group(1)
    blockquote_html = match.group(2) or ""
    meta_html = build_report_meta(blockquote_html) if blockquote_html else ""
    cover = f'<section class="report-cover">\n{h1_html}\n{meta_html}\n</section>\n'
    return cover + content_html[match.end():]


def build_report_meta(blockquote_html: str) -> str:
    text = blockquote_html
    pairs: list[tuple[str, str]] = []
    pattern = re.compile(r"<strong>(.*?)</strong>\s*:?\s*(.*?)(?=<strong>|</p>|</blockquote>|$)", re.I | re.DOTALL)
    for key, value in pattern.findall(text):
        clean_key = strip_tags(key)
        clean_value = strip_tags(value).strip(" :：")
        if clean_key and clean_value:
            pairs.append((clean_key, clean_value))

    if not pairs:
        clean = strip_tags(blockquote_html)
        return f'<div class="report-meta report-meta-freeform">{html_lib.escape(clean)}</div>'

    spans = []
    for key, value in pairs:
        spans.append(f'<span class="report-meta-key">{html_lib.escape(key)}</span>')
        spans.append(f'<span class="report-meta-value">{html_lib.escape(value)}</span>')
    return '<div class="report-meta">\n' + "\n".join(spans) + "\n</div>"


def get_cover_span(content_html: str) -> tuple[int, int] | None:
    match = re.search(r"<section\b[^>]*class=[\"'][^\"']*report-cover[^\"']*[\"'][^>]*>.*?</section>", content_html, flags=re.I | re.DOTALL)
    if match:
        return (match.start(), match.end())
    return None


def iter_heading_matches(content_html: str, anchor_text: str) -> list[re.Match[str]]:
    exact_matches: list[re.Match[str]] = []
    contains_matches: list[re.Match[str]] = []
    heading_pattern = re.compile(r"<h([1-4])\b[^>]*>.*?</h\1>", flags=re.IGNORECASE | re.DOTALL)
    for match in heading_pattern.finditer(content_html):
        heading_text = strip_tags(match.group(0))
        if heading_text == anchor_text:
            exact_matches.append(match)
        elif anchor_text in heading_text:
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

    if cover_span and cover_span[0] <= heading_match.start() < cover_span[1]:
        if any(token in pos for token in ("before", "前", "标题前", "section-before")):
            return cover_span[0]
        return cover_span[1]

    if any(token in pos for token in ("after_cover", "cover_after", "封面后", "cover-end")) and cover_span:
        return cover_span[1]

    if any(token in pos for token in ("before", "前", "标题前", "section-before")):
        return heading_match.start()

    if any(token in pos for token in ("first paragraph", "首段", "第一段", "paragraph after", "after_first_paragraph")):
        para = re.search(r"<p\b[^>]*>.*?</p>", content_html[section_start:], flags=re.IGNORECASE | re.DOTALL)
        if para:
            return section_start + para.end()

    if any(token in pos for token in ("section end", "章节末", "节末", "末尾", "section_end")):
        next_heading = re.search(r"<h[1-3]\b[^>]*>", content_html[section_start:], flags=re.IGNORECASE)
        if next_heading:
            return section_start + next_heading.start()
        return len(content_html)

    return section_start


def plan_insertions(
    content_html: str,
    fragment_map: dict[str, str],
    recommendations: list[dict[str, Any]],
) -> tuple[list[PlannedInsertion], list[InjectionResult]]:
    results: list[InjectionResult] = []
    insertions: list[PlannedInsertion] = []
    cover_span = get_cover_span(content_html)

    for rec in recommendations:
        chart_id = normalize_chart_id(rec.get("id"))
        anchor_text = normalize_anchor(rec.get("anchor"))

        if not chart_id:
            results.append(InjectionResult("", anchor_text, "WARN", "缺少 id，跳过"))
            continue
        if not anchor_text:
            results.append(InjectionResult(chart_id, "", "WARN", "缺少 anchor，跳过"))
            continue

        fragment = fragment_map.get(chart_id)
        if fragment is None:
            results.append(InjectionResult(chart_id, anchor_text, "WARN", "找不到对应片段，跳过"))
            continue
        if not has_renderable_fragment(fragment):
            results.append(InjectionResult(chart_id, anchor_text, "WARN", "片段疑似空壳，跳过"))
            continue

        matches = iter_heading_matches(content_html, anchor_text)
        if not matches:
            fallback = normalize_anchor(rec.get("anchor_full"))
            if fallback and fallback != anchor_text:
                matches = iter_heading_matches(content_html, fallback)
                if matches:
                    anchor_text = fallback

        if not matches:
            results.append(InjectionResult(chart_id, anchor_text, "WARN", "找不到锚点，跳过"))
            continue

        occurrence = parse_occurrence(rec.get("anchor_occurrence", rec.get("occurrence", 1)))
        if occurrence > len(matches):
            results.append(
                InjectionResult(
                    chart_id,
                    anchor_text,
                    "WARN",
                    f"anchor_occurrence={occurrence} 超出匹配数量 {len(matches)}，跳过",
                )
            )
            continue

        heading_match = matches[occurrence - 1]
        insert_pos = find_insert_position(content_html, heading_match, str(rec.get("position", "")), cover_span)
        insertions.append(PlannedInsertion(insert_pos, rec, fragment, anchor_text, len(matches)))
        results.append(InjectionResult(chart_id, anchor_text, "OK", f"已规划注入第 {occurrence}/{len(matches)} 个锚点"))

    return insertions, results


def build_insertion_html(insertions: list[PlannedInsertion]) -> str:
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
                if row_should_equal_height([item.rec for _, item in members]):
                    row_classes.append("visual-row-equal")
                row = [f'<div class="{" ".join(row_classes)}" data-group="{html_lib.escape(group)}">']
                if row_title:
                    row.append(f'  <div class="visual-row-title">{html_lib.escape(row_title)}</div>')
                for member_index, member in members:
                    used[member_index] = True
                    row.append(wrap_fragment(member.rec, member.fragment, nested=True))
                row.append("</div>")
                pieces.append("\n".join(row))
                continue

        used[index] = True
        pieces.append(wrap_fragment(rec, planned.fragment))

    return "\n".join(pieces)


def row_should_equal_height(recs: list[dict[str, Any]]) -> bool:
    for rec in recs:
        if parse_bool(rec.get("equal_height"), default=False):
            return True
        row_align = str(rec.get("row_align", "")).strip().lower()
        if row_align in ("stretch", "equal", "equal-height", "equal_height", "同高"):
            return True
    return False


def wrap_fragment(rec: dict[str, Any], fragment: str, nested: bool = False) -> str:
    chart_id = normalize_chart_id(rec.get("id"))
    layout = str(rec.get("layout", "full")).strip().lower() or "full"
    size = str(rec.get("size", "medium")).strip().lower() or "medium"
    vtype = str(rec.get("type", "")).strip()
    classes = ["visual-block", f"visual-{layout}", f"visual-size-{size}"]
    if nested:
        classes.append("visual-block-nested")
    attrs = [
        f'class="{" ".join(classes)}"',
        f'data-chart-id="{html_lib.escape(chart_id)}"',
    ]
    if vtype:
        attrs.append(f'data-visual-type="{html_lib.escape(vtype)}"')
    return f'<div {" ".join(attrs)}>\n{fragment}\n</div>'


def inject_charts_into_content(
    content_html: str,
    fragment_map: dict[str, str],
    recommendations: list[dict[str, Any]],
) -> tuple[str, list[InjectionResult]]:
    insertions, results = plan_insertions(content_html, fragment_map, recommendations)
    by_pos: dict[int, list[PlannedInsertion]] = {}
    for item in insertions:
        by_pos.setdefault(item.pos, []).append(item)

    for pos in sorted(by_pos.keys(), reverse=True):
        insertion_html = "\n" + build_insertion_html(by_pos[pos]) + "\n"
        content_html = content_html[:pos] + insertion_html + content_html[pos:]

    return content_html, results


def build_html(report_dir: str, output_name: str) -> None:
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fragments_dir = os.path.join(report_dir, "chart-fragments")
    content_path = os.path.join(report_dir, "content.html")
    css_path = os.path.join(skill_dir, "templates", "static", "base-styles.css")
    js_path = os.path.join(skill_dir, "templates", "static", "pdf-export.js")
    output_path = os.path.join(report_dir, output_name + ".html")

    if not os.path.exists(content_path):
        print(f"[ERROR] 找不到正文文件：{content_path}")
        sys.exit(1)

    recommendations = parse_recommendations(report_dir)
    fragment_map = load_fragments(fragments_dir) if os.path.isdir(fragments_dir) else {}

    if recommendations and not fragment_map:
        print(f"[WARN] 找不到片段目录或片段文件：{fragments_dir}")

    content_html = normalize_cover_content(read_file(content_path))
    content_with_charts, injection_results = inject_charts_into_content(content_html, fragment_map, recommendations)

    report_title = extract_report_title(content_with_charts, output_name)
    base_css = read_file(css_path)
    pdf_js = read_file(js_path)

    final_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_lib.escape(report_title)}</title>
  <style>
{base_css}
  </style>
  <script src="libs/echarts.min.js"></script>
</head>
<body>
  <main class="page">
{content_with_charts}
  </main>
  <button id="pdf-export-btn" type="button">打印 / 导出 PDF</button>
  <script>
{pdf_js}
  </script>
</body>
</html>
"""

    write_file(output_path, final_html)
    print(f"[DONE] 输出文件：{output_path}")
    print_validation_summary(output_path, injection_results, len(recommendations), len(fragment_map))


def extract_report_title(content_html: str, fallback: str) -> str:
    title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", content_html, flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        title = strip_tags(title_match.group(1))
        if title:
            return title
    return fallback


def print_validation_summary(
    output_path: str,
    injection_results: list[InjectionResult],
    recommendation_count: int,
    fragment_count: int,
) -> None:
    final = read_file(output_path)
    residual_p_block = len(re.findall(r"<p>\s*<(?:div|script|table|svg)", final, re.IGNORECASE))
    residual_download = len(re.findall(r"chart-download|downloadChart|html2canvas|jspdf", final, re.IGNORECASE))
    duplicate_ids = find_duplicate_chart_ids(final)
    visual_rows = len(re.findall(r'<div\s+class="visual-row(?:\s|")', final, re.IGNORECASE))
    cover_before_visual = bool(re.search(r'<section\b[^>]*report-cover[^>]*>.*?</section>\s*<div\b[^>]*visual-block', final, re.I | re.S))
    injected = sum(1 for result in injection_results if result.status == "OK")
    warnings = [result for result in injection_results if result.status != "OK"]

    print("[验证] recommendations：{}，fragments：{}，已注入：{}".format(recommendation_count, fragment_count, injected))
    for result in injection_results:
        prefix = "[OK]" if result.status == "OK" else "[WARN]"
        chart_label = result.chart_id or "(unknown)"
        print(f"{prefix} {chart_label} / {result.anchor} / {result.message}")
    print(f"[验证] <p> 包裹块级元素残留：{residual_p_block}")
    print(f"[验证] 下载/截图旧逻辑残留：{residual_download}")
    print(f"[验证] 重复 chart id：{', '.join(duplicate_ids) if duplicate_ids else '无'}")
    print(f"[验证] 并排视觉行：{visual_rows}")
    print(f"[验证] 封面保护：{'通过' if cover_before_visual or 'report-cover' in final else '未检测到封面'}")

    if residual_p_block == 0 and residual_download == 0 and not duplicate_ids and not warnings:
        print("[验证] 全部通过")
    else:
        print("[WARN] 存在需要检查的问题")


def find_duplicate_chart_ids(html: str) -> list[str]:
    ids = re.findall(r'\bid=["\'](chart-C\d+)["\']', html, flags=re.IGNORECASE)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in ids:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法：python3 scripts/assemble.py <report_dir> <output_name>")
        sys.exit(1)
    build_html(sys.argv[1], sys.argv[2])
