import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from check_phase_contract import check_before_export
from insertion_planner import iter_heading_matches
from prepare_recommendations import prepare_recommendations
from qa_layout import has_following_text_after_visual
from repair_layout import repair_terminal_sparse_pages, reflow_prev_visual_into_terminal_heading
from report_contract import strip_tags
from run_pipeline_parallel import (
    assert_batch_fragment_ownership,
    assert_protected_unchanged,
    build_worker_command,
    snapshot_fragment_outputs,
    snapshot_protected,
)


class RobustnessFixTests(unittest.TestCase):
    def test_heading_matching_supports_h5_and_h6(self) -> None:
        html = "<h5>深层标题</h5><p>正文</p><h6>更深标题</h6>"
        self.assertEqual(len(iter_heading_matches(html, "深层标题", strip_tags=strip_tags)), 1)
        self.assertEqual(len(iter_heading_matches(html, "更深标题", strip_tags=strip_tags)), 1)

    def test_prepare_recommendations_does_not_rewrite_authoritative_json_on_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-prepare-txn-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "content.html").write_text("<h2>存在标题</h2><p>正文</p>", encoding="utf-8")
            original = [
                {
                    "id": "1",
                    "type": "bar_compare",
                    "anchor": "不存在的标题",
                    "position": "after_heading",
                }
            ]
            original_text = json.dumps(original, ensure_ascii=False, indent=2) + "\n"
            (report_dir / "RECOMMENDATIONS.json").write_text(original_text, encoding="utf-8")

            _items, _warnings, errors, _source = prepare_recommendations(report_dir)

            self.assertTrue(errors)
            self.assertEqual((report_dir / "RECOMMENDATIONS.json").read_text(encoding="utf-8"), original_text)
            self.assertFalse((report_dir / "RECOMMENDATIONS.normalized.json").exists())
            self.assertTrue((report_dir / "RECOMMENDATION_PREP.json").exists())
            self.assertTrue((report_dir / "ANCHOR_MATCH_REPORT.json").exists())

    def test_parallel_worker_command_preserves_spacey_paths_without_shell(self) -> None:
        values = {
            "report_dir": "/tmp/report dir",
            "chart_id": "C7",
            "id": "7",
            "fragment_path": "/tmp/report dir/chart-fragments/C7.html",
        }
        command = build_worker_command(
            "python3 worker.py {report_dir} {fragment_path} {chart_id} {id}",
            values,
        )
        self.assertEqual(
            command,
            [
                "python3",
                "worker.py",
                "/tmp/report dir",
                "/tmp/report dir/chart-fragments/C7.html",
                "C7",
                "7",
            ],
        )

    def test_parallel_protected_guard_blocks_newly_created_protected_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-protected-guard-") as temp_dir:
            report_dir = Path(temp_dir)
            before = snapshot_protected(report_dir)
            (report_dir / "RECOMMENDATIONS.md").write_text("# unexpected\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                assert_protected_unchanged(report_dir, before)
            self.assertIn("新增创建", str(ctx.exception))

    def test_parallel_fragment_guard_allows_only_current_batch_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-fragment-guard-ok-") as temp_dir:
            report_dir = Path(temp_dir)
            fragments_dir = report_dir / "chart-fragments"
            fragments_dir.mkdir(parents=True)
            (fragments_dir / "C1.html").write_text("<div>old-1</div>", encoding="utf-8")
            (fragments_dir / "C2.html").write_text("<div>old-2</div>", encoding="utf-8")
            before = snapshot_fragment_outputs(report_dir)

            (fragments_dir / "C1.html").write_text("<div>new-1</div>", encoding="utf-8")
            assert_batch_fragment_ownership(report_dir, before, ["C1"])

    def test_parallel_fragment_guard_blocks_non_batch_fragment_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-fragment-guard-fail-") as temp_dir:
            report_dir = Path(temp_dir)
            fragments_dir = report_dir / "chart-fragments"
            fragments_dir.mkdir(parents=True)
            (fragments_dir / "C1.html").write_text("<div>old-1</div>", encoding="utf-8")
            (fragments_dir / "C2.html").write_text("<div>old-2</div>", encoding="utf-8")
            before = snapshot_fragment_outputs(report_dir)

            (fragments_dir / "C2.html").write_text("<div>new-2</div>", encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                assert_batch_fragment_ownership(report_dir, before, ["C1"])
            self.assertIn("非本批次片段", str(ctx.exception))

    def test_before_export_blocks_terminal_sparse_pages(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-terminal-gate-") as temp_dir:
            report_dir = Path(temp_dir)
            html_path = report_dir / "sample_illustrated.html"
            html_path.write_text("<html><body><main>ok</main></body></html>", encoding="utf-8")
            (report_dir / "LAYOUT_DIAGNOSIS.json").write_text(
                json.dumps({"sparsePages": [], "terminalSparsePages": [{"page": 9}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            with (
                patch("check_phase_contract.check_before_assemble", return_value=([], [])),
                patch("check_phase_contract.find_html", return_value=html_path),
                patch("check_phase_contract.run_qa", return_value=([], [], {})),
            ):
                errors, _warnings = check_before_export(report_dir)
            self.assertTrue(any("末页稀疏页" in item for item in errors))

    def test_repair_terminal_sparse_page_restores_raw_position_for_single_low_info_visual(self) -> None:
        raw_items = [
            {
                "id": "C10",
                "type": "risk_matrix",
                "position": "after_heading",
                "layout": "full",
                "size": "small",
                "keep_with_next": True,
                "can_shrink": False,
                "max_shrink_ratio": 0.22,
                "print_compact": False,
            }
        ]
        effective_items = [
            {
                "id": "C10",
                "type": "risk_matrix",
                "position": "section_end",
                "layout": "compact",
                "size": "compact",
                "keep_with_next": False,
                "can_shrink": True,
                "max_shrink_ratio": 0.30,
                "print_compact": True,
            }
        ]
        diagnosis = {
            "terminalSparsePages": [
                {
                    "page": 10,
                    "pageBlocks": [
                        {
                            "chartId": "C10",
                        }
                    ]
                }
            ]
        }

        repaired = repair_terminal_sparse_pages(raw_items, effective_items, diagnosis)

        self.assertEqual(repaired[0]["position"], "after_heading")
        self.assertEqual(repaired[0]["layout"], "full")
        self.assertEqual(repaired[0]["size"], "small")
        self.assertEqual(repaired[0]["keep_with_next"], True)
        self.assertFalse(repaired[0]["print_compact"])
        self.assertIn("restore_terminal_visual_to_raw_position:C10", diagnosis["appliedActions"])

    def test_reflow_prev_visual_into_terminal_heading_reanchors_visual(self) -> None:
        raw_items = [
            {
                "id": "C10",
                "type": "risk_matrix",
                "anchor": "投资结论与风险",
                "group": "risk-row",
                "group_anchor": "投资结论与风险",
                "row_anchor": "投资结论与风险",
                "anchor_occurrence": 1,
                "position": "after_heading",
                "layout": "half",
                "size": "small",
                "keep_with_next": True,
                "can_shrink": False,
                "max_shrink_ratio": 0.22,
                "print_compact": False,
            },
            {
                "id": "C11",
                "type": "risk_matrix",
                "anchor": "投资结论与风险",
                "group": "risk-row",
                "group_anchor": "投资结论与风险",
                "row_anchor": "投资结论与风险",
                "anchor_occurrence": 1,
                "position": "after_heading",
                "layout": "half",
                "size": "small",
                "keep_with_next": True,
                "can_shrink": False,
                "max_shrink_ratio": 0.22,
                "print_compact": False,
            },
        ]
        effective_items = [
            {
                "id": "C10",
                "type": "risk_matrix",
                "anchor": "投资结论与风险",
                "group": "risk-row",
                "group_anchor": "投资结论与风险",
                "row_anchor": "投资结论与风险",
                "anchor_occurrence": 1,
                "position": "after_heading",
                "layout": "compact",
                "size": "compact",
                "keep_with_next": False,
                "can_shrink": True,
                "max_shrink_ratio": 0.30,
                "print_compact": True,
            },
            {
                "id": "C11",
                "type": "risk_matrix",
                "anchor": "投资结论与风险",
                "group": "risk-row",
                "group_anchor": "投资结论与风险",
                "row_anchor": "投资结论与风险",
                "anchor_occurrence": 1,
                "position": "after_heading",
                "layout": "compact",
                "size": "compact",
                "keep_with_next": False,
                "can_shrink": True,
                "max_shrink_ratio": 0.30,
                "print_compact": True,
            },
        ]
        diagnosis = {
            "terminalSparsePages": [
                {
                    "previous_page_trailing_visual": {
                        "memberChartIds": ["C10", "C11"],
                    },
                    "first_terminal_block": {
                        "tag": "h5",
                        "text": "总体评级",
                    },
                }
            ]
        }

        repaired = reflow_prev_visual_into_terminal_heading(raw_items, effective_items, diagnosis)

        self.assertEqual(repaired[0]["anchor"], "总体评级")
        self.assertEqual(repaired[0]["group_anchor"], "总体评级")
        self.assertEqual(repaired[0]["row_anchor"], "总体评级")
        self.assertEqual(repaired[0]["anchor_occurrence"], 1)
        self.assertEqual(repaired[0]["position"], "after_heading")
        self.assertEqual(repaired[0]["layout"], "half")
        self.assertEqual(repaired[0]["size"], "small")
        self.assertEqual(repaired[0]["keep_with_next"], False)
        self.assertEqual(repaired[0]["can_shrink"], True)
        self.assertGreaterEqual(repaired[0]["max_shrink_ratio"], 0.30)
        self.assertEqual(repaired[1]["group_anchor"], "总体评级")
        self.assertEqual(repaired[1]["row_anchor"], "总体评级")
        self.assertIn("reflow_prev_visual_after_terminal_heading:C10", diagnosis["appliedActions"])
        self.assertIn("reflow_prev_visual_after_terminal_heading:C11", diagnosis["appliedActions"])

    def test_has_following_text_after_visual_stops_at_deep_heading(self) -> None:
        page_blocks = [
            {"domIndex": 1, "kind": "visual-block", "tag": "div"},
            {"domIndex": 2, "kind": "text", "tag": "h5", "text": "深层标题"},
            {"domIndex": 3, "kind": "text", "tag": "p", "text": "下一小节正文"},
        ]
        self.assertFalse(has_following_text_after_visual(page_blocks, page_blocks[0]))


if __name__ == "__main__":
    unittest.main()
