#!/usr/bin/env python3
"""
Report Illustrator - Phase 3 assembler CLI entrypoint.

Usage:
  python3 scripts/assemble.py <report_dir> <output_name>
"""

from __future__ import annotations

import sys

from assemble_engine import build_html


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        print("用法：python3 scripts/assemble.py <report_dir> <output_name>")
        raise SystemExit(1)
    build_html(argv[1], argv[2])


if __name__ == "__main__":
    main(sys.argv)
