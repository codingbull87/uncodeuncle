import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import run_pipeline
import run_pipeline_parallel
from qa_pdf import evaluate_pages


def command_name(cmd: list[str]) -> str:
    return Path(cmd[1]).name if len(cmd) > 1 else ""


class PipelineEntrypointTests(unittest.TestCase):
    def make_report_dir(self) -> Path:
        tempdir = tempfile.TemporaryDirectory(prefix="ri-pipeline-entry-")
        self.addCleanup(tempdir.cleanup)
        return Path(tempdir.name)

    def write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def serial_side_effect(
        self,
        report_dir: Path,
        report_name: str,
        *,
        layout_payload: dict,
        pdf_payload: dict | None = None,
    ):
        def _runner(cmd: list[str]) -> None:
            name = command_name(cmd)
            if name == "assemble.py":
                (report_dir / f"{report_name}_illustrated.html").write_text("<html><body><main>ok</main></body></html>", encoding="utf-8")
                self.write_json(report_dir / "ASSEMBLY_DIAGNOSTICS.json", {"pass": True})
            elif name == "check_phase_contract.py":
                stage = cmd[3]
                self.write_json(report_dir / f"GATE_STATUS.{stage}.json", {"pass": True})
            elif name == "qa_layout.py":
                self.write_json(Path(cmd[3]), layout_payload)
            elif name == "export_pdf.py":
                Path(cmd[3]).write_bytes(b"%PDF-1.4\n")
                self.write_json(report_dir / "EXPORT_DIAGNOSTICS.json", {"page_count": pdf_payload.get("pageCount", 0) if pdf_payload else 0})
            elif name == "qa_pdf.py" and pdf_payload is not None:
                self.write_json(Path(cmd[3]), pdf_payload)
            elif name == "qa_visual.py":
                self.write_json(Path(cmd[4]), {"pass": True, "skipped": False, "metrics": {"rmse": 0.12}, "warnings": [], "errors": []})

        return _runner

    def test_run_pipeline_writes_success_status_when_skip_export(self) -> None:
        report_dir = self.make_report_dir()
        layout_payload = {
            "sparsePages": [],
            "terminalSparsePages": [],
            "summary": {"pageCount": 3, "maxBlankRatio": 0.32},
        }
        with patch("run_pipeline.run_cmd", side_effect=self.serial_side_effect(report_dir, "demo", layout_payload=layout_payload)):
            rc = run_pipeline.main(["run_pipeline.py", str(report_dir), "demo", "--skip-export", "--skip-layout-repair"])

        self.assertEqual(rc, 0)
        status = json.loads((report_dir / "PIPELINE_STATUS.json").read_text(encoding="utf-8"))
        self.assertTrue(status["success"])
        self.assertEqual(status["mode"], "serial")
        self.assertEqual(status["status"], "passed")
        self.assertIn("lint-fragments", status["completedStages"])
        self.assertEqual(status["summary"]["layout"]["pageCount"], 3)
        self.assertEqual(
            Path(status["outputs"]["html"]).resolve(),
            (report_dir / "demo_illustrated.html").resolve(),
        )

    def test_run_pipeline_marks_failure_when_terminal_sparse_page_survives(self) -> None:
        report_dir = self.make_report_dir()
        layout_payload = {
            "sparsePages": [],
            "terminalSparsePages": [{"page": 9}],
            "summary": {"pageCount": 9, "maxBlankRatio": 0.81},
        }
        with patch("run_pipeline.run_cmd", side_effect=self.serial_side_effect(report_dir, "demo", layout_payload=layout_payload)):
            with self.assertRaises(SystemExit):
                run_pipeline.main(["run_pipeline.py", str(report_dir), "demo"])

        status = json.loads((report_dir / "PIPELINE_STATUS.json").read_text(encoding="utf-8"))
        self.assertFalse(status["success"])
        self.assertEqual(status["status"], "failed")
        self.assertIn("layout repair", status["error"])
        self.assertEqual(status["summary"]["layout"]["terminalSparsePages"], 1)

    def test_run_pipeline_parallel_writes_success_status_when_skip_export(self) -> None:
        report_dir = self.make_report_dir()
        layout_payload = {
            "sparsePages": [],
            "terminalSparsePages": [],
            "summary": {"pageCount": 4, "maxBlankRatio": 0.41},
        }

        def fake_run_cmd(cmd: list[str]) -> None:
            name = command_name(cmd)
            if name == "assemble.py":
                (report_dir / "demo_illustrated.html").write_text("<html><body><main>ok</main></body></html>", encoding="utf-8")
                self.write_json(report_dir / "ASSEMBLY_DIAGNOSTICS.json", {"pass": True})
            elif name == "check_phase_contract.py":
                stage = cmd[3]
                self.write_json(report_dir / f"GATE_STATUS.{stage}.json", {"pass": True})
            elif name == "qa_layout.py":
                self.write_json(Path(cmd[3]), layout_payload)
            elif name == "qa_visual.py":
                self.write_json(Path(cmd[4]), {"pass": True, "skipped": False, "metrics": {"rmse": 0.11}, "warnings": [], "errors": []})

        with (
            patch("run_pipeline_parallel.run_cmd", side_effect=fake_run_cmd),
            patch("run_pipeline_parallel.parse_recommendations", return_value=[{"id": "1"}]),
            patch("run_pipeline_parallel.run_worker", return_value=("C1", 0, "", "")),
            patch("run_pipeline_parallel.validate_batch_outputs", return_value=None),
            patch("run_pipeline_parallel.lint_report_dir", return_value=([], [], 1)),
        ):
            rc = run_pipeline_parallel.main(
                [
                    "run_pipeline_parallel.py",
                    str(report_dir),
                    "demo",
                    "--worker-cmd",
                    "python3 worker.py {report_dir} {chart_id}",
                    "--skip-export",
                    "--skip-layout-repair",
                ]
            )

        self.assertEqual(rc, 0)
        status = json.loads((report_dir / "PIPELINE_STATUS.json").read_text(encoding="utf-8"))
        self.assertTrue(status["success"])
        self.assertEqual(status["mode"], "parallel")
        self.assertIn("parallel-batch-1", status["completedStages"])
        self.assertEqual(status["summary"]["layout"]["pageCount"], 4)

    def test_pdf_qa_cross_checks_layout_page_count(self) -> None:
        report_dir = self.make_report_dir()
        pdf_path = report_dir / "sample.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")
        self.write_json(report_dir / "LAYOUT_DIAGNOSIS.json", {"summary": {"pageCount": 3}})
        pages = [
            {"page": 1, "widthPt": 595.0, "heightPt": 842.0, "rotation": 0, "textChars": 10, "textPreview": "a"},
            {"page": 2, "widthPt": 595.0, "heightPt": 842.0, "rotation": 0, "textChars": 12, "textPreview": "b"},
        ]
        errors, warnings = evaluate_pages(pages, pdf_path)
        self.assertFalse(warnings)
        self.assertTrue(any("LAYOUT_DIAGNOSIS.json" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
