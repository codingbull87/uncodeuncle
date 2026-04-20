import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from qa_visual import build_visual_qa_html, classify_rmse, evaluate_visual_regression, parse_compare_metric


class VisualQATests(unittest.TestCase):
    def test_parse_compare_metric_extracts_normalized_rmse(self) -> None:
        self.assertEqual(parse_compare_metric("12584.1 (0.192021)"), 0.192021)
        self.assertIsNone(parse_compare_metric("n/a"))

    def test_classify_rmse_uses_warning_and_error_thresholds(self) -> None:
        errors, warnings = classify_rmse(0.19)
        self.assertFalse(errors)
        self.assertFalse(warnings)

        errors, warnings = classify_rmse(0.24)
        self.assertFalse(errors)
        self.assertTrue(any("视觉差异偏高" in item for item in warnings))

        errors, warnings = classify_rmse(0.31)
        self.assertTrue(any("视觉差异过大" in item for item in errors))

    def test_build_visual_qa_html_hides_export_button_and_triggers_beforeprint(self) -> None:
        source = "<html><head></head><body><button id='pdf-export-btn'>导出</button></body></html>"
        rendered = build_visual_qa_html(source)
        self.assertIn("ri-visual-qa-hide", rendered)
        self.assertIn("beforeprint", rendered)
        self.assertIn("#pdf-export-btn", rendered)

    def test_visual_qa_skipped_does_not_claim_pass(self) -> None:
        html_path = Path("/tmp/demo.html")
        pdf_path = Path("/tmp/demo.pdf")
        with patch("qa_visual.render_pdf_first_page", return_value=(False, "unsupported")):
            payload = evaluate_visual_regression(html_path, pdf_path)
        self.assertTrue(payload["skipped"])
        self.assertIsNone(payload["pass"])
        self.assertTrue(any("跳过视觉回归" in item for item in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
