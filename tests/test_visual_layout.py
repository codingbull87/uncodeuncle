import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from visual_layout import build_insertion_html, build_layout_plan, diagnose_group_assembly


class VisualLayoutTests(unittest.TestCase):
    def test_build_insertion_html_creates_equal_height_visual_row(self) -> None:
        insertions = [
            SimpleNamespace(
                pos=100,
                rec={"id": "C3", "group": "hardware", "layout": "half", "row_title": "硬件对比", "equal_height": True},
                fragment="<div>left</div>",
                anchor="Q2",
            ),
            SimpleNamespace(
                pos=100,
                rec={"id": "C4", "group": "hardware", "layout": "half", "equal_height": True},
                fragment="<div>right</div>",
                anchor="Q2",
            ),
        ]

        html = build_insertion_html(
            insertions,
            wrap_fragment_func=lambda rec, fragment: f"<single>{rec['id']}:{fragment}</single>",
            wrap_nested_fragment_func=lambda rec, fragment: f"<nested>{rec['id']}:{fragment}</nested>",
            normalize_layout=lambda value: str(value or "full").lower(),
            row_should_equal_height_func=lambda recs: True,
            html_escape=lambda text: text,
        )

        self.assertIn('class="visual-row visual-row-half visual-row-equal"', html)
        self.assertIn("硬件对比", html)
        self.assertIn("<nested>C3:<div>left</div></nested>", html)
        self.assertIn("<nested>C4:<div>right</div></nested>", html)

    def test_build_layout_plan_groups_members_into_single_visual_row_block(self) -> None:
        insertions = [
            SimpleNamespace(
                pos=200,
                rec={"id": "C5", "group": "subscription", "layout": "half", "size": "small"},
                fragment="",
                anchor="Q3",
            ),
            SimpleNamespace(
                pos=200,
                rec={"id": "C6", "group": "subscription", "layout": "half", "size": "small"},
                fragment="",
                anchor="Q3",
            ),
        ]

        plan = build_layout_plan(
            insertions,
            layout_block_factory=SimpleNamespace,
            normalize_chart_id=lambda value: str(value),
            normalize_layout=lambda value: str(value or "full").lower(),
            normalize_size=lambda value: str(value or "medium").lower(),
            infer_page_role=lambda rec: "paired_visual",
            rec_keep_with_next=lambda rec: False,
            rec_can_shrink=lambda rec: True,
            rec_max_shrink_ratio=lambda rec: 0.18,
            row_should_equal_height_func=lambda recs: False,
        )

        self.assertEqual(len(plan["blocks"]), 1)
        self.assertEqual(plan["blocks"][0]["block_id"], "C5+C6")
        self.assertEqual(plan["blocks"][0]["kind"], "visual-row")
        self.assertEqual(plan["blocks"][0]["layout"], "half")

    def test_diagnose_group_assembly_flags_split_group_positions(self) -> None:
        insertions = [
            SimpleNamespace(pos=10, rec={"id": "C3", "group": "hardware", "layout": "half"}, anchor="Q2"),
            SimpleNamespace(pos=20, rec={"id": "C4", "group": "hardware", "layout": "half"}, anchor="Q2"),
        ]

        diagnostics = diagnose_group_assembly(
            insertions,
            normalize_layout=lambda value: str(value or "full").lower(),
            normalize_chart_id=lambda value: str(value),
            injection_result_factory=lambda chart_id, anchor, status, message: {
                "chart_id": chart_id,
                "anchor": anchor,
                "status": status,
                "message": message,
            },
        )

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["status"], "WARN")
        self.assertIn("未形成并排", diagnostics[0]["message"])


if __name__ == "__main__":
    unittest.main()
