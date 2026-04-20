#!/usr/bin/env python3
"""
Shared helpers for guarded md2report pipeline entrypoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path
from typing import Any


def run_cmd(cmd: list[str]) -> None:
    print("[RUN] " + " ".join(cmd))
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def sparse_pages(layout_diag_path: Path) -> int:
    payload = read_json(layout_diag_path)
    items = payload.get("sparsePages", [])
    return len(items) if isinstance(items, list) else 0


def terminal_sparse_pages(layout_diag_path: Path) -> int:
    payload = read_json(layout_diag_path)
    items = payload.get("terminalSparsePages", [])
    return len(items) if isinstance(items, list) else 0


def has_sparse_layout(layout_diag_path: Path) -> bool:
    return sparse_pages(layout_diag_path) > 0 or terminal_sparse_pages(layout_diag_path) > 0


def clear_generated_layout_overrides(report_dir: Path) -> None:
    path = report_dir / "LAYOUT_OVERRIDES.json"
    if path.exists():
        path.unlink()


def file_bytes(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


def persist_pipeline_status(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class PipelineStatusTracker:
    def __init__(
        self,
        path: Path,
        *,
        mode: str,
        report_dir: Path,
        report_name: str,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.path = path
        self.payload: dict[str, Any] = {
            "schema": "report-illustrator-pipeline-status:v1",
            "mode": mode,
            "reportDir": str(report_dir),
            "reportName": report_name,
            "startedAt": utc_timestamp(),
            "updatedAt": "",
            "currentStage": "",
            "status": "running",
            "success": None,
            "error": "",
            "options": options or {},
            "completedStages": [],
            "events": [],
            "outputs": {},
            "summary": {},
        }
        self._write()

    def _write(self) -> None:
        self.payload["updatedAt"] = utc_timestamp()
        persist_pipeline_status(self.path, self.payload)

    def start_stage(self, name: str, details: dict[str, Any] | None = None) -> None:
        self.payload["currentStage"] = name
        event = {
            "stage": name,
            "status": "running",
            "at": utc_timestamp(),
        }
        if details:
            event["details"] = details
        self.payload["events"].append(event)
        self._write()

    def finish_stage(self, name: str, details: dict[str, Any] | None = None) -> None:
        if name not in self.payload["completedStages"]:
            self.payload["completedStages"].append(name)
        event = {
            "stage": name,
            "status": "ok",
            "at": utc_timestamp(),
        }
        if details:
            event["details"] = details
        self.payload["events"].append(event)
        self._write()

    def fail(self, error: str, *, stage: str | None = None, outputs: dict[str, Any] | None = None, summary: dict[str, Any] | None = None) -> None:
        if stage:
            self.payload["currentStage"] = stage
        self.payload["status"] = "failed"
        self.payload["success"] = False
        self.payload["error"] = error
        if outputs is not None:
            self.payload["outputs"] = outputs
        if summary is not None:
            self.payload["summary"] = summary
        self.payload["events"].append(
            {
                "stage": self.payload.get("currentStage") or stage or "unknown",
                "status": "failed",
                "at": utc_timestamp(),
                "details": {"error": error},
            }
        )
        self._write()

    def succeed(self, *, outputs: dict[str, Any] | None = None, summary: dict[str, Any] | None = None) -> None:
        self.payload["status"] = "passed"
        self.payload["success"] = True
        self.payload["error"] = ""
        self.payload["currentStage"] = "done"
        if outputs is not None:
            self.payload["outputs"] = outputs
        if summary is not None:
            self.payload["summary"] = summary
        self.payload["events"].append(
            {
                "stage": "done",
                "status": "ok",
                "at": utc_timestamp(),
            }
        )
        self._write()


def build_pipeline_outputs(report_dir: Path, report_name: str, *, include_pdf: bool) -> dict[str, Any]:
    outputs = {
        "html": str(report_dir / f"{report_name}_illustrated.html"),
        "layoutDiagnosis": str(report_dir / "LAYOUT_DIAGNOSIS.json"),
        "layoutOverrides": str(report_dir / "LAYOUT_OVERRIDES.json"),
        "assemblyDiagnostics": str(report_dir / "ASSEMBLY_DIAGNOSTICS.json"),
        "gateBeforeFragments": str(report_dir / "GATE_STATUS.before-fragments.json"),
        "gateBeforeAssemble": str(report_dir / "GATE_STATUS.before-assemble.json"),
        "gateBeforeExport": str(report_dir / "GATE_STATUS.before-export.json"),
    }
    if include_pdf:
        outputs["pdf"] = str(report_dir / f"{report_name}_illustrated.pdf")
        outputs["pdfQa"] = str(report_dir / "PDF_QA.json")
        outputs["visualQa"] = str(report_dir / "VISUAL_QA.json")
        outputs["exportDiagnostics"] = str(report_dir / "EXPORT_DIAGNOSTICS.json")
    return outputs


def build_pipeline_summary(report_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    layout_payload = read_json(report_dir / "LAYOUT_DIAGNOSIS.json")
    if layout_payload:
        layout_summary = layout_payload.get("summary", {})
        summary["layout"] = {
            "pageCount": layout_summary.get("pageCount") or layout_summary.get("totalPages"),
            "sparsePages": len(layout_payload.get("sparsePages", []) or []),
            "terminalSparsePages": len(layout_payload.get("terminalSparsePages", []) or []),
            "maxBlankRatio": layout_summary.get("maxBlankRatio"),
        }
    pdf_payload = read_json(report_dir / "PDF_QA.json")
    if pdf_payload:
        summary["pdf"] = {
            "pass": pdf_payload.get("pass"),
            "pageCount": pdf_payload.get("pageCount"),
            "warnings": len(pdf_payload.get("warnings", []) or []),
            "errors": len(pdf_payload.get("errors", []) or []),
        }
    visual_payload = read_json(report_dir / "VISUAL_QA.json")
    if visual_payload:
        summary["visual"] = {
            "pass": visual_payload.get("pass"),
            "skipped": visual_payload.get("skipped"),
            "rmse": (visual_payload.get("metrics", {}) if isinstance(visual_payload.get("metrics"), dict) else {}).get("rmse"),
            "warnings": len(visual_payload.get("warnings", []) or []),
            "errors": len(visual_payload.get("errors", []) or []),
        }
    return summary
