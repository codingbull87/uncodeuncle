#!/usr/bin/env python3
"""
Run guarded assembly + export pipeline.

Usage:
  python3 scripts/run_pipeline.py <report_dir> <report_name> [--skip-export]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> None:
    print("[RUN] " + " ".join(cmd))
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run guarded report-illustrator pipeline")
    parser.add_argument("report_dir", help="Report workspace directory")
    parser.add_argument("report_name", help="Output report basename without extension")
    parser.add_argument("--skip-export", action="store_true", help="Only assemble HTML, skip PDF export")
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

    run_cmd([python, str(check), str(report_dir), "before-fragments"])
    run_cmd([python, str(check), str(report_dir), "before-assemble"])
    run_cmd([python, str(assemble), str(report_dir), args.report_name + "_illustrated"])

    if args.skip_export:
        print("[DONE] HTML 组装完成（已跳过 PDF 导出）")
        return 0

    run_cmd([python, str(check), str(report_dir), "before-export"])
    html_path = report_dir / f"{args.report_name}_illustrated.html"
    pdf_path = report_dir / f"{args.report_name}_illustrated.pdf"
    run_cmd([python, str(export), str(html_path), str(pdf_path)])
    print("[DONE] 流水线完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
