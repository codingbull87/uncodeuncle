import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPT_DIR))

from layout_probe import BLOCK_SELECTOR, merge_registry_with_markers


class LayoutProbeTests(unittest.TestCase):
    def test_probe_tracks_h4_to_h6_headings(self) -> None:
        self.assertIn('h4', BLOCK_SELECTOR)
        self.assertIn('h5', BLOCK_SELECTOR)
        self.assertIn('h6', BLOCK_SELECTOR)

    def test_merge_registry_tracks_cross_page_usage(self) -> None:
        registry = {
            'pageHeightPx': 100,
            'blocks': [
                {'blockId': 'B001', 'domIndex': 0, 'kind': 'text', 'tag': 'p', 'text': 'intro'},
                {'blockId': 'B002', 'domIndex': 1, 'kind': 'visual-block', 'tag': 'div', 'chartId': 'C1', 'memberChartIds': []},
            ],
        }
        markers = [
            {'blockId': 'B001', 'kind': 'start', 'page': 1, 'localY': 10},
            {'blockId': 'B001', 'kind': 'end', 'page': 1, 'localY': 40},
            {'blockId': 'B002', 'kind': 'start', 'page': 1, 'localY': 80},
            {'blockId': 'B002', 'kind': 'end', 'page': 2, 'localY': 35},
        ]
        payload = merge_registry_with_markers(registry, markers, total_pages=2)
        self.assertEqual(payload['pages'][0]['usedPx'], 100)
        self.assertEqual(payload['pages'][0]['blankPx'], 0)
        self.assertEqual(payload['pages'][1]['usedPx'], 35)
        self.assertEqual(payload['pages'][1]['blankPx'], 65)
        self.assertEqual(payload['pages'][0]['lastVisualBlockId'], 'B002')


if __name__ == '__main__':
    unittest.main()
