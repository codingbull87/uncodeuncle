import sys
import tempfile
import unittest
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from assembly_service import build_html


class SelfContainedOutputTests(unittest.TestCase):
    def test_build_html_inlines_echarts_runtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ri-self-contained-") as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "content.html").write_text(
                "<h1>测试报告</h1><p>正文内容。</p>",
                encoding="utf-8",
            )
            (report_dir / "RECOMMENDATIONS.json").write_text(
                json.dumps([], ensure_ascii=False),
                encoding="utf-8",
            )

            build_html(str(report_dir), "sample_report")
            html = (report_dir / "sample_report.html").read_text(encoding="utf-8")

            self.assertNotIn('src="libs/echarts.min.js"', html)
            self.assertIn("Apache License", html)
            self.assertIn("打印 / 导出 PDF", html)


if __name__ == "__main__":
    unittest.main()
