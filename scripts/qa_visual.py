#!/usr/bin/env python3
"""
Light visual regression QA for the first page of HTML vs exported PDF.

Usage:
  python3 scripts/qa_visual.py <html_path> <pdf_path> [qa_json_path]
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from export_pdf import LocalHttpServer, build_served_url, candidate_browsers


WARNING_RMSE = 0.22
ERROR_RMSE = 0.28


def build_visual_qa_html(source_html: str) -> str:
    inject = """
<style id="ri-visual-qa-hide">
  #pdf-export-btn { display: none !important; }
</style>
<script id="ri-visual-qa-script">
window.addEventListener('load', function () {
  document.documentElement.classList.add('pdf-export-mode');
  window.dispatchEvent(new Event('beforeprint'));
});
</script>
""".strip()
    if 'id="ri-visual-qa-script"' in source_html:
        return source_html
    if "</head>" in source_html:
        return source_html.replace("</head>", inject + "\n</head>", 1)
    return inject + "\n" + source_html


def parse_compare_metric(output: str) -> float | None:
    match = re.search(r"\((0?\.\d+|1(?:\.0+)?)\)", output or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def classify_rmse(rmse: float | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if rmse is None:
        warnings.append("无法解析视觉回归 RMSE 指标")
        return errors, warnings
    if rmse > ERROR_RMSE:
        errors.append(f"HTML/PDF 首页面视觉差异过大：RMSE={rmse:.3f} > {ERROR_RMSE:.2f}")
    elif rmse > WARNING_RMSE:
        warnings.append(f"HTML/PDF 首页面视觉差异偏高：RMSE={rmse:.3f} > {WARNING_RMSE:.2f}")
    return errors, warnings


def run_command(cmd: list[str], *, timeout_seconds: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)


def image_size(path: Path) -> tuple[int, int]:
    proc = run_command(["magick", "identify", "-format", "%w %h", str(path)])
    if proc.returncode != 0:
        raise SystemExit(f"[ERROR] 无法读取图片尺寸：{path}\n{proc.stderr.strip()}")
    try:
        width_str, height_str = proc.stdout.strip().split()
        return int(width_str), int(height_str)
    except Exception as exc:
        raise SystemExit(f"[ERROR] 图片尺寸输出异常：{path} -> {proc.stdout!r}") from exc


def render_pdf_first_page(pdf_path: Path, output_path: Path) -> tuple[bool, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if platform.system() == "Darwin" and shutil.which("qlmanage"):
        cmd = ["qlmanage", "-t", "-s", "1200", "-o", str(output_path.parent), str(pdf_path)]
        proc = run_command(cmd, timeout_seconds=45)
        rendered = output_path.parent / f"{pdf_path.name}.png"
        if proc.returncode == 0 and rendered.exists():
            if rendered.resolve() != output_path.resolve():
                shutil.move(str(rendered), str(output_path))
            return True, "qlmanage"
        stderr = (proc.stdout + "\n" + proc.stderr).strip()
        raise SystemExit(f"[ERROR] qlmanage 渲染 PDF 首页面失败：{stderr}")

    if shutil.which("magick") and shutil.which("gs"):
        proc = run_command(
            [
                "magick",
                "-density",
                "144",
                f"{pdf_path}[0]",
                "-alpha",
                "off",
                "-colorspace",
                "sRGB",
                str(output_path),
            ],
            timeout_seconds=45,
        )
        if proc.returncode == 0 and output_path.exists():
            return True, "magick+gs"
        stderr = (proc.stdout + "\n" + proc.stderr).strip()
        raise SystemExit(f"[ERROR] ImageMagick 渲染 PDF 首页面失败：{stderr}")

    return False, "unsupported"


def capture_html_first_page(html_path: Path, output_path: Path, *, width: int, height: int) -> None:
    browsers = candidate_browsers()
    if not browsers:
        raise SystemExit("[ERROR] 未找到 Chrome/Chromium/Edge，无法执行视觉 QA")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    browser = browsers[0]
    with tempfile.TemporaryDirectory(prefix="ri-visual-qa-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        temp_html = tmpdir_path / html_path.name
        temp_html.write_text(build_visual_qa_html(html_path.read_text(encoding="utf-8", errors="ignore")), encoding="utf-8")
        with LocalHttpServer(tmpdir_path) as server:
            url = f"{server.base_url}/{build_served_url(temp_html, tmpdir_path)}"
            cmd = [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=6500",
                f"--window-size={width},{height}",
                f"--screenshot={str(output_path)}",
                url,
            ]
            proc = run_command(cmd, timeout_seconds=30)
            if proc.returncode != 0:
                cmd[1] = "--headless"
                proc = run_command(cmd, timeout_seconds=30)
            if proc.returncode != 0 or not output_path.exists():
                stderr = (proc.stdout + "\n" + proc.stderr).strip()
                raise SystemExit(f"[ERROR] 截取 HTML 首页面失败：{stderr}")


def resize_image_to(path: Path, *, width: int, height: int, output_path: Path) -> Path:
    if image_size(path) == (width, height):
        if path.resolve() != output_path.resolve():
            shutil.copyfile(path, output_path)
        return output_path
    proc = run_command(
        ["magick", str(path), "-resize", f"{width}x{height}!", str(output_path)],
        timeout_seconds=30,
    )
    if proc.returncode != 0 or not output_path.exists():
        stderr = (proc.stdout + "\n" + proc.stderr).strip()
        raise SystemExit(f"[ERROR] 调整视觉 QA 图片尺寸失败：{stderr}")
    return output_path


def compare_images(html_image: Path, pdf_image: Path) -> float | None:
    proc = run_command(
        ["magick", "compare", "-metric", "RMSE", str(html_image), str(pdf_image), "null:"],
        timeout_seconds=30,
    )
    output = (proc.stderr or "") + "\n" + (proc.stdout or "")
    if proc.returncode not in {0, 1}:
        raise SystemExit(f"[ERROR] 视觉回归 compare 失败：{output.strip()}")
    return parse_compare_metric(output)


def evaluate_visual_regression(html_path: Path, pdf_path: Path) -> dict[str, Any]:
    artifacts_dir = html_path.parent / "visual-qa"
    html_image = artifacts_dir / "html-first-page.png"
    html_image_normalized = artifacts_dir / "html-first-page.normalized.png"
    pdf_image = artifacts_dir / "pdf-first-page.png"

    errors: list[str] = []
    warnings: list[str] = []
    skipped = False

    rendered, pdf_renderer = render_pdf_first_page(pdf_path, pdf_image)
    if not rendered:
        skipped = True
        warnings.append("当前环境缺少可用的 PDF 首页面渲染器，已跳过视觉回归 QA")
        return {
            "schema": "report-illustrator-visual-qa:v1",
            "htmlPath": str(html_path),
            "pdfPath": str(pdf_path),
            "pass": None,
            "skipped": True,
            "renderer": {"pdf": pdf_renderer, "html": ""},
            "artifacts": {},
            "metrics": {},
            "errors": [],
            "warnings": warnings,
        }

    width, height = image_size(pdf_image)
    capture_html_first_page(html_path, html_image, width=width, height=height)
    resize_image_to(html_image, width=width, height=height, output_path=html_image_normalized)
    rmse = compare_images(html_image_normalized, pdf_image)
    cmp_errors, cmp_warnings = classify_rmse(rmse)
    errors.extend(cmp_errors)
    warnings.extend(cmp_warnings)

    return {
        "schema": "report-illustrator-visual-qa:v1",
        "htmlPath": str(html_path),
        "pdfPath": str(pdf_path),
        "pass": not errors,
        "skipped": skipped,
        "renderer": {"pdf": pdf_renderer, "html": "chromium-screenshot"},
        "artifacts": {
            "htmlFirstPage": str(html_image),
            "htmlFirstPageNormalized": str(html_image_normalized),
            "pdfFirstPage": str(pdf_image),
        },
        "metrics": {
            "rmse": rmse,
            "warningThreshold": WARNING_RMSE,
            "errorThreshold": ERROR_RMSE,
            "width": width,
            "height": height,
        },
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Light visual regression QA for md2report")
    parser.add_argument("html_path", help="Illustrated HTML path")
    parser.add_argument("pdf_path", help="Exported PDF path")
    parser.add_argument("qa_json_path", nargs="?", help="Optional QA JSON output path")
    args = parser.parse_args(argv[1:])

    html_path = Path(args.html_path).expanduser().resolve()
    pdf_path = Path(args.pdf_path).expanduser().resolve()
    if not html_path.exists():
        print(f"[ERROR] 找不到 HTML 文件：{html_path}")
        return 1
    if not pdf_path.exists():
        print(f"[ERROR] 找不到 PDF 文件：{pdf_path}")
        return 1

    payload = evaluate_visual_regression(html_path, pdf_path)
    qa_json_path = Path(args.qa_json_path).expanduser().resolve() if args.qa_json_path else html_path.parent / "VISUAL_QA.json"
    qa_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[VISUAL_QA] html={html_path}")
    print(f"[VISUAL_QA] pdf={pdf_path}")
    print(f"[VISUAL_QA] output={qa_json_path}")
    if payload.get("skipped"):
        for item in payload.get("warnings", []):
            print(f"[WARN] {item}")
        print("[PASS] 视觉 QA 已跳过")
        return 0

    rmse = payload.get("metrics", {}).get("rmse")
    if rmse is not None:
        print(f"[VISUAL_QA] first_page_rmse={rmse:.3f}")
    for item in payload.get("warnings", []):
        print(f"[WARN] {item}")
    for item in payload.get("errors", []):
        print(f"[ERROR] {item}")
    if payload.get("errors"):
        print("[FAIL] 视觉 QA 未通过")
        return 1
    print("[PASS] 视觉 QA 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
