#!/usr/bin/env python3
"""
Run guarded assembly + export pipeline.

Usage:
  python3 scripts/run_pipeline.py <report_dir> <report_name> [--skip-export]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline_common import (
    PipelineStatusTracker,
    build_pipeline_outputs,
    build_pipeline_summary,
    clear_generated_layout_overrides,
    file_bytes,
    has_sparse_layout,
    run_cmd,
)


def run_status_cmd(tracker: PipelineStatusTracker, stage: str, cmd: list[str]) -> None:
    tracker.start_stage(stage, {"command": cmd})
    run_cmd(cmd)
    tracker.finish_stage(stage)


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

    tracker = PipelineStatusTracker(
        report_dir / "PIPELINE_STATUS.json",
        mode="serial",
        report_dir=report_dir,
        report_name=args.report_name,
        options={
            "skipExport": args.skip_export,
            "skipLayoutRepair": args.skip_layout_repair,
        },
    )

    python = sys.executable
    check = script_dir / "check_phase_contract.py"
    build_anchor_index = script_dir / "build_anchor_index.py"
    prepare_recommendations = script_dir / "prepare_recommendations.py"
    normalize_fragments = script_dir / "normalize_fragments.py"
    lint_fragments = script_dir / "lint_fragments.py"
    assemble = script_dir / "assemble.py"
    export = script_dir / "export_pdf.py"
    qa_html = script_dir / "qa_html.py"
    qa_pdf = script_dir / "qa_pdf.py"
    qa_visual = script_dir / "qa_visual.py"
    qa_layout = script_dir / "qa_layout.py"
    repair_layout = script_dir / "repair_layout.py"
    html_path = report_dir / f"{args.report_name}_illustrated.html"
    layout_diag = report_dir / "LAYOUT_DIAGNOSIS.json"
    pdf_path = report_dir / f"{args.report_name}_illustrated.pdf"

    try:
        run_status_cmd(tracker, "build-anchor-index", [python, str(build_anchor_index), str(report_dir)])
        run_status_cmd(tracker, "prepare-recommendations", [python, str(prepare_recommendations), str(report_dir)])
        run_status_cmd(tracker, "gate-before-fragments", [python, str(check), str(report_dir), "before-fragments"])
        run_status_cmd(tracker, "normalize-fragments", [python, str(normalize_fragments), str(report_dir)])
        run_status_cmd(tracker, "lint-fragments", [python, str(lint_fragments), str(report_dir)])
        run_status_cmd(tracker, "gate-before-assemble", [python, str(check), str(report_dir), "before-assemble"])

        tracker.start_stage("clear-layout-overrides")
        clear_generated_layout_overrides(report_dir)
        tracker.finish_stage("clear-layout-overrides")

        run_status_cmd(tracker, "assemble-initial", [python, str(assemble), str(report_dir), args.report_name + "_illustrated"])
        run_status_cmd(tracker, "qa-html-initial", [python, str(qa_html), str(report_dir)])
        run_status_cmd(tracker, "qa-layout-initial", [python, str(qa_layout), str(html_path), str(layout_diag)])

        if not args.skip_layout_repair:
            override_path = report_dir / "LAYOUT_OVERRIDES.json"
            max_rounds = 3
            for round_index in range(1, max_rounds + 1):
                if not has_sparse_layout(layout_diag):
                    break
                before = file_bytes(override_path)
                tracker.start_stage("layout-repair", {"round": round_index})
                run_cmd([python, str(repair_layout), str(report_dir), str(layout_diag), str(override_path)])
                after = file_bytes(override_path)
                changed = before != after
                tracker.finish_stage("layout-repair", {"round": round_index, "changed": changed})
                if not changed:
                    break
                run_status_cmd(tracker, f"assemble-repair-round-{round_index}", [python, str(assemble), str(report_dir), args.report_name + "_illustrated"])
                run_status_cmd(tracker, f"qa-html-repair-round-{round_index}", [python, str(qa_html), str(report_dir), str(html_path)])
                run_status_cmd(tracker, f"qa-layout-repair-round-{round_index}", [python, str(qa_layout), str(html_path), str(layout_diag)])
            if has_sparse_layout(layout_diag):
                raise SystemExit("[FAIL] layout repair 后仍存在稀疏页或末页稀疏页，禁止继续导出")
        else:
            tracker.start_stage("layout-repair-skipped")
            tracker.finish_stage("layout-repair-skipped")

        if args.skip_export:
            tracker.succeed(
                outputs=build_pipeline_outputs(report_dir, args.report_name, include_pdf=False),
                summary=build_pipeline_summary(report_dir),
            )
            print("[DONE] HTML 组装完成（已跳过 PDF 导出）")
            return 0

        run_status_cmd(tracker, "gate-before-export", [python, str(check), str(report_dir), "before-export"])
        run_status_cmd(tracker, "export-pdf", [python, str(export), str(html_path), str(pdf_path)])
        run_status_cmd(tracker, "qa-pdf", [python, str(qa_pdf), str(pdf_path), str(report_dir / "PDF_QA.json")])
        run_status_cmd(tracker, "qa-visual", [python, str(qa_visual), str(html_path), str(pdf_path), str(report_dir / "VISUAL_QA.json")])
    except SystemExit as exc:
        error = exc.code if isinstance(exc.code, str) else f"exit={exc.code}"
        tracker.fail(
            error,
            outputs=build_pipeline_outputs(report_dir, args.report_name, include_pdf=not args.skip_export),
            summary=build_pipeline_summary(report_dir),
        )
        raise
    except Exception as exc:
        tracker.fail(
            str(exc),
            outputs=build_pipeline_outputs(report_dir, args.report_name, include_pdf=not args.skip_export),
            summary=build_pipeline_summary(report_dir),
        )
        raise

    tracker.succeed(
        outputs=build_pipeline_outputs(report_dir, args.report_name, include_pdf=True),
        summary=build_pipeline_summary(report_dir),
    )
    print("[DONE] 流水线完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
