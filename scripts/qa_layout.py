#!/usr/bin/env python3
"""
Hybrid print-layout diagnosis.

- Uses browser DOM dump to collect visual block metadata.
- Uses Chromium print + PDF text density to detect sparse pages.
- Maps sparse pages back to likely visual blocks for repair suggestions.

Usage:
  python3 scripts/qa_layout.py <html_path> [output_json]
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from export_pdf import candidate_browsers, export_pdf


DUMP_SCRIPT = r"""
<script>
(function () {
  function cleanText(el) {
    return (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  }
  function memberIds(row) {
    var nodes = row.querySelectorAll(':scope > .visual-block[data-chart-id], :scope > .visual-block-nested[data-chart-id]');
    var ids = [];
    nodes.forEach(function (n) {
      var id = n.getAttribute('data-chart-id');
      if (id) ids.push(id);
    });
    return Array.from(new Set(ids));
  }
  function run() {
    var selectors = '.visual-row,.visual-block:not(.visual-block-nested),h2,h3,table,blockquote,p,ul,ol';
    var nodes = Array.prototype.slice.call(document.querySelectorAll(selectors));
    var blocks = [];
    nodes.forEach(function (node, idx) {
      var rect = node.getBoundingClientRect();
      if (!rect.height) return;
      blocks.push({
        domIndex: idx,
        tag: node.tagName.toLowerCase(),
        className: node.className || '',
        kind: node.classList.contains('visual-row') ? 'visual-row' : (node.classList.contains('visual-block') ? 'visual-block' : 'text'),
        top: Math.round(rect.top + window.scrollY),
        height: Math.round(rect.height),
        text: cleanText(node),
        chartId: node.getAttribute('data-chart-id') || '',
        group: node.getAttribute('data-group') || '',
        memberChartIds: node.classList.contains('visual-row') ? memberIds(node) : [],
        layout: node.getAttribute('data-layout') || node.getAttribute('data-row-layout') || '',
        size: node.getAttribute('data-size') || '',
        pageRole: node.getAttribute('data-page-role') || '',
        keepWithNext: node.getAttribute('data-keep-with-next') || '',
        canShrink: node.getAttribute('data-can-shrink') || '',
        maxShrinkRatio: node.getAttribute('data-max-shrink-ratio') || '',
        printCompact: node.getAttribute('data-print-compact') || ''
      });
    });

    var payload = {
      schema: 'report-illustrator-layout-diagnosis:v2',
      blocks: blocks
    };
    document.body.innerHTML = '<pre id="layout-json"></pre>';
    document.getElementById('layout-json').textContent = JSON.stringify(payload);
  }
  window.addEventListener('load', function () { window.setTimeout(run, 700); });
})();
</script>
"""


def inject_script(html: str) -> str:
    if "</body>" in html:
        return html.replace("</body>", DUMP_SCRIPT + "\n</body>")
    return html + DUMP_SCRIPT


def run_dump_dom(path: Path) -> str:
    browsers = candidate_browsers()
    if not browsers:
        raise SystemExit("[ERROR] 未找到 Chrome/Chromium/Edge")
    browser = browsers[0]
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-extensions",
        "--disable-sync",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--virtual-time-budget=3000",
        "--dump-dom",
        path.resolve().as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        cmd[1] = "--headless"
        proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"[ERROR] dump-dom 失败: rc={proc.returncode}\n{proc.stderr.strip()}")
    return proc.stdout


def parse_dumped_json(dom_text: str) -> dict:
    match = re.search(r'<pre id="layout-json">(.*?)</pre>', dom_text, flags=re.DOTALL)
    if not match:
        raise SystemExit("[ERROR] dump-dom 结果缺少 layout-json")
    raw = html_lib.unescape(match.group(1).strip())
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[ERROR] layout-json 解析失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("[ERROR] layout-json 顶层不是对象")
    return payload


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def pdf_pages_text(html_path: Path) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="report-illustrator-layout-pdf-") as tmp:
        pdf_path = Path(tmp) / "layout.pdf"
        export_pdf(html_path, pdf_path)
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise SystemExit("[ERROR] qa_layout.py 需要 pypdf") from exc
        reader = PdfReader(str(pdf_path))
        return [(page.extract_text() or "") for page in reader.pages]


def pdf_sparse_pages(page_texts: list[str]) -> list[dict]:
    items: list[dict] = []
    if not page_texts:
        return items
    for idx, text in enumerate(page_texts, start=1):
        chars = len(re.sub(r"\s+", "", text))
        blank_ratio = max(0.0, min(0.85, 1.0 - (chars / 650.0)))
        items.append({"page": idx, "textChars": chars, "blankRatio": round(blank_ratio, 3)})
    return items


def map_blocks_to_pdf_pages(blocks: list[dict], page_texts: list[str]) -> None:
    normalized_pages = [normalize_text(text) for text in page_texts]
    last_page = 1
    for block in blocks:
        text = normalize_text(str(block.get("text", "")))
        token = text[:24]
        matched = None
        if token:
            for idx, page_text in enumerate(normalized_pages, start=1):
                if token and token in page_text:
                    matched = idx
                    break
        if matched is None:
            matched = last_page
        block["pdfPage"] = matched
        last_page = matched


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def diagnose(payload: dict, page_stats: list[dict]) -> dict:
    blocks = sorted(payload.get("blocks", []), key=lambda x: int(x.get("domIndex", 0)))
    for block in blocks:
        if "pdfPage" not in block:
            block["pdfPage"] = 1

    sparse: list[dict] = []
    if page_stats:
        last_page = page_stats[-1]["page"]
        for item in page_stats:
            idx = int(item.get("page", 0))
            ratio = float(item.get("blankRatio", 0))
            if idx == last_page or ratio <= 0.38:
                continue

            page_visuals = [b for b in blocks if int(b.get("pdfPage", 0)) == idx and str(b.get("kind", "")).startswith("visual")]
            next_visuals = [b for b in blocks if int(b.get("pdfPage", 0)) == idx + 1 and str(b.get("kind", "")).startswith("visual")]
            trailing = page_visuals[-1] if page_visuals else None
            next_first = next_visuals[0] if next_visuals else None

            suggestions: list[dict] = []
            reason_parts: list[str] = []
            if trailing:
                if truthy(str(trailing.get("canShrink", ""))):
                    suggestions.append({
                        "action": "compact_trailing",
                        "target_chart_id": trailing.get("chartId", ""),
                        "target_member_chart_ids": trailing.get("memberChartIds", []),
                        "reason": "trailing visual can shrink"
                    })
                if truthy(str(trailing.get("keepWithNext", ""))):
                    reason_parts.append("trailing block keep-with-next")
            if next_first:
                suggestions.append({
                    "action": "compact_next",
                    "target_chart_id": next_first.get("chartId", ""),
                    "target_member_chart_ids": next_first.get("memberChartIds", []),
                    "reason": "leading next-page visual"
                })
                reason_parts.append("next-page leading visual")

            sparse.append({
                "page": idx,
                "blankRatio": ratio,
                "textChars": int(item.get("textChars", 0)),
                "reason": "; ".join(reason_parts) if reason_parts else "pdf text density indicates sparse page",
                "trailing_visual": trailing,
                "next_page_leading_visual": next_first,
                "suggestions": suggestions,
            })

    payload["pages"] = page_stats
    payload["blocks"] = blocks
    payload["sparsePages"] = sparse
    payload["summary"] = {
        "totalPages": len(page_stats),
        "sparsePages": len(sparse),
        "maxBlankRatio": max((float(p.get("blankRatio", 0)) for p in page_stats), default=0.0),
    }
    return payload


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Diagnose print layout via PDF density + DOM block mapping")
    parser.add_argument("html_path", help="Assembled report HTML path")
    parser.add_argument("output_json", nargs="?", help="Optional output JSON path")
    args = parser.parse_args(argv[1:])

    html_path = Path(args.html_path).expanduser().resolve()
    if not html_path.exists():
        print(f"[ERROR] 找不到 HTML：{html_path}")
        return 1

    with tempfile.TemporaryDirectory(prefix="report-illustrator-layout-") as tmp:
        temp_html = Path(tmp) / "layout.html"
        source = html_path.read_text(encoding="utf-8", errors="ignore")
        temp_html.write_text(inject_script(source), encoding="utf-8")
        dumped = run_dump_dom(temp_html)

    payload = parse_dumped_json(dumped)
    page_texts = pdf_pages_text(html_path)
    page_stats = pdf_sparse_pages(page_texts)

    # Better mapping with actual page text now available.
    blocks = sorted(payload.get("blocks", []), key=lambda x: int(x.get("domIndex", 0)))
    normalized_pages = [normalize_text(text) for text in page_texts]
    last_page = 1
    for block in blocks:
        token = normalize_text(str(block.get("text", "")))[:24]
        matched = None
        if token:
            for idx, text in enumerate(normalized_pages, start=1):
                if token in text:
                    matched = idx
                    break
        if matched is None:
            matched = last_page
        block["pdfPage"] = matched
        last_page = matched
    payload["blocks"] = blocks

    payload = diagnose(payload, page_stats)

    output_path = Path(args.output_json).expanduser().resolve() if args.output_json else html_path.with_name("LAYOUT_DIAGNOSIS.json")
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[LAYOUT_QA] html={html_path}")
    print(f"[LAYOUT_QA] output={output_path}")
    summary = payload.get("summary", {})
    print(f"[LAYOUT_QA] pages={summary.get('totalPages', 0)} sparse_pages={summary.get('sparsePages', 0)} max_blank={summary.get('maxBlankRatio', 0):.0%}")
    for item in payload.get("sparsePages", []):
        print(f"[WARN] 第 {item.get('page')} 页空白约 {float(item.get('blankRatio', 0)):.0%} / {item.get('reason', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
