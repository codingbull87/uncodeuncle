import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from insertion_planner import plan_insertions


def strip_tags_local(value: str) -> str:
    import re

    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(value.split())


class InsertionPlannerTests(unittest.TestCase):
    def test_plan_insertions_supports_h5_anchor_matching(self) -> None:
        html = "<h5>深层标题</h5><p>正文</p>"
        fragments = {"C7": "<svg></svg>"}
        recommendations = [
            {
                "id": "7",
                "anchor": "深层标题",
                "position": "after_heading",
            }
        ]

        insertions, results = plan_insertions(
            html,
            fragments,
            recommendations,
            normalize_chart_id=lambda raw: "C7" if str(raw).strip() in {"7", "C7"} else str(raw).strip(),
            normalize_anchor=lambda value: str(value or "").strip(),
            parse_occurrence=lambda value: int(value) if value else 1,
            has_renderable_fragment=lambda fragment: bool(fragment),
            get_cover_span=lambda content: None,
            strip_tags=strip_tags_local,
            planned_insertion_factory=lambda pos, rec, fragment, anchor, match_count: {
                "pos": pos,
                "rec": rec,
                "fragment": fragment,
                "anchor": anchor,
                "match_count": match_count,
            },
            injection_result_factory=lambda chart_id, anchor, status, message: {
                "chart_id": chart_id,
                "anchor": anchor,
                "status": status,
                "message": message,
            },
        )

        self.assertEqual(len(insertions), 1)
        self.assertEqual(insertions[0]["pos"], html.index("</h5>") + len("</h5>"))
        self.assertEqual(insertions[0]["anchor"], "深层标题")
        self.assertEqual(results[0]["status"], "OK")

    def test_plan_insertions_uses_anchor_full_fallback(self) -> None:
        html = "<h2>PS6“窗口”判断</h2><p>正文</p>"
        fragments = {"C2": "<svg></svg>"}
        recommendations = [
            {
                "id": "2",
                "anchor": "不存在的短锚点",
                "anchor_full": "PS6“窗口”判断",
                "position": "after_heading",
            }
        ]

        insertions, results = plan_insertions(
            html,
            fragments,
            recommendations,
            normalize_chart_id=lambda raw: "C2" if str(raw).strip() in {"2", "C2"} else str(raw).strip(),
            normalize_anchor=lambda value: str(value or "").strip().replace("\u201d", '"').replace("\u201c", '"'),
            parse_occurrence=lambda value: int(value) if value else 1,
            has_renderable_fragment=lambda fragment: bool(fragment),
            get_cover_span=lambda content: None,
            strip_tags=strip_tags_local,
            planned_insertion_factory=lambda pos, rec, fragment, anchor, match_count: {
                "pos": pos,
                "rec": rec,
                "fragment": fragment,
                "anchor": anchor,
                "match_count": match_count,
            },
            injection_result_factory=lambda chart_id, anchor, status, message: {
                "chart_id": chart_id,
                "anchor": anchor,
                "status": status,
                "message": message,
            },
        )

        self.assertEqual(len(insertions), 1)
        self.assertEqual(insertions[0]["anchor"], 'PS6"窗口"判断')
        self.assertEqual(results[0]["status"], "OK")


if __name__ == "__main__":
    unittest.main()
