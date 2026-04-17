#!/usr/bin/env python3
"""
Export an assembled report HTML to PDF through a Chromium-family browser.

This keeps text and SVG charts in the browser print pipeline instead of turning
the whole page into JPEG screenshots.

Usage:
  python3 scripts/export_pdf.py <html_path> [pdf_path]
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from pathlib import Path


def candidate_browsers() -> list[str]:
    system = platform.system()
    names = [
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "msedge",
        "microsoft-edge",
    ]
    found = [path for name in names if (path := shutil.which(name))]

    if system == "Darwin":
        found.extend(
            [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            ]
        )
    elif system == "Windows":
        roots = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        suffixes = [
            r"Google\Chrome\Application\chrome.exe",
            r"Microsoft\Edge\Application\msedge.exe",
        ]
        for root in roots:
            if not root:
                continue
            for suffix in suffixes:
                found.append(os.path.join(root, suffix))

    return [path for path in found if path and os.path.exists(path)]


def export_pdf(html_path: Path, pdf_path: Path) -> None:
    browsers = candidate_browsers()
    if not browsers:
        raise SystemExit(
            "[ERROR] 未找到 Chrome/Chromium/Edge。请安装任一 Chromium 系浏览器后重试。"
        )

    html_uri = html_path.resolve().as_uri()
    html_uri = f"{html_uri}?{urlencode({'pdf': '1'})}"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="report-illustrator-chrome-") as tmpdir:
        browser = browsers[0]
        tmp_pdf_path = Path(tmpdir) / pdf_path.name
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-extensions",
            "--disable-sync",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=5000",
            "--no-pdf-header-footer",
            f"--user-data-dir={tmpdir}",
            f"--print-to-pdf={str(tmp_pdf_path.resolve())}",
            html_uri,
        ]

        returncode, stdout, stderr = run_browser_command(cmd, tmp_pdf_path)
        if returncode != 0:
            # Older Chromium builds use the old headless switch.
            cmd[1] = "--headless"
            returncode, stdout, stderr = run_browser_command(cmd, tmp_pdf_path)

        if returncode != 0:
            sys.stderr.write(stdout)
            sys.stderr.write(stderr)
            raise SystemExit(f"[ERROR] PDF 导出失败，浏览器退出码：{returncode}")

        if not tmp_pdf_path.exists() or tmp_pdf_path.stat().st_size == 0:
            raise SystemExit(f"[ERROR] PDF 未生成或为空：{tmp_pdf_path}")

        shutil.move(str(tmp_pdf_path), str(pdf_path))

    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise SystemExit(f"[ERROR] PDF 未生成或为空：{pdf_path}")

    print(f"[DONE] PDF 输出文件：{pdf_path}")


def run_browser_command(cmd: list[str], pdf_path: Path, timeout_seconds: int = 45) -> tuple[int, str, str]:
    process = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    started = time.monotonic()
    last_size = -1
    stable_since: float | None = None

    while True:
        returncode = process.poll()
        if returncode is not None:
            stdout, stderr = process.communicate()
            return returncode, stdout, stderr

        if pdf_path.exists():
            size = pdf_path.stat().st_size
            if size > 0 and size == last_size:
                if stable_since is None:
                    stable_since = time.monotonic()
                elif time.monotonic() - stable_since >= 2:
                    process.terminate()
                    try:
                        stdout, stderr = process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stdout, stderr = process.communicate()
                    return 0, stdout, stderr
            else:
                last_size = size
                stable_since = None

        if time.monotonic() - started > timeout_seconds:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                return 0, stdout, stderr
            return 124, stdout, stderr

        time.sleep(0.25)


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("用法：python3 scripts/export_pdf.py <html_path> [pdf_path]")
        raise SystemExit(1)

    html_path = Path(argv[1]).expanduser()
    if not html_path.exists():
        raise SystemExit(f"[ERROR] 找不到 HTML 文件：{html_path}")

    if len(argv) >= 3:
        pdf_path = Path(argv[2]).expanduser()
    else:
        pdf_path = html_path.with_suffix(".pdf")

    export_pdf(html_path, pdf_path)


if __name__ == "__main__":
    main(sys.argv)
