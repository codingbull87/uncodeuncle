#!/usr/bin/env python3
"""
Approximate print-layout QA for an assembled report.

The script renders a temporary Chromium PDF and uses PDF text density as a
portable sparse-page heuristic. It is intentionally dependency-light: no poppler
or ghostscript is required.

Usage:
  python3 scripts/qa_pdf.py <html_path> [qa_json_path]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

from export_pdf import export_pdf


QA_SCRIPT = r"""
<script>
(function () {
  function pageHeightPx() {
    var mmToPx = 96 / 25.4;
    return Math.round((297 - 16 - 18) * mmToPx);
  }
  function topWithinPage(el, page) {
    var top = 0;
    var node = el;
    while (node && node !== page) {
      top += node.offsetTop || 0;
      node = node.offsetParent;
    }
    return top;
  }
  function textOf(el) {
    return (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  }
  function run() {
    document.documentElement.classList.add('pdf-export-mode');
    var page = document.querySelector('.page');
    var pageHeight = pageHeightPx();
    var blocks = Array.prototype.slice.call(document.querySelectorAll('h1,h2,h3,.visual-row,.visual-block:not(.visual-block-nested),table,blockquote,p,ul,ol'));
    var pages = {};
    var blockDetails = [];
    blocks.forEach(function (block) {
      var rect = block.getBoundingClientRect();
      if (!rect.height) return;
      var top = topWithinPage(block, page);
      var pageIndex = Math.floor(top / pageHeight) + 1;
      var bottom = top + rect.height;
      if (!pages[pageIndex]) pages[pageIndex] = { page: pageIndex, minTop: top, maxBottom: bottom, blocks: 0, visualBlocks: 0 };
      pages[pageIndex].minTop = Math.min(pages[pageIndex].minTop, top);
      pages[pageIndex].maxBottom = Math.max(pages[pageIndex].maxBottom, bottom);
      pages[pageIndex].blocks += 1;
      var isVisual = block.classList.contains('visual-block') || block.classList.contains('visual-row');
      if (isVisual) pages[pageIndex].visualBlocks += 1;
      blockDetails.push({
        tag: block.tagName.toLowerCase(),
        className: block.className || '',
        text: textOf(block),
        page: pageIndex,
        top: Math.round(top),
        height: Math.round(rect.height),
        withinPageTop: Math.round(top % pageHeight),
        withinPageBottom: Math.round((top + rect.height) % pageHeight)
      });
    });
    var pageList = Object.keys(pages).map(function (key) {
      var item = pages[key];
      var used = item.maxBottom - ((item.page - 1) * pageHeight);
      var blank = Math.max(0, pageHeight - used);
      return {
        page: item.page,
        blocks: item.blocks,
        visualBlocks: item.visualBlocks,
        usedPx: Math.round(used),
        blankPx: Math.round(blank),
        blankRatio: Number((blank / pageHeight).toFixed(3))
      };
    });
    var result = {
      schema: 'report-illustrator-pdf-qa:v1',
      pageHeightPx: pageHeight,
      pages: pageList,
      blocks: blockDetails
    };
    document.body.innerHTML = '<pre id="qa-json"></pre>';
    document.getElementById('qa-json').textContent = JSON.stringify(result);
  }
  window.addEventListener('load', function () {
    window.setTimeout(run, 800);
  });
})();
</script>
"""


def inject_script(html: str) -> str:
    if "</body>" in html:
        return html.replace("</body>", QA_SCRIPT + "\n</body>")
    return html + QA_SCRIPT


def run_browser_dump(html_path: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="report-illustrator-qa-") as tmpdir:
        pdf_path = Path(tmpdir) / "qa.pdf"
        export_pdf(html_path, pdf_path)
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise SystemExit("[ERROR] qa_pdf.py 需要 pypdf 才能检查 PDF 文本密度") from exc

        reader = PdfReader(str(pdf_path))
        pages = []
        blocks = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            chars = len(re.sub(r"\s+", "", text))
            # This is a density heuristic, not a visual renderer. It reliably catches
            # very sparse pages produced by forced block moves.
            blank_ratio = max(0.0, min(0.85, 1.0 - (chars / 650.0)))
            pages.append({
                "page": index,
                "blocks": 0,
                "visualBlocks": 0,
                "textChars": chars,
                "usedPx": None,
                "blankPx": None,
                "blankRatio": round(blank_ratio, 3)
            })
            blocks.append({"page": index, "textChars": chars, "text": text[:180]})

    return {
        "schema": "report-illustrator-pdf-qa:v1",
        "method": "chromium-print-plus-pypdf-density",
        "pages": pages,
        "blocks": blocks
    }


def evaluate(result: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    pages = result.get("pages", [])
    if not pages:
        errors.append("未检测到任何页面内容")
        return errors, warnings

    last_page = max(int(page.get("page", 0)) for page in pages)
    for page in pages:
        index = int(page.get("page", 0))
        blank_ratio = float(page.get("blankRatio", 0))
        blocks = int(page.get("blocks", 0))
        visual_blocks = int(page.get("visualBlocks", 0))
        if index == last_page:
            if blank_ratio > 0.55 and blocks <= 4:
                warnings.append(f"第 {index} 页内容偏少，页底空白约 {blank_ratio:.0%}")
            continue
        if blank_ratio > 0.68:
            errors.append(f"第 {index} 页页底空白过大，约 {blank_ratio:.0%}")
        elif blank_ratio > 0.38:
            warnings.append(f"第 {index} 页页底空白偏大，约 {blank_ratio:.0%}")
        if visual_blocks == 1 and blocks <= 3 and blank_ratio > 0.35:
            warnings.append(f"第 {index} 页疑似单视觉块低密度页")
    return errors, warnings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="QA PDF print layout from assembled HTML")
    parser.add_argument("html_path", help="Assembled report HTML path")
    parser.add_argument("qa_json_path", nargs="?", help="Optional QA JSON output path")
    args = parser.parse_args(argv[1:])

    html_path = Path(args.html_path).expanduser().resolve()
    if not html_path.exists():
        print(f"[ERROR] 找不到 HTML 文件：{html_path}")
        return 1

    result = run_browser_dump(html_path)
    errors, warnings = evaluate(result)
    result["errors"] = errors
    result["warnings"] = warnings

    qa_json_path = Path(args.qa_json_path).expanduser().resolve() if args.qa_json_path else html_path.with_name("PDF_QA.json")
    qa_json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[PDF_QA] html={html_path}")
    print(f"[PDF_QA] output={qa_json_path}")
    for item in warnings:
        print(f"[WARN] {item}")
    for item in errors:
        print(f"[ERROR] {item}")
    if errors:
        print("[FAIL] PDF QA 未通过")
        return 1
    print("[PASS] PDF QA 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
