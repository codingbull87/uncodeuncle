import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from recommendation_loader import parse_recommendations_base
from prepare_recommendations import prepare_recommendations


class RecommendationPreparationTests(unittest.TestCase):
    def test_prepare_recommendations_builds_anchor_index_and_group_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-prepare-recs-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "content.html").write_text(
                "<h2>章节A</h2><p>正文。</p><h3>子节</h3><p>更多正文。</p>",
                encoding="utf-8",
            )
            payload = [
                {
                    "id": "1",
                    "type": "bar_compare",
                    "anchor": "章节A",
                    "position": "after_heading",
                    "layout": "half",
                    "group": "paired-a",
                },
                {
                    "id": "2",
                    "type": "insight_cards",
                    "anchor": "章节A",
                    "layout": "half",
                    "group": "paired-a",
                },
            ]
            (report_dir / "RECOMMENDATIONS.json").write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

            items, warnings, errors, source_name = prepare_recommendations(report_dir)

            self.assertEqual(source_name, "RECOMMENDATIONS.json")
            self.assertFalse(errors)
            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["anchor_id"], "h2_1")
            self.assertEqual(items[1]["position"], "after_heading")
            self.assertEqual(items[1]["group_anchor"], "章节A")
            rewritten = json.loads((report_dir / "RECOMMENDATIONS.json").read_text(encoding="utf-8"))
            self.assertEqual(rewritten[0]["id"], "C1")
            self.assertEqual(rewritten[0]["anchor_id"], "h2_1")
            self.assertTrue((report_dir / "ANCHOR_INDEX.json").exists())
            self.assertTrue((report_dir / "RECOMMENDATIONS.normalized.json").exists())
            self.assertTrue((report_dir / "RECOMMENDATIONS.storyboard.md").exists())
            self.assertTrue((report_dir / "ANCHOR_MATCH_REPORT.json").exists())
            self.assertEqual(len(warnings), 0)

    def test_parse_recommendations_base_prefers_authoritative_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-normalized-source-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "RECOMMENDATIONS.json").write_text(
                json.dumps([{"id": "1", "type": "bar_compare", "anchor": "旧标题"}], ensure_ascii=False),
                encoding="utf-8",
            )
            (report_dir / "RECOMMENDATIONS.normalized.json").write_text(
                json.dumps([{"id": "1", "type": "bar_compare", "anchor": "新标题"}], ensure_ascii=False),
                encoding="utf-8",
            )
            items = parse_recommendations_base(str(report_dir))
            self.assertEqual(items[0]["anchor"], "旧标题")

    def test_parse_recommendations_base_rejects_derived_only_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-derived-only-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "RECOMMENDATIONS.normalized.json").write_text(
                json.dumps([{"id": "1", "type": "bar_compare", "anchor": "派生标题"}], ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError) as ctx:
                parse_recommendations_base(str(report_dir))
            self.assertIn("派生产物", str(ctx.exception))

    def test_prepare_recommendations_rejects_markdown_only_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-md-only-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "RECOMMENDATIONS.md").write_text("## C1\nanchor: 标题\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                prepare_recommendations(report_dir)
            self.assertIn("不再支持 Markdown", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
