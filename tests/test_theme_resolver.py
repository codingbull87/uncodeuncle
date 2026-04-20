import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from theme_resolver import anchor_index_summary, recommendation_source_info, resolve_color_scheme_info


class ThemeResolverTests(unittest.TestCase):
    def test_resolve_color_scheme_info_uses_aliases_and_brief(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-theme-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "DESIGN_BRIEF.json").write_text(
                json.dumps(
                    {
                        "color_scheme": "institutional-carbon",
                        "color_confirmed": True,
                        "color_selected_by": "user",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = resolve_color_scheme_info(str(report_dir))

            self.assertEqual(payload["requested_color_scheme"], "institutional-carbon")
            self.assertEqual(payload["resolved_color_scheme"], "blue")
            self.assertTrue(payload["color_confirmed"])
            self.assertEqual(payload["color_selected_by"], "user")

    def test_recommendation_source_and_anchor_summary_reflect_workspace_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-theme-diag-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "RECOMMENDATIONS.json").write_text("[]", encoding="utf-8")
            (report_dir / "RECOMMENDATIONS.normalized.json").write_text("[{}]", encoding="utf-8")
            (report_dir / "ANCHOR_INDEX.json").write_text(
                json.dumps({"schema": "anchors:v1", "items": [{"id": "h2_1"}, {"id": "h3_2"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            source_info = recommendation_source_info(str(report_dir))
            anchor_info = anchor_index_summary(str(report_dir))

            self.assertEqual(source_info["source"], "RECOMMENDATIONS.json")
            self.assertTrue(source_info["authoritative"])
            self.assertTrue(source_info["supported"])
            self.assertTrue(anchor_info["present"])
            self.assertEqual(anchor_info["count"], 2)
            self.assertEqual(anchor_info["schema"], "anchors:v1")


if __name__ == "__main__":
    unittest.main()
