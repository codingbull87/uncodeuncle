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
import json
import re
import sys
from pathlib import Path

from build_anchor_index import build_anchor_index_from_html
from lint_fragments import lint_report_dir
from qa_html import find_html, run_qa
from report_contract import normalize_anchor, normalize_chart_id, parse_occurrence
from recommendation_loader import parse_recommendations_base


def has_recommendations(report_dir: Path) -> bool:
    return (report_dir / "RECOMMENDATIONS.json").exists()


ALLOWED_RECOMMENDATION_TYPES = {
    "kpi_strip", "bar_compare", "bar_trend", "line_trend", "waterfall",
    "benchmark_table", "risk_matrix", "matrix_2x2", "timeline", "value_chain",
    "issue_tree", "driver_tree", "range_band", "football_field", "heatmap",
    "roadmap", "scorecard", "decision_tree", "sankey", "tree", "gauge", "insight_cards",
}


def recommendation_insertion_key(item: dict[str, object]) -> tuple[str, str, int]:
    anchor = normalize_anchor(item.get("group_anchor") or item.get("row_anchor") or item.get("anchor"))
    position = str(item.get("position", "")).strip().lower()
    occurrence = parse_occurrence(item.get("anchor_occurrence", item.get("occurrence", 1)))
    return anchor, position, occurrence


def scorecard_has_evidence(item: dict[str, object]) -> bool:
    evidence_keys = ("evidence_lines", "evidence_quotes", "supporting_points", "supporting_quotes")
    for key in evidence_keys:
        value = item.get(key)
        if isinstance(value, list) and any(str(entry).strip() for entry in value):
            return True

    data = item.get("data")
    if not isinstance(data, dict):
        return False

    for key in evidence_keys:
        value = data.get(key)
        if isinstance(value, list) and any(str(entry).strip() for entry in value):
            return True

    candidates: list[dict[str, object]] = []
    for key in ("items", "rows", "cards", "scores"):
        value = data.get(key)
        if isinstance(value, list):
            candidates.extend(entry for entry in value if isinstance(entry, dict))
    if not candidates:
        return False

    evidence_field_names = ("evidence", "evidence_quote", "source_quote", "source_anchor", "basis")
    return all(any(str(entry.get(field, "")).strip() for field in evidence_field_names) for entry in candidates)


