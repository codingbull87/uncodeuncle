#!/usr/bin/env python3
from __future__ import annotations

import html as html_lib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from export_pdf import candidate_browsers, export_pdf


BLOCK_SELECTOR = "h1,h2,h3,.visual-row,.visual-block:not(.visual-block-nested),table,blockquote,p,ul,ol"
PAGE_HEIGHT_PX = round((297 - 16 - 18) * (96 / 25.4))
MARKER_REGEX = re.compile(r"R([SE])B(\d+)Z")
MARKER_TOKEN_REGEX = re.compile(r"[A-Z0-9]+")
MARKER_TEXT_REGEX = re.compile(r"R[SE]B\d+Z")
DUMP_SCHEMA = "report-illustrator-layout-probe:v3"


PROBE_STYLE = """
<style id="ri-layout-probe-style">
  .ri-layout-probe-positioned {
    position: relative !important;
  }
  .ri-layout-marker {
    position: absolute !important;
    left: 0 !important;
    font: 8px/1 monospace !important;
    color: #000 !important;
    opacity: 0.06 !important;
    white-space: nowrap !important;
    pointer-events: none !important;
    z-index: 0 !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
  }
  .ri-layout-marker-start {
    top: 0 !important;
  }
  .ri-layout-marker-end {
    bottom: 0 !important;
  }
</style>
""".strip()


PROBE_SCRIPT = rf"""
<script id="ri-layout-probe-script">
(function () {{
  var BLOCK_SELECTOR = {json.dumps(BLOCK_SELECTOR)};
  var PAGE_HEIGHT_PX = {PAGE_HEIGHT_PX};

  function cleanText(el) {{
    return (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160);
  }}

  function memberIds(row) {{
    var nodes = row.querySelectorAll(':scope > .visual-block[data-chart-id], :scope > .visual-block-nested[data-chart-id]');
    var ids = [];
    nodes.forEach(function (n) {{
      var id = n.getAttribute('data-chart-id');
      if (id) ids.push(id);
    }});
    return Array.from(new Set(ids));
  }}

  function ensurePositioned(node) {{
    if (node.classList.contains('ri-layout-probe-positioned')) return;
    var computed = window.getComputedStyle(node).position;
    if (!computed || computed === 'static') {{
      node.classList.add('ri-layout-probe-positioned');
    }}
  }}

  function addMarker(node, markerText, cls) {{
    if (node.querySelector(':scope > .' + cls)) return;
    var marker = document.createElement('span');
    marker.className = 'ri-layout-marker ' + cls;
    marker.setAttribute('aria-hidden', 'true');
    marker.textContent = markerText;
    node.appendChild(marker);
  }}

  function buildRegistry() {{
    var nodes = Array.prototype.slice.call(document.querySelectorAll(BLOCK_SELECTOR));
    var blocks = [];
    nodes.forEach(function (node, idx) {{
      var rect = node.getBoundingClientRect();
      if (!rect.height) return;
      var blockNumber = blocks.length + 1;
      var blockId = 'B' + String(blockNumber).padStart(3, '0');
      var isRow = node.classList.contains('visual-row');
      var isVisual = isRow || node.classList.contains('visual-block');
      var chartId = node.getAttribute('data-chart-id') || '';
      var text = cleanText(node);
      node.setAttribute('data-layout-block-id', blockId);
      ensurePositioned(node);
      addMarker(node, 'RS' + blockId + 'Z', 'ri-layout-marker-start');
      addMarker(node, 'RE' + blockId + 'Z', 'ri-layout-marker-end');
      blocks.push({{
        blockId: blockId,
        domIndex: idx,
        tag: node.tagName.toLowerCase(),
        className: node.className || '',
        kind: isRow ? 'visual-row' : (isVisual ? 'visual-block' : 'text'),
        text: text,
        chartId: chartId,
        group: node.getAttribute('data-group') || '',
        memberChartIds: isRow ? memberIds(node) : [],
        layout: node.getAttribute('data-layout') || node.getAttribute('data-row-layout') || '',
        size: node.getAttribute('data-size') || '',
        pageRole: node.getAttribute('data-page-role') || '',
        keepWithNext: node.getAttribute('data-keep-with-next') || '',
        canShrink: node.getAttribute('data-can-shrink') || '',
        maxShrinkRatio: node.getAttribute('data-max-shrink-ratio') || '',
        printCompact: node.getAttribute('data-print-compact') || '',
        visualType: node.getAttribute('data-visual-type') || ''
      }});
    }});
    return {{
      schema: {json.dumps(DUMP_SCHEMA)},
      pageHeightPx: PAGE_HEIGHT_PX,
      blockSelector: BLOCK_SELECTOR,
      blocks: blocks
    }};
  }}

  function maybeDump(payload) {{
    var params = new URLSearchParams(window.location.search);
    if (params.get('layout_dump') !== '1') return;
    document.body.innerHTML = '<pre id="layout-json"></pre>';
    document.getElementById('layout-json').textContent = JSON.stringify(payload);
  }}

  window.addEventListener('load', function () {{
    window.setTimeout(function () {{
      var payload = buildRegistry();
      maybeDump(payload);
    }}, 700);
  }});
}})();
</script>
""".strip()


