#!/usr/bin/env python3
"""
Fragment cleanup helpers shared by the assembler path.
"""

from __future__ import annotations

import html as html_lib
import json
import re


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


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = html_lib.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


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
