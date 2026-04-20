#!/usr/bin/env python3
"""
Export an assembled report HTML to PDF through a Chromium-family browser.

This keeps text and SVG charts in the browser print pipeline instead of turning
the whole page into JPEG screenshots.

Usage:
  python3 scripts/export_pdf.py <html_path> [pdf_path]
"""

from __future__ import annotations

import json
import os
import platform
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import threading
from functools import partial
from pathlib import Path
from urllib.parse import quote, urlencode

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


META_PATTERN = re.compile(
    r'<meta\s+name=["\']([^"\']+)["\']\s+content=["\']([^"\']*)["\']',
    flags=re.IGNORECASE,
)


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


def candidate_playwright_cli() -> list[str]:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    candidates = [
        codex_home / "skills" / "playwright" / "scripts" / "playwright_cli.sh",
        Path.home() / ".codex" / "skills" / "playwright" / "scripts" / "playwright_cli.sh",
    ]
    found: list[str] = []
    for path in candidates:
        if path.exists():
            found.append(str(path))
    return found


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return


class LocalHttpServer:
    def __init__(self, root: Path):
        self.root = root
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> "LocalHttpServer":
        handler = partial(QuietHandler, directory=str(self.root))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2)

    @property
    def base_url(self) -> str:
        if not self.httpd:
            raise RuntimeError("server not started")
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"


def build_served_url(html_path: Path, root: Path) -> str:
    relative = html_path.resolve().relative_to(root.resolve())
    route = posixpath.join(*(quote(part) for part in relative.parts))
    return f"{route}?{urlencode({'pdf': '1'})}"


def extract_report_meta(html_path: Path) -> dict[str, str]:
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    return {name.strip().lower(): value.strip() for name, value in META_PATTERN.findall(text)}


def detect_page_count(pdf_path: Path) -> int | None:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return None
    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return None
    try:
        return len(reader.pages)
    except Exception:
        return None


def write_export_diagnostics(html_path: Path, pdf_path: Path, export_mode: str, backend: str) -> None:
    meta = extract_report_meta(html_path)
    payload = {
        "schema": "report-illustrator-export-diagnostics:v1",
        "export_mode": export_mode,
        "backend": backend,
        "html_path": str(html_path.resolve()),
        "pdf_path": str(pdf_path.resolve()),
        "pdf_size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "page_count": detect_page_count(pdf_path),
        "report_color_scheme": meta.get("report-color-scheme", ""),
        "report_color_scheme_resolved": meta.get("report-color-scheme-resolved", ""),
        "recommendations_source": meta.get("report-recommendations-source", ""),
    }
    diagnostics_path = html_path.parent / "EXPORT_DIAGNOSTICS.json"
    diagnostics_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[DONE] 导出诊断：{diagnostics_path}")


def run_playwright_command(pwcli: str, args: list[str], workdir: Path, timeout_seconds: int = 60) -> subprocess.CompletedProcess[str]:
    cmd = [pwcli] + args
    proc = subprocess.run(
        cmd,
        cwd=str(workdir),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"playwright-cli failed: {' '.join(args)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def export_pdf_via_playwright(html_path: Path, pdf_path: Path) -> bool:
    pwclis = candidate_playwright_cli()
    if not pwclis or not shutil.which("npx"):
        return False

    pwcli = pwclis[0]
    session = f"md2report-{int(time.time() * 1000)}"
    with tempfile.TemporaryDirectory(prefix="report-illustrator-pw-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        tmp_pdf_path = tmpdir_path / pdf_path.name
        page_root = html_path.resolve().parent
        wait_for_stable_layout = """
async () => {
  const blockSelector = '.visual-row, .visual-block:not(.visual-block-nested), h2, h3, table, blockquote, p, ul, ol';
  const ready = () => document.documentElement.classList.contains('charts-ready');
  const snapshot = () => Array.from(document.querySelectorAll(blockSelector)).map((el) => {
    const rect = el.getBoundingClientRect();
    return `${Math.round(rect.top)}:${Math.round(rect.height)}`;
  }).join('|');

  const deadline = Date.now() + 12000;
  while (!ready() && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  let last = snapshot();
  let stableCount = 0;
  while (Date.now() < deadline) {
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    await new Promise((resolve) => setTimeout(resolve, 180));
    const current = snapshot();
    if (current === last) {
      stableCount += 1;
      if (stableCount >= 4) break;
    } else {
      stableCount = 0;
      last = current;
    }
  }

  window.dispatchEvent(new Event('beforeprint'));
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await new Promise((resolve) => setTimeout(resolve, 500));
  return {
    ready: ready(),
    bodyClass: document.body.className,
    htmlClass: document.documentElement.className,
    blocks: document.querySelectorAll('.visual-row, .visual-block:not(.visual-block-nested)').length
  };
}
        """.strip()

        try:
            with LocalHttpServer(page_root) as server:
                url = f"{server.base_url}/{build_served_url(html_path, page_root)}"
                run_playwright_command(pwcli, [f"-s={session}", "open", url], tmpdir_path, timeout_seconds=90)
                run_playwright_command(pwcli, [f"-s={session}", "resize", "1440", "1200"], tmpdir_path)
                run_playwright_command(pwcli, [f"-s={session}", "eval", wait_for_stable_layout], tmpdir_path, timeout_seconds=90)
                run_playwright_command(
                    pwcli,
                    [f"-s={session}", "pdf", "--filename", str(tmp_pdf_path)],
                    tmpdir_path,
                    timeout_seconds=90,
                )
        except Exception:
            try:
                run_playwright_command(pwcli, [f"-s={session}", "close"], tmpdir_path)
            except Exception:
                pass
            return False
        finally:
            try:
                run_playwright_command(pwcli, [f"-s={session}", "close"], tmpdir_path)
            except Exception:
                pass

        if not tmp_pdf_path.exists() or tmp_pdf_path.stat().st_size == 0:
            return False

        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_pdf_path), str(pdf_path))
        return True


def export_pdf(html_path: Path, pdf_path: Path) -> None:
    if export_pdf_via_playwright(html_path, pdf_path):
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            raise SystemExit(f"[ERROR] PDF 未生成或为空：{pdf_path}")
        write_export_diagnostics(html_path, pdf_path, "playwright", "playwright-cli")
        print(f"[DONE] PDF 输出文件：{pdf_path}")
        return

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

    write_export_diagnostics(html_path, pdf_path, "chromium-print", browser)
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
