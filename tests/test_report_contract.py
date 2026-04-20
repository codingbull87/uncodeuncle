import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from report_contract import (
    heading_level,
    infer_page_role,
    is_heading_tag,
    normalize_anchor,
    normalize_chart_id,
    normalize_layout,
    normalize_size,
    numeric_chart_id,
    rec_can_shrink,
    rec_keep_with_next,
    rec_max_shrink_ratio,
)


class ReportContractTests(unittest.TestCase):
    def test_normalize_chart_id_and_numeric_chart_id(self) -> None:
        self.assertEqual(normalize_chart_id("7"), "C7")
        self.assertEqual(normalize_chart_id("c12"), "C12")
        self.assertEqual(numeric_chart_id("C12"), "12")

    def test_normalize_anchor_strips_markup_and_normalizes_quotes(self) -> None:
        value = '<strong>PS6“窗口”</strong>'
        self.assertEqual(normalize_anchor(value), 'PS6"窗口"')

    def test_layout_and_size_default_to_supported_values(self) -> None:
        self.assertEqual(normalize_layout("weird"), "full")
        self.assertEqual(normalize_size("giant"), "medium")

    def test_heading_helpers_cover_h1_to_h6(self) -> None:
        self.assertTrue(is_heading_tag("h5"))
        self.assertEqual(heading_level("H6"), 6)
        self.assertFalse(is_heading_tag("p"))
        self.assertIsNone(heading_level("section"))

    def test_page_role_and_compaction_defaults(self) -> None:
        self.assertEqual(infer_page_role({"layout": "half", "type": "bar_compare"}), "paired_visual")
        self.assertEqual(infer_page_role({"layout": "full", "type": "benchmark_table"}), "table_visual")
        self.assertFalse(rec_can_shrink({"type": "benchmark_table"}))
        self.assertTrue(rec_keep_with_next({"layout": "full"}))
        self.assertEqual(rec_max_shrink_ratio({"layout": "half"}), 0.18)


if __name__ == "__main__":
    unittest.main()
