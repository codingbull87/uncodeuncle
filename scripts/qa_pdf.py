#!/usr/bin/env python3
"""
QA the actual exported PDF artifact.

Usage:
  python3 scripts/qa_pdf.py <pdf_path> [qa_json_path]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def load_pdf_pages(pdf_path: Path) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit("[ERROR] qa_pdf.py 需要 pypdf") from exc

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        raise SystemExit(f"[ERROR] PDF 解析失败：{exc}") from exc

    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        mediabox = page.mediabox
        width = float(mediabox.width)
        height = float(mediabox.height)
        pages.append(
            {
                "page": index,
                "widthPt": round(width, 2),
                "heightPt": round(height, 2),
                "rotation": int(page.get("/Rotate", 0) or 0),
                "textChars": len(re.sub(r"\s+", "", text)),
                "textPreview": text[:240],
            }
        )
    return pages


def evaluate_pages(pages: list[dict[str, Any]], pdf_path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not pages:
        errors.append("未检测到任何 PDF 页面")
        return errors, warnings

    width_values = {page["widthPt"] for page in pages}
    height_values = {page["heightPt"] for page in pages}
    if len(width_values) > 1 or len(height_values) > 1:
        warnings.append("PDF 页面尺寸不一致；可能存在异常分页或导出配置漂移")

    for page in pages:
        index = int(page["page"])
        text_chars = int(page["textChars"])
        if page["widthPt"] <= 0 or page["heightPt"] <= 0:
            errors.append(f"第 {index} 页尺寸非法")
        if page["rotation"] not in {0, 90, 180, 270}:
            warnings.append(f"第 {index} 页旋转角异常：{page['rotation']}")
        if text_chars == 0:
            warnings.append(f"第 {index} 页未提取到任何文本")

    diagnostics_path = pdf_path.parent / "EXPORT_DIAGNOSTICS.json"
    if diagnostics_path.exists():
        try:
            diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            diagnostics = {}
        expected_page_count = diagnostics.get("page_count")
        if isinstance(expected_page_count, int) and expected_page_count > 0 and expected_page_count != len(pages):
            errors.append(
                f"实际 PDF 页数与 EXPORT_DIAGNOSTICS.json 不一致：actual={len(pages)} expected={expected_page_count}"
            )

    layout_path = pdf_path.parent / "LAYOUT_DIAGNOSIS.json"
    if layout_path.exists():
        try:
            layout_payload = json.loads(layout_path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            layout_payload = {}
        layout_summary = layout_payload.get("summary", {}) if isinstance(layout_payload, dict) else {}
        expected_layout_pages = layout_summary.get("pageCount") or layout_summary.get("totalPages")
        if isinstance(expected_layout_pages, int) and expected_layout_pages > 0 and expected_layout_pages != len(pages):
            errors.append(
                f"实际 PDF 页数与 LAYOUT_DIAGNOSIS.json 不一致：actual={len(pages)} expected={expected_layout_pages}"
            )
    return errors, warnings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="QA actual exported PDF artifact")
    parser.add_argument("pdf_path", help="Exported PDF path")
    parser.add_argument("qa_json_path", nargs="?", help="Optional QA JSON output path")
    args = parser.parse_args(argv[1:])

    pdf_path = Path(args.pdf_path).expanduser().resolve()
    if not pdf_path.exists():
        print(f"[ERROR] 找不到 PDF 文件：{pdf_path}")
        return 1

    if pdf_path.stat().st_size <= 0:
        print(f"[ERROR] PDF 文件为空：{pdf_path}")
        return 1

    pages = load_pdf_pages(pdf_path)
    errors, warnings = evaluate_pages(pages, pdf_path)
    payload = {
        "schema": "report-illustrator-pdf-qa:v1",
        "pdfPath": str(pdf_path),
        "pageCount": len(pages),
        "pass": not errors,
        "pages": pages,
        "errors": errors,
        "warnings": warnings,
    }

    qa_json_path = Path(args.qa_json_path).expanduser().resolve() if args.qa_json_path else pdf_path.with_name("PDF_QA.json")
    qa_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[PDF_QA] pdf={pdf_path}")
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
