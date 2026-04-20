#!/usr/bin/env python3
"""
Run an end-to-end smoke test against a copied report workspace.

Usage:
  python3 scripts/smoke_e2e.py <source_report_dir> <report_name> [--installed-skill-dir PATH] [--keep-workdir]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def run(cmd: list[str]) -> None:
    print("[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def validate_outputs(workdir: Path, report_name: str) -> None:
    html_path = workdir / f"{report_name}_illustrated.html"
    pdf_path = workdir / f"{report_name}_illustrated.pdf"
    status_path = workdir / "PIPELINE_STATUS.json"
    layout_path = workdir / "LAYOUT_DIAGNOSIS.json"
    pdf_qa_path = workdir / "PDF_QA.json"
    visual_qa_path = workdir / "VISUAL_QA.json"

    for path in (html_path, pdf_path, status_path, layout_path, pdf_qa_path, visual_qa_path):
        if not path.exists():
            raise SystemExit(f"[FAIL] 缺少输出文件：{path}")

    status = read_json(status_path)
    if not status.get("success"):
        raise SystemExit(f"[FAIL] PIPELINE_STATUS.json 标记失败：{status.get('error')}")

    layout = read_json(layout_path)
    if layout.get("sparsePages") or layout.get("terminalSparsePages"):
        raise SystemExit("[FAIL] smoke 结束后仍存在 sparsePages 或 terminalSparsePages")

    pdf_qa = read_json(pdf_qa_path)
    if not pdf_qa.get("pass"):
        raise SystemExit("[FAIL] PDF_QA.json 未通过")

    visual_qa = read_json(visual_qa_path)
    if not visual_qa.get("skipped") and not visual_qa.get("pass"):
        raise SystemExit("[FAIL] VISUAL_QA.json 未通过")

    print(
        "[PASS] smoke 完成：pageCount={} html={} pdf={}".format(
            layout.get("summary", {}).get("pageCount"),
            html_path,
            pdf_path,
        )
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run md2report end-to-end smoke test")
    parser.add_argument("source_report_dir", help="Existing report workspace to copy")
    parser.add_argument("report_name", help="Output report basename without extension")
    parser.add_argument(
        "--installed-skill-dir",
        default="/Users/zheliu/.codex/skills/md2report",
        help="Installed md2report skill directory to validate",
    )
    parser.add_argument("--keep-workdir", action="store_true", help="Keep temporary copied workspace for inspection")
    args = parser.parse_args(argv[1:])

    source_report_dir = Path(args.source_report_dir).expanduser().resolve()
    if not source_report_dir.exists() or not source_report_dir.is_dir():
        raise SystemExit(f"[FAIL] 报告目录不存在：{source_report_dir}")

    installed_skill_dir = Path(args.installed_skill_dir).expanduser().resolve()
    run_pipeline = installed_skill_dir / "scripts" / "run_pipeline.py"
    if not run_pipeline.exists():
        raise SystemExit(f"[FAIL] 找不到安装版 run_pipeline.py：{run_pipeline}")

    temp_dir_obj = tempfile.TemporaryDirectory(prefix="md2report-smoke-")
    workdir = Path(temp_dir_obj.name)
    shutil.copytree(source_report_dir, workdir, dirs_exist_ok=True)
    print(f"[INFO] smoke 工作目录：{workdir}")

    try:
        run([sys.executable, str(run_pipeline), str(workdir), args.report_name])
        validate_outputs(workdir, args.report_name)
    finally:
        if args.keep_workdir:
            print(f"[INFO] 保留 smoke 工作目录：{workdir}")
        else:
            temp_dir_obj.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
