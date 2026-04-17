#!/usr/bin/env python3
"""
Build templates/static/base-styles.css from templates/static/css/*.css.

This keeps `base-styles.css` as a compatibility snapshot while split CSS files
are the source of truth.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    skill_dir = Path(__file__).resolve().parent.parent
    split_css_dir = skill_dir / "templates" / "static" / "css"
    target_css = skill_dir / "templates" / "static" / "base-styles.css"

    css_files = sorted(Path(p) for p in glob.glob(str(split_css_dir / "*.css")))
    if not css_files:
        raise SystemExit(f"[ERROR] 找不到分层 CSS 文件：{split_css_dir}")

    parts: list[str] = [
        "/*",
        " * Compatibility snapshot generated from templates/static/css/*.css",
        " * Source of truth: split CSS files in templates/static/css/",
        " */",
        "",
    ]
    for css_file in css_files:
        rel = css_file.relative_to(skill_dir)
        parts.append(f"/* >>> {rel} */")
        parts.append(read_text(css_file).rstrip())
        parts.append("")

    target_css.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    print(f"[DONE] 写入兼容样式快照：{target_css}")


if __name__ == "__main__":
    main()
