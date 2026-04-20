import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from assembly_output import compute_validation_summary, extract_report_title, find_duplicate_chart_ids


def strip_tags_local(value: str) -> str:
    import re

    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(value.split())


class AssemblyOutputTests(unittest.TestCase):
    def test_extract_report_title_prefers_h1(self) -> None:
        html = "<section><h1>PS6 报告</h1><p>正文</p></section>"
        self.assertEqual(extract_report_title(html, "fallback", strip_tags=strip_tags_local), "PS6 报告")

    def test_find_duplicate_chart_ids_returns_sorted_duplicates(self) -> None:
        html = '<div id="chart-C2"></div><div id="chart-C1"></div><div id="chart-C2"></div><div id="chart-C1"></div>'
        self.assertEqual(find_duplicate_chart_ids(html), ["chart-C1", "chart-C2"])

    def test_compute_validation_summary_flags_structural_residue(self) -> None:
        html = (
            '<section class="report-cover"></section>'
            '<div class="visual-row"></div>'
            '<div id="chart-C1"></div><div id="chart-C1"></div>'
            '<p><div>bad</div></p>'
            '<script>downloadChart()</script>'
        )
        results = [
            SimpleNamespace(status="OK", chart_id="C1", anchor="A", message="ok"),
            SimpleNamespace(status="WARN", chart_id="C2", anchor="B", message="warn"),
        ]

        summary = compute_validation_summary(html, results)

        self.assertEqual(summary["injected"], 1)
        self.assertEqual(summary["residual_p_block"], 1)
        self.assertEqual(summary["residual_download"], 1)
        self.assertEqual(summary["duplicate_ids"], ["chart-C1"])
        self.assertEqual(summary["visual_rows"], 1)
        self.assertTrue(summary["cover_protected"])
        self.assertFalse(summary["all_passed"])

    def test_compute_validation_summary_rejects_visual_before_cover(self) -> None:
        html = (
            '<div class="visual-block"></div>'
            '<section class="report-cover"></section>'
        )

        summary = compute_validation_summary(html, [])

        self.assertTrue(summary["cover_present"])
        self.assertFalse(summary["cover_protected"])
        self.assertFalse(summary["all_passed"])


if __name__ == "__main__":
    unittest.main()
