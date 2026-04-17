#!/usr/bin/env python3
"""
Run guarded assembly + export pipeline.

Usage:
  python3 scripts/run_pipeline.py <report_dir> <report_name> [--skip-export]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> None:
    print("[RUN] " + " ".join(cmd))
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def sparse_pages(layout_diag_path: Path) -> int:
    if not layout_diag_path.exists():
        return 0
    try:
        payload = json.loads(layout_diag_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return 0
    items = payload.get("sparsePages", [])
    return len(items) if isinstance(items, list) else 0


def terminal_sparse_pages(layout_diag_path: Path) -> int:
    if not layout_diag_path.exists():
        return 0
    try:
        payload = json.loads(layout_diag_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return 0
    items = payload.get("terminalSparsePages", [])
    return len(items) if isinstance(items, list) else 0


def clear_generated_layout_overrides(report_dir: Path) -> None:
    path = report_dir / "LAYOUT_OVERRIDES.json"
    if path.exists():
        path.unlink()


def file_bytes(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run guarded md2report pipeline")
    parser.add_argument("report_dir", help="Report workspace directory")
    parser.add_argument("report_name", help="Output report basename without extension")
    parser.add_argument("--skip-export", action="store_true", help="Only assemble HTML, skip PDF export")
    parser.add_argument("--skip-layout-repair", action="store_true", help="Skip layout diagnosis and automatic repair loop")
    args = parser.parse_args(argv[1:])

    script_dir = Path(__file__).resolve().parent
    report_dir = Path(args.report_dir).expanduser().resolve()
    if not report_dir.exists() or not report_dir.is_dir():
        print(f"[ERROR] 报告目录不存在：{report_dir}")
        return 1

    python = sys.executable
    check = script_dir / "check_phase_contract.py"
    assemble = script_dir / "assemble.py"
    export = script_dir / "export_pdf.py"
    qa_html = script_dir / "qa_html.py"
    qa_pdf = script_dir / "qa_pdf.py"
    qa_layout = script_dir / "qa_layout.py"
    repair_layout = script_dir / "repair_layout.py"

    run_cmd([python, str(check), str(report_dir), "before-fragments"])
    run_cmd([python, str(check), str(report_dir), "before-assemble"])
    clear_generated_layout_overrides(report_dir)
    run_cmd([python, str(assemble), str(report_dir), args.report_name + "_illustrated"])
    run_cmd([python, str(qa_html), str(report_dir)])
    html_path = report_dir / f"{args.report_name}_illustrated.html"
    layout_diag = report_dir / "LAYOUT_DIAGNOSIS.json"
    run_cmd([python, str(qa_layout), str(html_path), str(layout_diag)])

    if not args.skip_layout_repair:
        override_path = report_dir / "LAYOUT_OVERRIDES.json"
        max_rounds = 3
        for _ in range(max_rounds):
            if sparse_pages(layout_diag) == 0 and terminal_sparse_pages(layout_diag) == 0:
                break
            before = file_bytes(override_path)
            run_cmd([python, str(repair_layout), str(report_dir), str(layout_diag), str(override_path)])
            after = file_bytes(override_path)
            if before == after:
                break
            run_cmd([python, str(assemble), str(report_dir), args.report_name + "_illustrated"])
            run_cmd([python, str(qa_html), str(report_dir), str(html_path)])
            run_cmd([python, str(qa_layout), str(html_path), str(layout_diag)])
        if sparse_pages(layout_diag) > 0:
            raise SystemExit("[FAIL] layout repair 后仍存在稀疏页，禁止继续导出")

    if args.skip_export:
        print("[DONE] HTML 组装完成（已跳过 PDF 导出）")
        return 0

    run_cmd([python, str(check), str(report_dir), "before-export"])
    pdf_path = report_dir / f"{args.report_name}_illustrated.pdf"
    run_cmd([python, str(qa_pdf), str(html_path), str(report_dir / "PDF_QA.json")])
    run_cmd([python, str(export), str(html_path), str(pdf_path)])
    print("[DONE] 流水线完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
