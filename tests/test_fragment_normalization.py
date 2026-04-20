import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from normalize_fragments import normalize_fragments


class FragmentNormalizationTests(unittest.TestCase):
    def test_normalize_fragments_wraps_headers_and_injects_palette(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-normalize-fragments-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "chart-fragments").mkdir()
            (report_dir / "DESIGN_BRIEF.json").write_text(
                json.dumps({"color_scheme": "black", "color_confirmed": True}, ensure_ascii=False),
                encoding="utf-8",
            )
            fragment_path = report_dir / "chart-fragments" / "C1.html"
            fragment_path.write_text(
                """
<div class="chart-container">
  <div class="chart-title">结论标题足够长以触发规范化</div>
  <div id="chart-C1" style="width:100%;height:240px;"></div>
</div>
<script>
var chart = echarts.init(document.getElementById('chart-C1'), null, { renderer: 'svg' });
</script>
<div class="kpi-strip"><div class="kpi-card"><div class="kpi-label">A</div><div class="kpi-val">1</div></div></div>
""".strip(),
                encoding="utf-8",
            )

            payload = normalize_fragments(report_dir)

            self.assertEqual(payload["changed"], 1)
            updated = fragment_path.read_text(encoding="utf-8")
            self.assertIn('class="chart-header"', updated)
            self.assertIn(":root", updated)
            self.assertIn("--color-primary", updated)
            self.assertIn("kpi-block", updated)
            self.assertNotIn("kpi-strip", updated)


if __name__ == "__main__":
    unittest.main()
