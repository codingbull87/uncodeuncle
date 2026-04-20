#!/usr/bin/env python3
"""
Run guarded pipeline with parallel fragment generation in Phase 6 only.

Usage:
  python3 scripts/run_pipeline_parallel.py <report_dir> <report_name> \
    --worker-cmd "<command template>" [--max-workers 3] [--batch-size 3] [--skip-export]

Template variables in --worker-cmd:
  - {report_dir}
  - {chart_id}      (e.g. C12)
  - {id}            (numeric part, e.g. 12)
  - {fragment_path}
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from lint_fragments import lint_fragment, lint_report_dir, load_contracts, load_recommendation_types
from pipeline_common import (
    PipelineStatusTracker,
    build_pipeline_outputs,
    build_pipeline_summary,
    clear_generated_layout_overrides,
    file_bytes,
    has_sparse_layout,
    run_cmd,
)
from report_contract import normalize_chart_id, numeric_chart_id
from recommendation_state import parse_recommendations


PROTECTED_FILES = [
    "content.html",
    "DESIGN_BRIEF.md",
    "DESIGN_BRIEF.json",
    "RECOMMENDATIONS.md",
    "RECOMMENDATIONS.storyboard.md",
    "RECOMMENDATIONS.json",
    "RECOMMENDATIONS.normalized.json",
    "ANCHOR_INDEX.json",
    "ANCHOR_MATCH_REPORT.json",
    "RECOMMENDATION_PREP.json",
    "VALIDATION.md",
]


def parse_id_filter(raw: str) -> set[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    result: set[str] = set()
    for item in values:
        chart_id = normalize_chart_id(item)
        if chart_id:
            result.add(chart_id)
    return result


def select_chart_ids(recommendations: list[dict[str, Any]], id_filter: set[str] | None = None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for rec in recommendations:
        chart_id = normalize_chart_id(rec.get("id"))
        if not chart_id:
            continue
        if id_filter and chart_id not in id_filter:
            continue
        if chart_id in seen:
            continue
        seen.add(chart_id)
        ordered.append(chart_id)
    return ordered


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def snapshot_protected(report_dir: Path) -> dict[str, tuple[bool, int, int]]:
    snapshot: dict[str, tuple[bool, int, int]] = {}
    for name in PROTECTED_FILES:
        path = report_dir / name
        if path.exists() and path.is_file():
            stat = path.stat()
            snapshot[name] = (True, stat.st_size, int(stat.st_mtime_ns))
        else:
            snapshot[name] = (False, 0, 0)
    return snapshot


def assert_protected_unchanged(report_dir: Path, before: dict[str, tuple[bool, int, int]]) -> None:
    for name, old in before.items():
        path = report_dir / name
        existed_before, old_size, old_mtime = old
        exists_now = path.exists() and path.is_file()
        if existed_before and not exists_now:
            raise SystemExit(f"[ERROR] 并行阶段修改了受保护文件（被删除）：{name}")
        if not existed_before and exists_now:
            raise SystemExit(f"[ERROR] 并行阶段修改了受保护文件（新增创建）：{name}")
        if not existed_before:
            continue
        stat = path.stat()
        now = (stat.st_size, int(stat.st_mtime_ns))
        if now != (old_size, old_mtime):
            raise SystemExit(f"[ERROR] 并行阶段修改了受保护文件：{name}")


def snapshot_fragment_outputs(report_dir: Path) -> dict[str, tuple[int, int]]:
    fragments_dir = report_dir / "chart-fragments"
    snapshot: dict[str, tuple[int, int]] = {}
    if not fragments_dir.exists() or not fragments_dir.is_dir():
        return snapshot
    for path in sorted(path for path in fragments_dir.glob("*.html") if path.is_file()):
        stat = path.stat()
        snapshot[path.name] = (stat.st_size, int(stat.st_mtime_ns))
    return snapshot


def assert_batch_fragment_ownership(
    report_dir: Path,
    before: dict[str, tuple[int, int]],
    allowed_chart_ids: list[str],
) -> None:
    after = snapshot_fragment_outputs(report_dir)
    allowed_names = {f"{chart_id}.html" for chart_id in allowed_chart_ids}
    all_names = set(before) | set(after)
    for name in sorted(all_names):
        if name in allowed_names:
            continue
        previous = before.get(name)
        current = after.get(name)
        if previous is None and current is not None:
            raise SystemExit(f"[ERROR] 并行阶段写入了非本批次片段：{name}")
        if previous is not None and current is None:
            raise SystemExit(f"[ERROR] 并行阶段删除了非本批次片段：{name}")
        if previous != current:
            raise SystemExit(f"[ERROR] 并行阶段修改了非本批次片段：{name}")


def run_worker(worker_cmd: str, report_dir: Path, chart_id: str) -> tuple[str, int, str, str]:
    fragment_path = report_dir / "chart-fragments" / f"{chart_id}.html"
    values = {
        "report_dir": str(report_dir),
        "chart_id": chart_id,
        "id": numeric_chart_id(chart_id),
        "fragment_path": str(fragment_path),
    }
    command = build_worker_command(worker_cmd, values)
    proc = subprocess.run(command, text=True, capture_output=True)
    return chart_id, proc.returncode, proc.stdout, proc.stderr


def build_worker_command(worker_cmd: str, values: dict[str, str]) -> list[str]:
    template_parts = shlex.split(worker_cmd)
    return [part.format(**values) for part in template_parts]


def validate_batch_outputs(report_dir: Path, batch_ids: list[str]) -> None:
    errors: list[str] = []
    warnings: list[str] = []
    rec_types = load_recommendation_types(report_dir)
    contracts_payload = load_contracts()
    for chart_id in batch_ids:
        path = report_dir / "chart-fragments" / f"{chart_id}.html"
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"{chart_id}: 片段文件缺失或为空")
            continue
        file_errors, file_warnings = lint_fragment(path, visual_type=rec_types.get(chart_id, ""), contracts_payload=contracts_payload)
        errors.extend(file_errors)
        warnings.extend(file_warnings)
    for item in warnings:
        print(f"[WARN] {item}")
    if errors:
        for item in errors:
            print(f"[ERROR] {item}")
        raise SystemExit("[FAIL] 批次片段质量检查未通过")


def run_status_cmd(tracker: PipelineStatusTracker, stage: str, cmd: list[str]) -> None:
    tracker.start_stage(stage, {"command": cmd})
    run_cmd(cmd)
    tracker.finish_stage(stage)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run parallel guarded md2report pipeline")
    parser.add_argument("report_dir", help="Report workspace directory")
    parser.add_argument("report_name", help="Output report basename without extension")
    parser.add_argument("--worker-cmd", required=True, help="Command template for one chart fragment task")
    parser.add_argument("--max-workers", type=int, default=3, help="Max concurrent workers for a batch")
    parser.add_argument("--batch-size", type=int, default=3, help="Charts per batch")
    parser.add_argument("--ids", help="Optional comma-separated chart ids (e.g. C1,C2,3)")
    parser.add_argument("--skip-export", action="store_true", help="Only assemble HTML, skip PDF export")
    parser.add_argument("--skip-layout-repair", action="store_true", help="Skip layout diagnosis and automatic repair loop")
    args = parser.parse_args(argv[1:])

    if args.max_workers < 1:
        raise SystemExit("[ERROR] --max-workers 必须 >= 1")
    if args.batch_size < 1:
        raise SystemExit("[ERROR] --batch-size 必须 >= 1")

    script_dir = Path(__file__).resolve().parent
    report_dir = Path(args.report_dir).expanduser().resolve()
    if not report_dir.exists() or not report_dir.is_dir():
        raise SystemExit(f"[ERROR] 报告目录不存在：{report_dir}")

    tracker = PipelineStatusTracker(
        report_dir / "PIPELINE_STATUS.json",
        mode="parallel",
        report_dir=report_dir,
        report_name=args.report_name,
        options={
            "workerCmd": args.worker_cmd,
            "maxWorkers": args.max_workers,
            "batchSize": args.batch_size,
            "ids": args.ids or "",
            "skipExport": args.skip_export,
            "skipLayoutRepair": args.skip_layout_repair,
        },
    )

    python = sys.executable
    check = script_dir / "check_phase_contract.py"
    build_anchor_index = script_dir / "build_anchor_index.py"
    prepare_recommendations = script_dir / "prepare_recommendations.py"
    normalize_fragments = script_dir / "normalize_fragments.py"
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

        tracker.start_stage("clear-layout-overrides")
        clear_generated_layout_overrides(report_dir)
        tracker.finish_stage("clear-layout-overrides")

        recommendations = parse_recommendations(
            str(report_dir),
            normalize_chart_id=normalize_chart_id,
            read_file=lambda path: Path(path).read_text(encoding="utf-8", errors="ignore"),
        )
        id_filter = parse_id_filter(args.ids) if args.ids else None
        chart_ids = select_chart_ids(recommendations, id_filter=id_filter)
        if not chart_ids:
            raise SystemExit("[ERROR] 没有可生成的 recommendation id")

        fragments_dir = report_dir / "chart-fragments"
        fragments_dir.mkdir(parents=True, exist_ok=True)
        protected_before = snapshot_protected(report_dir)

        batches = chunked(chart_ids, args.batch_size)
        print(f"[INFO] 并行阶段：{len(chart_ids)} 个片段，{len(batches)} 批，max_workers={args.max_workers}")

        for index, batch in enumerate(batches, start=1):
            stage_name = f"parallel-batch-{index}"
            batch_fragment_snapshot = snapshot_fragment_outputs(report_dir)
            tracker.start_stage(stage_name, {"batch": batch})
            print(f"[INFO] 开始批次 {index}/{len(batches)}: {', '.join(batch)}")
            futures = []
            with ThreadPoolExecutor(max_workers=min(args.max_workers, len(batch))) as pool:
                for chart_id in batch:
                    futures.append(pool.submit(run_worker, args.worker_cmd, report_dir, chart_id))
                failed = False
                for future in as_completed(futures):
                    chart_id, returncode, stdout, stderr = future.result()
                    if returncode != 0:
                        failed = True
                        print(f"[ERROR] worker 失败：{chart_id} rc={returncode}")
                        if stdout.strip():
                            print("[STDOUT] " + stdout.strip())
                        if stderr.strip():
                            print("[STDERR] " + stderr.strip())
                    else:
                        print(f"[OK] worker 完成：{chart_id}")
                if failed:
                    raise SystemExit("[FAIL] 并行批次执行失败")

            assert_protected_unchanged(report_dir, protected_before)
            assert_batch_fragment_ownership(report_dir, batch_fragment_snapshot, batch)
            run_status_cmd(tracker, f"normalize-batch-{index}", [python, str(normalize_fragments), str(report_dir), "--ids", ",".join(batch)])
            assert_protected_unchanged(report_dir, protected_before)
            assert_batch_fragment_ownership(report_dir, batch_fragment_snapshot, batch)
            validate_batch_outputs(report_dir, batch)
            tracker.finish_stage(stage_name, {"batch": batch})

        run_status_cmd(tracker, "normalize-fragments", [python, str(normalize_fragments), str(report_dir)])
        tracker.start_stage("lint-fragments")
        all_errors, all_warnings, count = lint_report_dir(report_dir)
        print(f"[INFO] 全量片段质量复核：{count} 个片段")
        for item in all_warnings:
            print(f"[WARN] {item}")
        if all_errors:
            for item in all_errors:
                print(f"[ERROR] {item}")
            raise SystemExit("[FAIL] 全量片段质量复核失败")
        tracker.finish_stage("lint-fragments", {"count": count, "warnings": len(all_warnings)})

        run_status_cmd(tracker, "gate-before-assemble", [python, str(check), str(report_dir), "before-assemble"])
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
            print("[DONE] 并行流水线完成（已跳过 PDF 导出）")
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
    print("[DONE] 并行流水线完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
