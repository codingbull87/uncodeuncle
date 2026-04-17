import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPT_DIR))

from assemble_engine import parse_recommendations, parse_recommendations_base
from repair_layout import apply_suggestions, build_payload


class LayoutStateTests(unittest.TestCase):
    def make_report_dir(self) -> Path:
        tempdir = tempfile.TemporaryDirectory(prefix='ri-layout-state-')
        self.addCleanup(tempdir.cleanup)
        report_dir = Path(tempdir.name)
        recommendations = [
            {
                'id': '1',
                'enabled': True,
                'type': 'kpi_strip',
                'anchor': 'A',
                'position': 'after_heading',
                'layout': 'full',
                'size': 'medium',
            }
        ]
        (report_dir / 'RECOMMENDATIONS.json').write_text(json.dumps(recommendations, ensure_ascii=False), encoding='utf-8')
        (report_dir / 'LAYOUT_OVERRIDES.json').write_text(
            json.dumps({'by_chart_id': {'C1': {'size': 'small', 'print_compact': True}}}, ensure_ascii=False),
            encoding='utf-8',
        )
        return report_dir

    def test_raw_recommendations_ignore_generated_overrides(self) -> None:
        report_dir = self.make_report_dir()
        raw = parse_recommendations_base(str(report_dir))
        effective = parse_recommendations(str(report_dir))
        self.assertEqual(raw[0]['size'], 'medium')
        self.assertEqual(effective[0]['size'], 'small')
        self.assertTrue(effective[0]['print_compact'])

    def test_build_payload_is_stateless_against_raw_baseline(self) -> None:
        raw_items = [
            {'id': '1', 'type': 'kpi_strip', 'layout': 'full', 'size': 'medium', 'position': 'after_heading'},
            {'id': '2', 'type': 'heatmap', 'layout': 'full', 'size': 'medium', 'position': 'after_heading'},
        ]
        effective_items = [dict(item) for item in raw_items]
        diagnosis = {
            'sparsePages': [
                {
                    'suggestions': [
                        {'action': 'compact_trailing_visual', 'target_chart_id': 'C1'},
                        {'action': 'move_trailing_visual_to_section_end', 'target_chart_id': 'C2'},
                    ]
                }
            ]
        }
        mutated = apply_suggestions(effective_items, diagnosis)
        payload, changed = build_payload(raw_items, mutated, diagnosis)
        self.assertGreater(changed, 0)
        self.assertEqual(set(payload['by_chart_id'].keys()), {'C1', 'C2'})
        self.assertEqual(payload['by_chart_id']['C2']['position'], 'section_end')
        self.assertNotIn('C99', payload['by_chart_id'])


if __name__ == '__main__':
    unittest.main()
