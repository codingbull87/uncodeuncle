#!/usr/bin/env python3
"""
Phase gate checks for Report Illustrator workflow contracts.

Usage:
  python3 scripts/check_phase_contract.py <report_dir> <stage>

Stages:
  - before-fragments : gate before Phase 6
  - before-assemble  : gate before Phase 7
  - before-export    : gate before Phase 8
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from lint_fragments import lint_report_dir


def has_recommendations(report_dir: Path) -> bool:
    return (report_dir / "RECOMMENDATIONS.md").exists() or (report_dir / "RECOMMENDATIONS.json").exists()


def parse_validation_decision(report_dir: Path) -> str:
    path = report_dir / "VALIDATION.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    explicit = re.findall(
        r"^\s*(?:-+\s*)?判定[:：]\s*(PROCEED|NEEDS_ITERATION|NEEDS_CLARIFICATION)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if len(explicit) == 1:
        return explicit[0].upper()
    if len(explicit) > 1:
        return ""

    tokens = {
        item.upper()
        for item in re.findall(r"\b(PROCEED|NEEDS_ITERATION|NEEDS_CLARIFICATION)\b", text, flags=re.IGNORECASE)
    }
    if len(tokens) == 1:
        return next(iter(tokens))
    return ""


def list_fragment_files(report_dir: Path) -> list[Path]:
    fragments_dir = report_dir / "chart-fragments"
    if not fragments_dir.exists():
        return []
    return sorted(path for path in fragments_dir.glob("*.html") if path.is_file())


def classify_fragment_names(report_dir: Path) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    invalid: list[str] = []
    for path in list_fragment_files(report_dir):
        name = path.name
        if re.fullmatch(r"C\d+\.html", name, flags=re.IGNORECASE):
            valid.append(name)
        else:
            invalid.append(name)
    return valid, invalid


def find_illustrated_html(report_dir: Path) -> list[str]:
    return sorted(path.name for path in report_dir.glob("*_illustrated.html") if path.is_file())


def detect_drift_artifacts(report_dir: Path) -> list[str]:
    suspicious = [
        "assemble_final.py",
        "report_final.html",
        "report_final.pdf",
    ]
    found: list[str] = []
    for name in suspicious:
        if (report_dir / name).exists():
            found.append(name)
    return found


def check_before_fragments(report_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "content.html",
        "DESIGN_BRIEF.md",
    ]
    for name in required:
        if not (report_dir / name).exists():
            errors.append(f"缺少必需文件：{name}")

    if not has_recommendations(report_dir):
        errors.append("缺少推荐项文件：RECOMMENDATIONS.md 或 RECOMMENDATIONS.json")

    decision = parse_validation_decision(report_dir)
    if not decision:
        errors.append("缺少 VALIDATION.md 判定（需要 PROCEED 才能进入 Phase 6）")
    elif decision != "PROCEED":
        errors.append(f"VALIDATION.md 判定为 {decision}，禁止进入 Phase 6")

    _, invalid = classify_fragment_names(report_dir)
    if invalid:
        errors.append("存在非法片段命名：" + ", ".join(invalid))

    drift = detect_drift_artifacts(report_dir)
    if drift:
        errors.append("发现跑偏产物，需清理后重试：" + ", ".join(drift))

    return errors, warnings


def check_before_assemble(report_dir: Path) -> tuple[list[str], list[str]]:
    errors, warnings = check_before_fragments(report_dir)
    valid, invalid = classify_fragment_names(report_dir)
    if invalid:
        errors.append("存在非法片段命名：" + ", ".join(invalid))
    if not valid:
        errors.append("未找到可组装片段：chart-fragments/C{id}.html")
    lint_errors, lint_warnings, _ = lint_report_dir(report_dir)
    errors.extend("片段质量不合格：" + item for item in lint_errors)
    warnings.extend("片段质量告警：" + item for item in lint_warnings)
    return errors, warnings


def check_before_export(report_dir: Path) -> tuple[list[str], list[str]]:
    errors, warnings = check_before_assemble(report_dir)
    illustrated = find_illustrated_html(report_dir)
    if not illustrated:
        errors.append("未找到 *_illustrated.html，禁止进入 Phase 8")
    return errors, warnings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check phase contract for report-illustrator")
    parser.add_argument("report_dir", help="Report workspace directory")
    parser.add_argument(
        "stage",
        choices=["before-fragments", "before-assemble", "before-export"],
        help="Gate stage to check",
    )
    args = parser.parse_args(argv[1:])

    report_dir = Path(args.report_dir).expanduser().resolve()
    if not report_dir.exists() or not report_dir.is_dir():
        print(f"[ERROR] 报告目录不存在：{report_dir}")
        return 1

    if args.stage == "before-fragments":
        errors, warnings = check_before_fragments(report_dir)
    elif args.stage == "before-assemble":
        errors, warnings = check_before_assemble(report_dir)
    else:
        errors, warnings = check_before_export(report_dir)

    print(f"[GATE] stage={args.stage} report_dir={report_dir}")
    for item in warnings:
        print(f"[WARN] {item}")
    for item in errors:
        print(f"[ERROR] {item}")

    if errors:
        print("[FAIL] 未通过阶段门禁检查")
        return 1

    print("[PASS] 阶段门禁检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
