import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from insertion_planner import find_insert_position, iter_heading_matches
from report_contract import strip_tags


class AssemblePositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (
            "<h2>Q5：财务影响评估</h2>"
            "<blockquote><p>提示信息。</p></blockquote>"
            "<h3>PS6营收三阶段模型</h3>"
            "<p><strong>阶段1：</strong>发布前过渡期。</p>"
            "<table><tr><td>阶段2数据</td></tr></table>"
            "<p><strong>阶段3：</strong>中后期稳定。</p>"
            "<h2>投资结论与风险</h2>"
        )
        self.heading = iter_heading_matches(self.html, "Q5：财务影响评估", strip_tags=strip_tags)[0]

    def test_after_first_paragraph_skips_blockquote_paragraph(self) -> None:
        insert_pos = find_insert_position(self.html, self.heading, "after_first_paragraph", None)
        expected = self.html.index("</p>", self.html.index("<h3>")) + 4
        self.assertEqual(insert_pos, expected)

    def test_section_end_stops_at_next_same_level_heading(self) -> None:
        insert_pos = find_insert_position(self.html, self.heading, "section_end", None)
        expected = self.html.index("<h2>投资结论与风险</h2>")
        self.assertEqual(insert_pos, expected)


if __name__ == "__main__":
    unittest.main()
