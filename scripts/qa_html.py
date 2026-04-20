#!/usr/bin/env python3
"""
QA assembled report HTML for structural layout regressions.

Usage:
  python3 scripts/qa_html.py <report_dir> [html_path]
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from export_pdf import candidate_browsers
from lint_fragments import ECHARTS_CSS_VAR_STRING, classes_in
from report_contract import normalize_chart_id, normalize_layout
from recommendation_state import parse_recommendations


DOC_ALLOWED_CLASSES = {
    "page",
    "report-cover",
    "report-meta",
    "report-meta-freeform",
    "report-meta-key",
    "report-meta-value",
    "visual-block",
    "visual-full",
    "visual-half",
    "visual-third",
    "visual-quarter",
    "visual-compact",
    "visual-size-small",
    "visual-size-medium",
    "visual-size-large",
    "visual-size-compact",
    "visual-block-nested",
    "visual-row",
    "visual-row-half",
    "visual-row-third",
    "visual-row-quarter",
    "visual-row-equal",
    "visual-row-title",
    "chapter-page-break",
    "compact-print",
    "page-fit-compact",
    "pdf-export-mode",
    "charts-ready",
}

RENDER_QA_SCHEMA = "report-illustrator-render-qa:v1"


RENDER_QA_SCRIPT = r"""
<script id="ri-render-qa-script">
(function () {
  function colCount(el) {
    var tpl = window.getComputedStyle(el).gridTemplateColumns || '';
    if (!tpl || tpl === 'none') return 0;
    return tpl.split(/\s+/).filter(function (token) {
      return token && token !== '/';
    }).length;
  }

  function localTop(target, base) {
    var top = 0;
    var node = target;
    while (node && node !== base) {
      top += node.offsetTop || 0;
      node = node.offsetParent;
    }
    return top;
  }

  function firstBodyNode(container) {
    var selectors = [
      '[id^="chart-C"]',
      '.kpi-block,.kpi-strip,.insight-grid,.framework-grid,.scorecard-grid',
      '.matrix-2x2,.risk-matrix,.heatmap-grid,.timeline,.value-chain,.process-chain',
      '.swimlane-roadmap,.driver-tree,.decision-tree,.range-band,.football-field',
      'table'
    ];
    for (var i = 0; i < selectors.length; i += 1) {
      var node = container.querySelector(selectors[i]);
      if (node) return node;
    }
    return null;
  }

  function cappedPush(target, item, limit) {
    if (target.length < limit) target.push(item);
  }

  function severeTailImbalance(childCount, columns) {
    if (columns <= 1 || childCount <= columns) return false;
    var remainder = childCount % columns;
    if (remainder === 0) return false;
    return remainder === 1;
  }

  function hasIntentionalFullSpanTail(grid, children, columns) {
    if (columns !== 2 || children.length !== 3) return false;
    var last = children[children.length - 1];
    var style = window.getComputedStyle(last);
    var start = style.gridColumnStart || '';
    var end = style.gridColumnEnd || '';
    if (end === '-1') return true;
    if (/span\s+2/.test(end)) return true;
    var startNum = parseInt(start, 10);
    var endNum = parseInt(end, 10);
    return !isNaN(startNum) && !isNaN(endNum) && (endNum - startNum) >= 2;
  }

  var symmetryIssues = [];
  document.querySelectorAll('.kpi-block,.kpi-strip,.insight-grid,.framework-grid,.scorecard-grid,.swimlane-track,.value-chain,.process-chain,.risk-matrix,.heatmap-grid,.decision-tree').forEach(function (grid) {
    var children = Array.prototype.filter.call(grid.children || [], function (node) {
      return node.nodeType === 1;
    });
    var childCount = children.length;
    var columns = colCount(grid);
    if (hasIntentionalFullSpanTail(grid, children, columns)) return;
    if (severeTailImbalance(childCount, columns)) {
      cappedPush(symmetryIssues, {
        className: grid.className || '',
        childCount: childCount,
        columns: columns,
        remainder: childCount % columns
      }, 50);
    }
  });

  var alignmentIssues = [];
  document.querySelectorAll('.visual-row.visual-row-equal').forEach(function (row) {
    var blocks = row.querySelectorAll(':scope > .visual-block, :scope > .visual-block-nested');
    if (!blocks || blocks.length < 2) return;
    var containers = [];
    Array.prototype.forEach.call(blocks, function (block) {
      var container = block.querySelector(':scope > .chart-container, :scope > .consulting-figure');
      if (container) containers.push(container);
    });
    if (containers.length < 2) return;
    var bodyA = firstBodyNode(containers[0]);
    var bodyB = firstBodyNode(containers[1]);
    if (!bodyA || !bodyB) return;
    var delta = Math.abs(localTop(bodyA, row) - localTop(bodyB, row));
    if (delta > 6) {
      cappedPush(alignmentIssues, {
        group: row.getAttribute('data-group') || '',
        rowLayout: row.getAttribute('data-row-layout') || '',
        baselineDeltaPx: Math.round(delta)
      }, 50);
    }
  });

  var overflowIssues = [];
  var overflowSelectors = [
    '.kpi-card',
    '.insight-card',
    '.framework-card',
    '.scorecard-item',
    '.matrix-cell',
    '.risk-cell',
    '.heatmap-cell',
    '.swimlane-milestone',
    '.decision-node',
    '.chain-step',
    '.timeline-title,.timeline-body,.driver-title,.driver-body',
    '.range-label,.range-value,.swimlane-label',
    '.lollipop-label,.lollipop-value',
    '.figure-title,.chart-title',
    '.figure-src,.chart-src,.component-src',
    'td,th'
  ].join(',');
  document.querySelectorAll(overflowSelectors).forEach(function (el) {
    var overflowY = el.scrollHeight - el.clientHeight;
    var overflowX = el.scrollWidth - el.clientWidth;
    if (overflowY > 2 || overflowX > 2) {
      cappedPush(overflowIssues, {
        className: el.className || el.tagName.toLowerCase(),
        overflowY: Math.round(Math.max(0, overflowY)),
        overflowX: Math.round(Math.max(0, overflowX)),
        text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 96)
      }, 80);
    }
  });

  document.body.innerHTML = '<pre id="ri-render-qa-json"></pre>';
  document.getElementById('ri-render-qa-json').textContent = JSON.stringify({
    schema: 'report-illustrator-render-qa:v1',
    symmetryIssues: symmetryIssues,
    alignmentIssues: alignmentIssues,
    overflowIssues: overflowIssues
  });
})();
</script>
""".strip()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def find_html(report_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.exists() else None
    candidates = sorted(report_dir.glob("*_illustrated.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def expected_group_counts(recommendations: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rec in recommendations:
        group = str(rec.get("group", "")).strip()
        layout = normalize_layout(rec.get("layout"))
        if group and layout in {"half", "third", "quarter", "compact"}:
            counts[group] = counts.get(group, 0) + 1
    return {group: count for group, count in counts.items() if count >= 2}


def actual_group_counts(html: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for group in re.findall(r'<div\s+[^>]*class=["\'][^"\']*\bvisual-row\b[^"\']*["\'][^>]*data-group=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
        counts[group] = counts.get(group, 0) + 1
    return counts


def duplicate_chart_ids(html: str) -> list[str]:
    ids = re.findall(r'\bid=["\'](chart-C\d+)["\']', html, flags=re.IGNORECASE)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in ids:
        normalized = item.upper()
        if normalized in seen:
            duplicates.add(item)
        seen.add(normalized)
    return sorted(duplicates)


def visual_ids(html: str) -> set[str]:
    return {normalize_chart_id(item) for item in re.findall(r'data-chart-id=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)}


def css_root_variables(html: str) -> dict[str, str]:
    variables: dict[str, str] = {}
    for block in re.findall(r":root\s*\{(.*?)\}", html, flags=re.IGNORECASE | re.DOTALL):
        for name, value in re.findall(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);", block):
            variables[name.strip()] = re.sub(r"\s+", " ", value).strip().lower()
    return variables


def is_white_css_value(value: str) -> bool:
    normalized = value.strip().lower().replace(" ", "")
    return normalized in {"#fff", "#ffffff", "white", "rgb(255,255,255)", "rgba(255,255,255,1)"}


def check_report_surface_tokens(html: str) -> list[str]:
    errors: list[str] = []
    variables = css_root_variables(html)
    for token in ("--report-bg", "--report-surface", "--color-bg", "--color-surface", "--paper"):
        value = variables.get(token)
        if value and not is_white_css_value(value):
            errors.append(f"正式报告大面积底板 token 必须为白色：{token}={value}")
    return errors


def run_dump_dom(path: Path, timeout_seconds: int = 20) -> str:
    browsers = candidate_browsers()
    if not browsers:
        raise RuntimeError("未找到 Chrome/Chromium/Edge，无法执行真实渲染 QA")
    browser = browsers[0]
    uri = path.resolve().as_uri()
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
        "--virtual-time-budget=5000",
        "--dump-dom",
        uri,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    if proc.returncode != 0:
        cmd[1] = "--headless"
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"dump-dom 失败，rc={proc.returncode} stderr={stderr}")
    return proc.stdout


def run_render_qa(html_path: Path) -> dict[str, Any]:
    source = read_text(html_path)
    payload_html = source
    if "</body>" in payload_html:
        payload_html = payload_html.replace("</body>", "\n" + RENDER_QA_SCRIPT + "\n</body>")
    else:
        payload_html += "\n" + RENDER_QA_SCRIPT + "\n"

    with tempfile.TemporaryDirectory(prefix="report-render-qa-") as temp_dir:
        temp_html = Path(temp_dir) / "render_qa.html"
        temp_html.write_text(payload_html, encoding="utf-8")
        dom = run_dump_dom(temp_html)

    matches = re.findall(r'<pre id="ri-render-qa-json">(.*?)</pre>', dom, flags=re.DOTALL)
    if not matches:
        raise RuntimeError("真实渲染 QA 输出缺少 ri-render-qa-json")
    raw = ""
    for candidate in reversed(matches):
        text = html_lib.unescape(candidate.strip())
        if text:
            raw = text
            break
    if not raw:
        raise RuntimeError("真实渲染 QA 输出为空")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or parsed.get("schema") != RENDER_QA_SCHEMA:
        raise RuntimeError("真实渲染 QA 输出 schema 非法")
    return parsed


def run_qa(report_dir: Path, html_path: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    html = read_text(html_path)
    recommendations = parse_recommendations(
        str(report_dir),
        normalize_chart_id=normalize_chart_id,
        read_file=lambda path: Path(path).read_text(encoding="utf-8", errors="ignore"),
    )

    if not re.search(r'<section\b[^>]*class=["\'][^"\']*\breport-cover\b', html, flags=re.IGNORECASE):
        warnings.append("未检测到 .report-cover")
    cover_match = re.search(r'<section\b[^>]*class=["\'][^"\']*\breport-cover\b[^>]*>(.*?)</section>', html, flags=re.IGNORECASE | re.DOTALL)
    if cover_match and re.search(r'<div\b[^>]*class=["\'][^"\']*\bvisual-block\b', cover_match.group(1), flags=re.IGNORECASE):
        errors.append(".report-cover 内部包含 visual-block")
    if re.search(r"<p>\s*<(?:div|script|table|svg)", html, flags=re.IGNORECASE):
        errors.append("存在 <p> 包裹块级元素的非法嵌套")
    for body in re.findall(r"<blockquote\b[^>]*>(.*?)</blockquote>", html, flags=re.IGNORECASE | re.DOTALL):
        if re.search(r"<div\b[^>]*class=[\"'][^\"']*\bvisual-block\b", body, flags=re.IGNORECASE):
            errors.append("存在 visual-block 被注入到 blockquote 内部")
            break
    if re.search(r"html2canvas|jspdf|downloadChart", html, flags=re.IGNORECASE):
        errors.append("存在截图式 PDF 或下载残留逻辑")

    duplicates = duplicate_chart_ids(html)
    if duplicates:
        errors.append("存在重复 chart DOM id：" + ", ".join(duplicates))

    expected_ids = {normalize_chart_id(rec.get("id")) for rec in recommendations if rec.get("id")}
    missing_ids = sorted(expected_ids - visual_ids(html))
    if missing_ids:
        errors.append("recommendation 未注入到 HTML：" + ", ".join(missing_ids))

    expected_groups = expected_group_counts(recommendations)
    actual_groups = actual_group_counts(html)
    for group, count in expected_groups.items():
        if actual_groups.get(group, 0) == 0:
            errors.append(f"group '{group}' 有 {count} 个并排候选，但最终未生成 visual-row")

    if ECHARTS_CSS_VAR_STRING.search(html):
        errors.append("最终 HTML 中 ECharts option 仍直接传入 CSS 变量字符串")

    errors.extend(check_report_surface_tokens(html))

    render_details: dict[str, Any] = {}
    try:
        render_details = run_render_qa(html_path)
    except Exception as exc:  # pragma: no cover - environment-dependent browser probe
        warnings.append(f"真实渲染 QA 未执行：{exc}")
    else:
        symmetry_issues = render_details.get("symmetryIssues", []) or []
        alignment_issues = render_details.get("alignmentIssues", []) or []
        overflow_issues = render_details.get("overflowIssues", []) or []
        if symmetry_issues:
            preview = ", ".join(
                f"{item.get('className', '')}({item.get('columns')}列/{item.get('childCount')}项/余{item.get('remainder')})"
                for item in symmetry_issues[:6]
            )
            errors.append(f"检测到网格重度不均衡（尾行仅 1 项）：{preview}")
        if alignment_issues:
            preview = ", ".join(
                f"group={item.get('group') or '<none>'} delta={item.get('baselineDeltaPx')}px"
                for item in alignment_issues[:6]
            )
            errors.append(f"检测到并排组件标题/正文基线错位：{preview}")
        if overflow_issues:
            preview = ", ".join(
                f"{item.get('className', '')}(+{item.get('overflowY', 0)}y/+{item.get('overflowX', 0)}x)"
                for item in overflow_issues[:8]
            )
            errors.append(f"检测到文本容器真实溢出：{preview}")

    unknown_classes = sorted(cls for cls in classes_in(html) if cls not in DOC_ALLOWED_CLASSES)
    # Fragment classes are validated by lint_fragments; here only catch known generator drift classes.
    bad_generator_classes = [cls for cls in unknown_classes if cls in {"tree-level", "tree-node", "high-impact", "medium-impact", "low-impact", "high-probability", "medium-probability", "low-probability"}]
    if bad_generator_classes:
        errors.append("最终 HTML 含组件协议外关键类：" + ", ".join(sorted(set(bad_generator_classes))))

    visual_blocks = len(re.findall(r'class=["\'][^"\']*\bvisual-block\b', html, flags=re.IGNORECASE))
    visual_rows = len(re.findall(r'class=["\'][^"\']*\bvisual-row\b', html, flags=re.IGNORECASE))
    details = {
        "html_path": str(html_path),
        "recommendations": len(recommendations),
        "visual_blocks": visual_blocks,
        "visual_rows": visual_rows,
        "expected_groups": expected_groups,
        "actual_groups": actual_groups,
        "render_qa": render_details,
        "errors": errors,
        "warnings": warnings
    }
    return errors, warnings, details


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="QA assembled report HTML")
    parser.add_argument("report_dir", help="Report workspace directory")
    parser.add_argument("html_path", nargs="?", help="Optional assembled HTML path")
    parser.add_argument("--json", action="store_true", help="Print JSON details")
    args = parser.parse_args(argv[1:])

    report_dir = Path(args.report_dir).expanduser().resolve()
    html_path = find_html(report_dir, args.html_path)
    if not html_path:
        print(f"[ERROR] 未找到可 QA 的 *_illustrated.html：{report_dir}")
        return 1

    errors, warnings, details = run_qa(report_dir, html_path)
    if args.json:
        print(json.dumps(details, ensure_ascii=False, indent=2))
    else:
        print(f"[HTML_QA] html={html_path}")
        for item in warnings:
            print(f"[WARN] {item}")
        for item in errors:
            print(f"[ERROR] {item}")

    if errors:
        print("[FAIL] HTML QA 未通过")
        return 1
    print("[PASS] HTML QA 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
