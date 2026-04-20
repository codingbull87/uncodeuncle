import json
import sys
import tempfile
import time
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from check_phase_contract import check_before_fragments, validate_recommendation_contracts
from lint_fragments import lint_fragment, load_contracts


class ContractPrecisionTests(unittest.TestCase):
    def test_lint_rejects_host_scoped_echarts_palette(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-host-scope-") as temp_dir:
            path = Path(temp_dir) / "C1.html"
            path.write_text(
                """<style>:host { --color-primary: #c96442; --color-secondary: #5e5d59; --color-positive: #3f6d4e; --color-negative: #b53333; --color-accent: #9c6f2f; --color-border: #e6e1d7; --color-text: #2f2d2a; }</style>
<div class="chart-container"><div class="chart-header"><div class="chart-title">足够长的测试标题</div></div><div id="chart-C1" style="height:240px;"></div></div>
<script>var chart = echarts.init(document.getElementById('chart-C1'), null, { renderer: 'svg' });</script>""",
                encoding="utf-8",
            )
            errors, _warnings = lint_fragment(path, "bar_compare", load_contracts())
            self.assertTrue(any(":host" in item for item in errors))
            self.assertTrue(any(":root" in item for item in errors))

    def test_group_contract_requires_same_anchor_position_and_occurrence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-group-contract-") as temp_dir:
            report_dir = Path(temp_dir)
            payload = [
                {
                    "id": "3",
                    "type": "bar_compare",
                    "group": "hardware",
                    "layout": "half",
                    "anchor": "Q2：硬件规格与定价策略",
                    "position": "after_heading",
                    "anchor_occurrence": 1,
                },
                {
                    "id": "4",
                    "type": "insight_cards",
                    "group": "hardware",
                    "layout": "half",
                    "anchor": "Q2：硬件规格与定价策略",
                    "position": "after_first_paragraph",
                    "anchor_occurrence": 1,
                },
            ]
            (report_dir / "RECOMMENDATIONS.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            errors, _warnings = validate_recommendation_contracts(report_dir)
            self.assertTrue(any("并排合同不一致" in item for item in errors))

    def test_scorecard_requires_traceable_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-scorecard-evidence-") as temp_dir:
            report_dir = Path(temp_dir)
            payload = [
                {
                    "id": "11",
                    "type": "scorecard",
                    "layout": "full",
                    "anchor": "投资结论与风险",
                    "position": "section_end",
                    "data": {
                        "items": [
                            {"title": "PS6发布催化", "score": "5/5"},
                            {"title": "订阅业务增长", "score": "4/5"},
                        ]
                    },
                }
            ]
            (report_dir / "RECOMMENDATIONS.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            errors, _warnings = validate_recommendation_contracts(report_dir)
            self.assertTrue(any("scorecard 缺少可追溯证据" in item for item in errors))

    def test_before_fragments_validates_current_authoritative_json_not_stale_snapshots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-current-json-gate-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "content.html").write_text("<h2>存在标题</h2><p>正文</p>", encoding="utf-8")
            (report_dir / "DESIGN_BRIEF.md").write_text("# brief\n", encoding="utf-8")
            (report_dir / "DESIGN_BRIEF.json").write_text(
                json.dumps(
                    {
                        "color_scheme": "green",
                        "color_confirmed": True,
                        "color_selected_by": "user",
                        "color_candidates": ["green", "blue", "black"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (report_dir / "VALIDATION.md").write_text("判定: PROCEED\n", encoding="utf-8")
            clean_payload = [
                {
                    "id": "C1",
                    "type": "bar_compare",
                    "anchor_id": "h2_1",
                    "anchor": "存在标题",
                    "position": "after_heading",
                    "anchor_occurrence": 1,
                }
            ]
            (report_dir / "RECOMMENDATIONS.json").write_text(
                json.dumps(clean_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (report_dir / "RECOMMENDATIONS.normalized.json").write_text(
                json.dumps(clean_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (report_dir / "ANCHOR_INDEX.json").write_text(
                json.dumps(
                    {
                        "schema": "report-illustrator-anchor-index:v1",
                        "count": 1,
                        "items": [{"anchor_id": "h2_1", "text": "存在标题", "occurrence": 1, "level": 2}],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (report_dir / "ANCHOR_MATCH_REPORT.json").write_text(
                json.dumps(
                    {
                        "schema": "report-illustrator-anchor-match-report:v1",
                        "items": [{"id": "C1", "status": "resolved", "anchor_id": "h2_1", "anchor": "存在标题"}],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (report_dir / "RECOMMENDATION_PREP.json").write_text(
                json.dumps(
                    {
                        "schema": "report-illustrator-recommendation-prep:v1",
                        "source": "RECOMMENDATIONS.json",
                        "authoritative_source": "RECOMMENDATIONS.json",
                        "count": 1,
                        "warnings": [],
                        "errors": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            time.sleep(0.01)
            dirty_payload = [
                {
                    "id": "C1",
                    "type": "bar_compare",
                    "anchor_id": "h2_1",
                    "anchor": "不存在的标题",
                    "position": "after_heading",
                    "anchor_occurrence": 1,
                }
            ]
            (report_dir / "RECOMMENDATIONS.json").write_text(
                json.dumps(dirty_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            errors, _warnings = check_before_fragments(report_dir)

            self.assertTrue(any("当前 RECOMMENDATIONS.json anchor 未命中正文 heading" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
