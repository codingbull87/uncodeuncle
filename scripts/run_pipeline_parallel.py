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
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from assemble_engine import normalize_chart_id, numeric_chart_id, parse_recommendations
from lint_fragments import lint_fragment, lint_report_dir, load_contracts, load_recommendation_types


PROTECTED_FILES = [
    "content.html",
    "DESIGN_BRIEF.md",
    "DESIGN_BRIEF.json",
    "RECOMMENDATIONS.md",
    "RECOMMENDATIONS.json",
    "VALIDATION.md",
]


def run_cmd(cmd: list[str]) -> None:
    print("[RUN] " + " ".join(cmd))
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


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


def snapshot_protected(report_dir: Path) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for name in PROTECTED_FILES:
        path = report_dir / name
        if path.exists() and path.is_file():
            stat = path.stat()
            snapshot[name] = (stat.st_size, int(stat.st_mtime_ns))
    return snapshot


def assert_protected_unchanged(report_dir: Path, before: dict[str, tuple[int, int]]) -> None:
    for name, old in before.items():
        path = report_dir / name
        if not path.exists():
            raise SystemExit(f"[ERROR] 并行阶段修改了受保护文件（被删除）：{name}")
        stat = path.stat()
        now = (stat.st_size, int(stat.st_mtime_ns))
        if now != old:
            raise SystemExit(f"[ERROR] 并行阶段修改了受保护文件：{name}")


def run_worker(worker_cmd: str, report_dir: Path, chart_id: str) -> tuple[str, int, str, str]:
    fragment_path = report_dir / "chart-fragments" / f"{chart_id}.html"
    command = worker_cmd.format(
        report_dir=str(report_dir),
        chart_id=chart_id,
        id=numeric_chart_id(chart_id),
        fragment_path=str(fragment_path),
    )
    proc = subprocess.run(command, shell=True, text=True, capture_output=True)
    return chart_id, proc.returncode, proc.stdout, proc.stderr


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


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run parallel guarded report-illustrator pipeline")
    parser.add_argument("report_dir", help="Report workspace directory")
    parser.add_argument("report_name", help="Output report basename without extension")
    parser.add_argument("--worker-cmd", required=True, help="Command template for one chart fragment task")
    parser.add_argument("--max-workers", type=int, default=3, help="Max concurrent workers for a batch")
    parser.add_argument("--batch-size", type=int, default=3, help="Charts per batch")
    parser.add_argument("--ids", help="Optional comma-separated chart ids (e.g. C1,C2,3)")
    parser.add_argument("--skip-export", action="store_true", help="Only assemble HTML, skip PDF export")
    args = parser.parse_args(argv[1:])

    if args.max_workers < 1:
        raise SystemExit("[ERROR] --max-workers 必须 >= 1")
    if args.batch_size < 1:
        raise SystemExit("[ERROR] --batch-size 必须 >= 1")

    script_dir = Path(__file__).resolve().parent
    report_dir = Path(args.report_dir).expanduser().resolve()
    if not report_dir.exists() or not report_dir.is_dir():
        raise SystemExit(f"[ERROR] 报告目录不存在：{report_dir}")

    python = sys.executable
    check = script_dir / "check_phase_contract.py"
    assemble = script_dir / "assemble.py"
    export = script_dir / "export_pdf.py"
    qa_html = script_dir / "qa_html.py"
    qa_pdf = script_dir / "qa_pdf.py"

    run_cmd([python, str(check), str(report_dir), "before-fragments"])

    recommendations = parse_recommendations(str(report_dir))
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
        validate_batch_outputs(report_dir, batch)

    all_errors, all_warnings, count = lint_report_dir(report_dir)
    print(f"[INFO] 全量片段质量复核：{count} 个片段")
    for item in all_warnings:
        print(f"[WARN] {item}")
    if all_errors:
        for item in all_errors:
            print(f"[ERROR] {item}")
        raise SystemExit("[FAIL] 全量片段质量复核失败")

    run_cmd([python, str(check), str(report_dir), "before-assemble"])
    run_cmd([python, str(assemble), str(report_dir), args.report_name + "_illustrated"])
    run_cmd([python, str(qa_html), str(report_dir)])

    if args.skip_export:
        print("[DONE] 并行流水线完成（已跳过 PDF 导出）")
        return 0

    run_cmd([python, str(check), str(report_dir), "before-export"])
    html_path = report_dir / f"{args.report_name}_illustrated.html"
    pdf_path = report_dir / f"{args.report_name}_illustrated.pdf"
    run_cmd([python, str(qa_pdf), str(html_path), str(report_dir / "PDF_QA.json")])
    run_cmd([python, str(export), str(html_path), str(pdf_path)])
    print("[DONE] 并行流水线完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
