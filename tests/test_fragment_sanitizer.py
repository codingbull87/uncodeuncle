import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from fragment_sanitizer import clean_fragment


class FragmentSanitizerTests(unittest.TestCase):
    def test_clean_fragment_removes_download_artifacts_and_internal_sources(self) -> None:
        fragment = """
<p><div class="chart-wrap"><div class="chart-src">数据来源：报告正文整理 | Sony FY2024</div></div></p>
<button class="chart-download">download</button>
<script>
const option = {"tooltip": {"formatter": "function (p) {\\nreturn p.name;\\n}"}};
</script>
""".strip()

        cleaned = clean_fragment(fragment)

        self.assertNotIn("chart-download", cleaned)
        self.assertNotIn("报告正文整理", cleaned)
        self.assertIn("Sony FY2024", cleaned)
        self.assertIn('formatter": function (p)', cleaned)
        self.assertTrue(cleaned.startswith('<div class="chart-wrap">'))


if __name__ == "__main__":
    unittest.main()