def validate_recommendation_contracts(report_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    items = parse_recommendations_base(str(report_dir))
    if not items:
        return errors, warnings

    grouped: dict[str, list[dict[str, object]]] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        chart_id = normalize_chart_id(raw.get("id")) or "<unknown>"
        rec_type = str(raw.get("type", "")).strip().lower()
        if rec_type and rec_type not in ALLOWED_RECOMMENDATION_TYPES:
            warnings.append(f"{chart_id}: recommendation type 未注册（{rec_type}）")
        if rec_type == "scorecard" and not scorecard_has_evidence(raw):
            errors.append(
                f"{chart_id}: scorecard 缺少可追溯证据；必须提供 evidence_lines/evidence_quotes，或为每个评分项提供 evidence/source_anchor/basis"
            )
        group = str(raw.get("group", "")).strip()
        layout = str(raw.get("layout", "")).strip().lower()
        if group and layout in {"half", "third", "quarter", "compact"}:
            grouped.setdefault(group, []).append(raw)

    for group, members in sorted(grouped.items()):
        if len(members) < 2:
            continue
        keys = {recommendation_insertion_key(item) for item in members}
        if len(keys) > 1:
            chart_ids = ", ".join(normalize_chart_id(item.get("id")) or "<unknown>" for item in members)
            detail = "；".join(
                f"{normalize_chart_id(item.get('id')) or '<unknown>'}:{recommendation_insertion_key(item)}"
                for item in members
            )
            errors.append(
                f"group '{group}' 的并排合同不一致：{chart_ids} 必须共享同一个 anchor/group_anchor、position、anchor_occurrence；当前为 {detail}"
            )
    return errors, warnings


def validate_design_brief_json(report_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    path = report_dir / "DESIGN_BRIEF.json"
    if not path.exists():
        errors.append("缺少必需文件：DESIGN_BRIEF.json")
        return errors, warnings

    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as exc:
        errors.append(f"DESIGN_BRIEF.json 解析失败：{exc}")
        return errors, warnings

    if not isinstance(payload, dict):
        errors.append("DESIGN_BRIEF.json 顶层必须是对象")
        return errors, warnings

    color_scheme = str(payload.get("color_scheme", "")).strip().lower()
    allowed = {
        "green", "warm", "wine", "black", "blue",
        "consulting-classic", "institutional-carbon", "banker-monochrome",
        "financial-blue", "burgundy-editorial",
        "consulting-navy", "institutional-blue", "corporate-neutral",
        "financial-trust", "boardroom-green", "monochrome-executive",
        "mckinsey-blue", "modern-slate", "warm-clay", "forest-green", "minimal-light",
    }
    if not color_scheme:
        errors.append("DESIGN_BRIEF.json 缺少 color_scheme")
    elif color_scheme not in allowed:
        errors.append("DESIGN_BRIEF.json color_scheme 非法：" + color_scheme)

    color_confirmed = payload.get("color_confirmed") is True
    if not color_confirmed:
        errors.append("DESIGN_BRIEF.json 缺少 color_confirmed=true；必须先完成用户配色确认")

    candidates = payload.get("color_candidates")
    if not isinstance(candidates, list) or len(candidates) < 3:
        errors.append("DESIGN_BRIEF.json 缺少至少 3 个 color_candidates")

    if color_confirmed:
        selected_by = str(payload.get("color_selected_by", "")).strip().lower()
        allowed_selected_by = {"user", "orchestrator-confirmed"}
        if selected_by not in allowed_selected_by:
            errors.append(
                "DESIGN_BRIEF.json color_selected_by 非法："
                + (selected_by or "<empty>")
                + "；color_confirmed=true 时必须是 user 或 orchestrator-confirmed"
            )

    if "narrative_lines" not in payload:
        warnings.append("DESIGN_BRIEF.json 缺少 narrative_lines，建议补充叙事主线")
    return errors, warnings


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


def validate_prepared_artifacts(report_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    normalized = report_dir / "RECOMMENDATIONS.normalized.json"
    if not normalized.exists():
        errors.append("缺少预处理产物：RECOMMENDATIONS.normalized.json")

    anchor_index = report_dir / "ANCHOR_INDEX.json"
    if not anchor_index.exists():
        errors.append("缺少预处理产物：ANCHOR_INDEX.json")

    anchor_match = report_dir / "ANCHOR_MATCH_REPORT.json"
    if not anchor_match.exists():
        errors.append("缺少预处理产物：ANCHOR_MATCH_REPORT.json")
    else:
        try:
            json.loads(anchor_match.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError as exc:
            errors.append(f"ANCHOR_MATCH_REPORT.json 解析失败：{exc}")

    prep = report_dir / "RECOMMENDATION_PREP.json"
    if not prep.exists():
        errors.append("缺少预处理产物：RECOMMENDATION_PREP.json")
    else:
        try:
            json.loads(prep.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            errors.append("RECOMMENDATION_PREP.json 解析失败；建议重新运行 prepare_recommendations.py")

    authoritative = report_dir / "RECOMMENDATIONS.json"
    derived = [normalized, anchor_match, prep]
    if authoritative.exists():
        stale = [
            path.name
            for path in derived
            if path.exists() and path.stat().st_mtime_ns < authoritative.stat().st_mtime_ns
        ]
        if stale:
            errors.append("预处理产物已落后于当前 RECOMMENDATIONS.json，请重新运行 prepare_recommendations.py：" + ", ".join(stale))
    return errors, warnings


def index_maps(anchor_payload: dict[str, object]) -> tuple[dict[str, dict[str, object]], dict[str, list[dict[str, object]]]]:
    items = [item for item in anchor_payload.get("items", []) if isinstance(item, dict)]
    by_id = {str(item.get("anchor_id", "")).strip(): item for item in items if str(item.get("anchor_id", "")).strip()}
    by_text: dict[str, list[dict[str, object]]] = {}
    for item in items:
        text = normalize_anchor(item.get("text"))
        if text:
            by_text.setdefault(text, []).append(item)
    return by_id, by_text


def choose_by_occurrence(matches: list[dict[str, object]], occurrence: int) -> dict[str, object] | None:
    if not matches:
        return None
    for item in matches:
        if int(item.get("occurrence", 1)) == occurrence:
            return item
    if len(matches) == 1 and occurrence == 1:
        return matches[0]
    return None


def validate_current_recommendation_resolution(report_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    content_path = report_dir / "content.html"
    if not content_path.exists():
        return ["缺少必需文件：content.html"], warnings

    items = parse_recommendations_base(str(report_dir))
    if not items:
        return errors, warnings

    anchor_payload = build_anchor_index_from_html(content_path.read_text(encoding="utf-8", errors="ignore"))
    by_id, by_text = index_maps(anchor_payload)

    for raw in items:
        if not isinstance(raw, dict):
            continue
        chart_id = normalize_chart_id(raw.get("id")) or "<unknown>"
        anchor_id = str(raw.get("anchor_id", "")).strip()
        anchor_text = normalize_anchor(raw.get("group_anchor") or raw.get("row_anchor") or raw.get("anchor"))
        occurrence = parse_occurrence(raw.get("anchor_occurrence", raw.get("occurrence", 1)))
        if not anchor_id:
            errors.append(f"{chart_id}: 当前 RECOMMENDATIONS.json 缺少 anchor_id；请重新运行 prepare_recommendations.py")
            continue
        if not anchor_text:
            errors.append(f"{chart_id}: 当前 RECOMMENDATIONS.json 缺少 anchor/group_anchor/row_anchor")
            continue
        resolved_item = choose_by_occurrence(by_text.get(anchor_text, []), occurrence)
        if not resolved_item:
            errors.append(f"{chart_id}: 当前 RECOMMENDATIONS.json anchor 未命中正文 heading（{anchor_text}）")
            continue
        resolved_anchor_id = str(resolved_item.get("anchor_id", "")).strip()
        if anchor_id != resolved_anchor_id:
            errors.append(
                f"{chart_id}: 当前 RECOMMENDATIONS.json anchor_id 与 anchor 文本不一致（anchor_id={anchor_id} anchor={anchor_text} expected={resolved_anchor_id}）"
            )
            continue
        if anchor_id not in by_id:
            errors.append(f"{chart_id}: 当前 RECOMMENDATIONS.json anchor_id 未命中正文 heading（{anchor_id}）")
    return errors, warnings


def validate_export_artifacts(report_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for name in ("ASSEMBLY_DIAGNOSTICS.json", "THEME_RESOLUTION.json"):
        if not (report_dir / name).exists():
            errors.append(f"缺少导出前诊断文件：{name}")

    html_path = find_html(report_dir, None)
    if not html_path or not html_path.exists():
        return errors, warnings

    html_text = html_path.read_text(encoding="utf-8", errors="ignore")
    meta_match = re.search(
        r'<meta\s+name=["\']report-color-scheme["\']\s+content=["\']([^"\']+)["\']',
        html_text,
        flags=re.IGNORECASE,
    )
    theme_payload = validate_design_brief_json(report_dir)[0]
    expected_payload = {}
    brief_path = report_dir / "DESIGN_BRIEF.json"
    if brief_path.exists():
        try:
            expected_payload = json.loads(brief_path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            expected_payload = {}
    expected_scheme = str(expected_payload.get("color_scheme", "")).strip().lower() if isinstance(expected_payload, dict) else ""
    actual_scheme = meta_match.group(1).strip().lower() if meta_match else ""
    if expected_scheme and actual_scheme and expected_scheme != actual_scheme:
        errors.append(
            f"最终 HTML 主题与 DESIGN_BRIEF.json 不一致：expected={expected_scheme} actual={actual_scheme}"
        )
    elif expected_scheme and not actual_scheme:
        errors.append("最终 HTML 缺少 report-color-scheme meta，无法验证主题锁定")
    if theme_payload:
        # No-op: keep the design brief validation side effect in this stage.
        pass
    return errors, warnings


ISSUE_PATTERNS: list[tuple[str, str, str]] = [
    ("缺少预处理产物：RECOMMENDATIONS.normalized.json", "MISSING_NORMALIZED_RECOMMENDATIONS", "先运行 prepare_recommendations.py，确保 recommendation 只有一个机器真实源。"),
    ("缺少预处理产物：ANCHOR_INDEX.json", "MISSING_ANCHOR_INDEX", "先运行 build_anchor_index.py，从 content.html 固化 heading 索引。"),
    ("缺少预处理产物：ANCHOR_MATCH_REPORT.json", "MISSING_ANCHOR_MATCH_REPORT", "先运行 prepare_recommendations.py，生成 anchor 解析结果。"),
    ("缺少预处理产物：RECOMMENDATION_PREP.json", "MISSING_RECOMMENDATION_PREP", "先运行 prepare_recommendations.py，生成 recommendation 预处理诊断。"),
    ("仍有未解析 anchor", "UNRESOLVED_ANCHORS", "修正 RECOMMENDATIONS.json 中的 anchor/anchor_id，使其命中 ANCHOR_INDEX.json。"),
    ("预处理产物已落后于当前 RECOMMENDATIONS.json", "STALE_RECOMMENDATION_DERIVED_FILES", "当前 JSON 已被修改；重新运行 prepare_recommendations.py 刷新派生文件。"),
    ("当前 RECOMMENDATIONS.json", "AUTHORITATIVE_JSON_INVALID", "修正当前 RECOMMENDATIONS.json 的 anchor/anchor_id，使其与正文 heading 一致。"),
    ("color_scheme 非法", "INVALID_COLOR_SCHEME", "把 DESIGN_BRIEF.json 的 color_scheme 改为受支持的 palette 代号。"),
    ("缺少 color_confirmed=true", "COLOR_NOT_CONFIRMED", "完成用户配色确认，并把 DESIGN_BRIEF.json 写成 color_confirmed=true。"),
    ("缺少 VALIDATION.md 判定", "MISSING_VALIDATION_DECISION", "先完成 Phase 5，并由 validator 产出唯一判定。"),
    ("判定为", "VALIDATION_BLOCKED", "不要绕过 validator 结论；先修 recommendation 或 brief 问题。"),
    ("并排合同不一致", "GROUP_CONTRACT_MISMATCH", "并排 group 成员必须共享 anchor/position/anchor_occurrence。"),
    ("scorecard 缺少可追溯证据", "SCORECARD_MISSING_EVIDENCE", "给 scorecard 每个评分项补可追溯证据字段。"),
    ("片段质量不合格", "FRAGMENT_LINT_FAILED", "先运行 normalize_fragments.py，再修复 lint 仍未自动收敛的问题。"),
    ("HTML QA 不合格", "HTML_QA_FAILED", "不要继续导出；先修组装或片段问题直到 HTML QA 通过。"),
    ("稀疏页", "LAYOUT_SPARSE_PAGE", "先完成 layout repair，让普通页不再出现大面积空白。"),
    ("最终 HTML 主题与 DESIGN_BRIEF.json 不一致", "THEME_LOCK_BROKEN", "检查 assemble 输出 meta 与 DESIGN_BRIEF.json 是否一致。"),
]


def classify_issue(message: str) -> dict[str, str]:
    for needle, code, remediation in ISSUE_PATTERNS:
        if needle in message:
            return {"code": code, "message": message, "remediation": remediation}
    return {
        "code": "UNCLASSIFIED",
        "message": message,
        "remediation": "按报错文字修复对应文件，再重新运行当前阶段门禁。",
    }


def write_gate_status(report_dir: Path, stage: str, errors: list[str], warnings: list[str]) -> Path:
    payload = {
        "schema": "report-illustrator-gate-status:v1",
        "stage": stage,
        "pass": not errors,
        "warnings": [classify_issue(item) for item in warnings],
        "errors": [classify_issue(item) for item in errors],
    }
    path = report_dir / f"GATE_STATUS.{stage}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


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

    brief_errors, brief_warnings = validate_design_brief_json(report_dir)
    errors.extend(brief_errors)
    warnings.extend(brief_warnings)

    if not has_recommendations(report_dir):
        errors.append("缺少推荐项文件：RECOMMENDATIONS.json")
    else:
        rec_errors, rec_warnings = validate_recommendation_contracts(report_dir)
        errors.extend(rec_errors)
        warnings.extend(rec_warnings)
        source_errors, source_warnings = validate_current_recommendation_resolution(report_dir)
        errors.extend(source_errors)
        warnings.extend(source_warnings)
        prep_errors, prep_warnings = validate_prepared_artifacts(report_dir)
        errors.extend(prep_errors)
        warnings.extend(prep_warnings)

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

    html_path = find_html(report_dir, None)
    if not html_path:
        errors.append("未找到可执行 HTML QA 的 *_illustrated.html")
        return errors, warnings
    html_errors, html_warnings, _ = run_qa(report_dir, html_path)
    errors.extend("HTML QA 不合格：" + item for item in html_errors)
    warnings.extend("HTML QA 告警：" + item for item in html_warnings)

    layout_diag = report_dir / "LAYOUT_DIAGNOSIS.json"
    if layout_diag.exists():
        try:
            payload = json.loads(layout_diag.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError as exc:
            errors.append(f"LAYOUT_DIAGNOSIS.json 解析失败：{exc}")
        else:
            sparse = payload.get("sparsePages", [])
            terminal_sparse = payload.get("terminalSparsePages", [])
            if isinstance(sparse, list) and sparse:
                errors.append(f"LAYOUT_DIAGNOSIS.json 仍有 {len(sparse)} 个稀疏页，禁止进入 Phase 8")
            if isinstance(terminal_sparse, list) and terminal_sparse:
                errors.append(f"LAYOUT_DIAGNOSIS.json 仍有 {len(terminal_sparse)} 个末页稀疏页，禁止进入 Phase 8")
    export_errors, export_warnings = validate_export_artifacts(report_dir)
    errors.extend(export_errors)
    warnings.extend(export_warnings)
    return errors, warnings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check phase contract for md2report")
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

    gate_status_path = write_gate_status(report_dir, args.stage, errors, warnings)
    print(f"[GATE] stage={args.stage} report_dir={report_dir}")
    print(f"[INFO] gate_status={gate_status_path}")
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
