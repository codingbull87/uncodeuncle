import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import assemble_engine
import assembly_service


class AssembleEngineCompatTests(unittest.TestCase):
    def test_build_html_aliases_supported_service(self) -> None:
        self.assertIs(assemble_engine.build_html, assembly_service.build_html)

    def test_main_delegates_to_build_html(self) -> None:
        with patch("assemble_engine.build_html") as mock_build_html:
            assemble_engine.main(["assemble_engine.py", "/tmp/report", "demo"])
        mock_build_html.assert_called_once_with("/tmp/report", "demo")


if __name__ == "__main__":
    unittest.main()
