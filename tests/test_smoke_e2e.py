import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from smoke_e2e import validate_outputs


class SmokeE2ETests(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_validate_outputs_accepts_successful_pipeline_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-smoke-e2e-") as temp_dir:
            workdir = Path(temp_dir)
            (workdir / "demo_illustrated.html").write_text("<html></html>", encoding="utf-8")
            (workdir / "demo_illustrated.pdf").write_bytes(b"%PDF-1.4\n")
            self.write_json(workdir / "PIPELINE_STATUS.json", {"success": True})
            self.write_json(workdir / "LAYOUT_DIAGNOSIS.json", {"sparsePages": [], "terminalSparsePages": [], "summary": {"pageCount": 5}})
            self.write_json(workdir / "PDF_QA.json", {"pass": True})
            self.write_json(workdir / "VISUAL_QA.json", {"pass": True, "skipped": False})

            validate_outputs(workdir, "demo")

    def test_validate_outputs_rejects_sparse_layout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-smoke-e2e-fail-") as temp_dir:
            workdir = Path(temp_dir)
            (workdir / "demo_illustrated.html").write_text("<html></html>", encoding="utf-8")
            (workdir / "demo_illustrated.pdf").write_bytes(b"%PDF-1.4\n")
            self.write_json(workdir / "PIPELINE_STATUS.json", {"success": True})
            self.write_json(workdir / "LAYOUT_DIAGNOSIS.json", {"sparsePages": [{"page": 3}], "terminalSparsePages": [], "summary": {"pageCount": 5}})
            self.write_json(workdir / "PDF_QA.json", {"pass": True})
            self.write_json(workdir / "VISUAL_QA.json", {"pass": True, "skipped": False})

            with self.assertRaises(SystemExit):
                validate_outputs(workdir, "demo")


if __name__ == "__main__":
    unittest.main()