def inject_probe_assets(source_html: str) -> str:
    html = source_html
    if "ri-layout-probe-style" not in html:
        if "</head>" in html:
            html = html.replace("</head>", PROBE_STYLE + "\n</head>")
        else:
            html = PROBE_STYLE + "\n" + html
    if "ri-layout-probe-script" not in html:
        if "</body>" in html:
            html = html.replace("</body>", PROBE_SCRIPT + "\n</body>")
        else:
            html += "\n" + PROBE_SCRIPT
    return html


def run_dump_dom(path: Path, query: str = "layout_dump=1") -> str:
    browsers = candidate_browsers()
    if not browsers:
        raise SystemExit("[ERROR] 未找到 Chrome/Chromium/Edge")
    browser = browsers[0]
    uri = path.resolve().as_uri()
    if query:
        uri = f"{uri}?{query}"
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
        "--virtual-time-budget=4000",
        "--dump-dom",
        uri,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        cmd[1] = "--headless"
        proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"[ERROR] dump-dom 失败: rc={proc.returncode}\n{proc.stderr.strip()}")
    return proc.stdout


def parse_dumped_registry(dom_text: str) -> dict[str, Any]:
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


def _marker_events_from_page(page: Any, page_index: int, page_height_px: int) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []

    def visitor(text: str, cm: list[Any], tm: list[Any], font_dict: Any, font_size: float) -> None:
        raw = re.sub(r"\s+", "", text or "")
        if not raw or not MARKER_TOKEN_REGEX.fullmatch(raw):
            return
        tokens.append({
            "text": raw,
            "x": float(tm[4]) if len(tm) > 4 else 0.0,
            "y": float(tm[5]) if len(tm) > 5 else 0.0,
            "fontSize": float(font_size or 0.0),
        })

    page.extract_text(visitor_text=visitor)

    events: list[dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if "R" not in token["text"]:
            index += 1
            continue
        buffer = ""
        pieces: list[dict[str, Any]] = []
        matched = False
        for follow in range(index, min(len(tokens), index + 4)):
            piece = tokens[follow]
            if pieces and abs(piece["y"] - pieces[0]["y"]) > 6:
                break
            buffer += piece["text"]
            pieces.append(piece)
            match = MARKER_REGEX.search(buffer)
            if match:
                y_value = max(part["y"] for part in pieces)
                local_y = y_value - ((page_index - 1) * page_height_px)
                events.append({
                    "blockId": f"B{match.group(2)}",
                    "kind": "start" if match.group(1) == "S" else "end",
                    "page": page_index,
                    "y": y_value,
                    "localY": local_y,
                    "x": min(part["x"] for part in pieces),
                })
                index = follow + 1
                matched = True
                break
        if not matched:
            index += 1
    return events


def export_probe_pdf(temp_html: Path, pdf_path: Path) -> None:
    export_pdf(temp_html, pdf_path)


def extract_pdf_markers(pdf_path: Path, page_height_px: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit("[ERROR] layout_probe.py 需要 pypdf") from exc

    reader = PdfReader(str(pdf_path))
    page_texts: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = MARKER_TEXT_REGEX.sub("", text)
        text = re.sub(r"\s+", " ", text).strip()
        page_texts.append({
            "page": page_index,
            "text": text,
            "textChars": len(re.sub(r"\s+", "", text)),
        })
        events.extend(_marker_events_from_page(page, page_index, page_height_px))
    return events, page_texts, len(reader.pages)


def _round_px(value: float | int | None) -> int:
    if value is None:
        return 0
    return int(round(float(value)))


def _local_top(block: dict[str, Any], page: int) -> float:
    if page == int(block.get("pdfPageStart", 0)):
        return float(block.get("pdfLocalTop", 0.0))
    return 0.0


def _local_bottom(block: dict[str, Any], page: int, page_height_px: int) -> float:
    start_page = int(block.get("pdfPageStart", 0))
    end_page = int(block.get("pdfPageEnd", 0))
    if start_page <= page < end_page:
        return float(page_height_px)
    return float(block.get("pdfLocalBottom", 0.0))


def merge_registry_with_markers(registry: dict[str, Any], marker_events: list[dict[str, Any]], total_pages: int) -> dict[str, Any]:
    blocks = sorted(registry.get("blocks", []), key=lambda item: int(item.get("domIndex", 0)))
    page_height_px = int(registry.get("pageHeightPx", PAGE_HEIGHT_PX))
    events_by_block: dict[str, dict[str, dict[str, Any]]] = {}
    for event in marker_events:
        block_id = str(event.get("blockId", "")).strip()
        if not block_id:
            continue
        slot = events_by_block.setdefault(block_id, {})
        slot[str(event.get("kind", ""))] = event

    missing_markers: list[str] = []
    merged_blocks: list[dict[str, Any]] = []
    for block in blocks:
        record = dict(block)
        block_id = str(block.get("blockId", "")).strip()
        events = events_by_block.get(block_id, {})
        start = events.get("start")
        end = events.get("end")
        if not start or not end:
            missing_markers.append(block_id)
            continue
        record["pdfPage"] = int(start.get("page", 0))
        record["pdfPageStart"] = int(start.get("page", 0))
        record["pdfPageEnd"] = int(end.get("page", 0))
        record["pdfLocalTop"] = round(max(0.0, float(start.get("localY", 0.0))), 2)
        record["pdfLocalBottom"] = round(max(0.0, float(end.get("localY", 0.0))), 2)
        merged_blocks.append(record)

    pages: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        page_blocks = [
            block for block in merged_blocks
            if int(block.get("pdfPageStart", 0)) <= page <= int(block.get("pdfPageEnd", 0))
        ]
        used_px = 0.0
        first_block = None
        first_visual = None
        last_block = None
        last_visual = None
        for block in page_blocks:
            top_value = _local_top(block, page)
            bottom_value = _local_bottom(block, page, page_height_px)
            used_px = max(used_px, bottom_value)
            if first_block is None or (top_value, int(block.get("domIndex", 0))) < (first_block[0], first_block[1]):
                first_block = (top_value, int(block.get("domIndex", 0)), block)
            if last_block is None or (bottom_value, int(block.get("domIndex", 0))) >= (last_block[0], last_block[1]):
                last_block = (bottom_value, int(block.get("domIndex", 0)), block)
            if str(block.get("kind", "")).startswith("visual"):
                if first_visual is None or (top_value, int(block.get("domIndex", 0))) < (first_visual[0], first_visual[1]):
                    first_visual = (top_value, int(block.get("domIndex", 0)), block)
                if last_visual is None or (bottom_value, int(block.get("domIndex", 0))) >= (last_visual[0], last_visual[1]):
                    last_visual = (bottom_value, int(block.get("domIndex", 0)), block)

        used_px = min(float(page_height_px), max(0.0, used_px))
        blank_px = max(0.0, float(page_height_px) - used_px)
        pages.append({
            "page": page,
            "blockCount": len(page_blocks),
            "visualBlocks": sum(1 for block in page_blocks if str(block.get("kind", "")).startswith("visual")),
            "usedPx": _round_px(used_px),
            "blankPx": _round_px(blank_px),
            "blankRatio": round(blank_px / float(page_height_px), 3),
            "firstBlockId": first_block[2].get("blockId") if first_block else "",
            "firstVisualBlockId": first_visual[2].get("blockId") if first_visual else "",
            "lastBlockId": last_block[2].get("blockId") if last_block else "",
            "lastVisualBlockId": last_visual[2].get("blockId") if last_visual else "",
        })

    return {
        "schema": DUMP_SCHEMA,
        "pageHeightPx": page_height_px,
        "totalPages": total_pages,
        "blocks": merged_blocks,
        "pages": pages,
        "missingMarkers": missing_markers,
    }


def build_probe_payload(html_path: Path) -> dict[str, Any]:
    source_html = html_path.read_text(encoding="utf-8", errors="ignore")
    probe_html = inject_probe_assets(source_html)
    with tempfile.TemporaryDirectory(prefix="report-illustrator-probe-") as tmpdir:
        temp_html = Path(tmpdir) / "probe.html"
        temp_html.write_text(probe_html, encoding="utf-8")
        dumped = run_dump_dom(temp_html, query="layout_dump=1")
        registry = parse_dumped_registry(dumped)
        pdf_path = Path(tmpdir) / "probe.pdf"
        export_probe_pdf(temp_html, pdf_path)
        events, page_texts, total_pages = extract_pdf_markers(pdf_path, int(registry.get("pageHeightPx", PAGE_HEIGHT_PX)))

    payload = merge_registry_with_markers(registry, events, total_pages)
    page_text_index = {int(item["page"]): item for item in page_texts}
    for page in payload.get("pages", []):
        info = page_text_index.get(int(page.get("page", 0)), {})
        page["textChars"] = int(info.get("textChars", 0))
        page["textPreview"] = str(info.get("text", ""))[:240]
    payload["markerEvents"] = events
    return payload
