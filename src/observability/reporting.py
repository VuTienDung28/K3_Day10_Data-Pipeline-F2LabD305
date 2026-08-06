from __future__ import annotations

import json
from numbers import Number
from pathlib import Path
from typing import Any

from core.utils import write_text


PRIMARY_METRICS = [
    "retrieval_hit_rate",
    "mean_token_f1",
    "judge_accuracy",
    "mean_judge_score",
]


def _escape(value: Any) -> str:
    if value is None:
        return "N/A"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _format_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (dict, list)):
        return _escape(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return _escape(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Number):
        return None
    return float(value)


def _metric_label(name: str) -> str:
    return name.replace("_", " ").title()


def _quality_status(quality: dict[str, Any]) -> str:
    if not quality:
        return "unknown"
    if "status" in quality:
        return str(quality["status"])
    if "success" in quality:
        return "pass" if quality["success"] else "fail"
    return "unknown"


def _freshness_status(freshness: dict[str, Any]) -> str:
    if not freshness:
        return "unknown"
    if "status" in freshness:
        return str(freshness["status"])
    if "is_fresh" in freshness:
        return "fresh" if freshness["is_fresh"] else "stale"
    return "unknown"


def _quality_table(quality: dict[str, Any]) -> list[str]:
    lines = [
        "| Check | Dimension | Severity | Status | Observed | Expected | Details |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    checks = quality.get("checks", []) if quality else []
    if not checks:
        lines.append("| N/A | N/A | N/A | UNKNOWN | N/A | No checks supplied | N/A |")
        return lines

    for check in checks:
        details = ", ".join(str(item) for item in check.get("details", [])) or "-"
        lines.append(
            "| {name} | {dimension} | {severity} | {status} | {observed} | {expected} | {details} |".format(
                name=_escape(check.get("name")),
                dimension=_escape(check.get("dimension")),
                severity=_escape(check.get("severity", "error")),
                status="PASS" if check.get("success") else "FAIL",
                observed=_format_value(check.get("observed")),
                expected=_escape(check.get("expected")),
                details=_escape(details),
            )
        )
    return lines


def _failed_check_names(quality: dict[str, Any]) -> list[str]:
    return [
        str(check.get("name", "unnamed_check"))
        for check in quality.get("checks", [])
        if not check.get("success")
    ]


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write an evidence-based Markdown report for the baseline phase."""
    source_fields = [
        ("Source API", "source_api"),
        ("Query", "query"),
        ("Filter", "filter"),
        ("Raw records", "raw_records"),
        ("Clean records", "clean_records"),
        ("Embedding model", "embedding_model"),
        ("Collection", "collection_name"),
    ]
    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Source and pipeline",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    for label, key in source_fields:
        lines.append(f"| {label} | {_format_value(source_summary.get(key))} |")

    lines.extend(
        [
            "",
            "## Evaluation metrics",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Samples | {_format_value(metrics.get('samples'))} |",
        ]
    )
    for metric in PRIMARY_METRICS:
        lines.append(f"| `{metric}` | {_format_value(metrics.get(metric))} |")
    lines.append(f"| `ragas` | {_format_value(metrics.get('ragas'))} |")

    lines.extend(
        [
            "",
            "## Data quality",
            "",
            f"Overall status: **{_quality_status(quality).upper()}**  ",
            f"Rows checked: **{_format_value(quality.get('total_rows'))}**  ",
            f"Failed error checks: **{_format_value(quality.get('failed_checks'))}**  ",
            f"Warning checks: **{_format_value(quality.get('warning_checks'))}**",
            "",
            *_quality_table(quality),
            "",
            "## Freshness",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Status | **{_freshness_status(freshness).upper()}** |",
            f"| Latest publication | {_format_value(freshness.get('latest_published'))} |",
            f"| Oldest publication | {_format_value(freshness.get('oldest_published'))} |",
            f"| Stale rows | {_format_value(freshness.get('stale_rows'))} |",
            f"| Invalid date rows | {_format_value(freshness.get('invalid_date_rows'))} |",
            f"| Threshold (days) | {_format_value(freshness.get('freshness_threshold_days'))} |",
            f"| Maximum age (days) | {_format_value(freshness.get('max_age_days'))} |",
            "",
            "## Baseline conclusion",
            "",
        ]
    )
    failed_names = _failed_check_names(quality)
    if failed_names:
        lines.append(
            "The baseline has unresolved quality signals: "
            + ", ".join(f"`{_escape(name)}`" for name in failed_names)
            + "."
        )
    elif not freshness.get("is_fresh", False):
        lines.append("The quality checks passed, but the corpus is not currently fresh.")
    else:
        lines.append("The baseline quality checks passed and the corpus is fresh at the configured threshold.")
    lines.append(
        "Evaluation conclusions should be interpreted from the recorded metrics and answer artifacts, "
        "not from pipeline exit status alone."
    )

    write_text(Path(report_path), "\n".join(lines).rstrip() + "\n")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write a comparison report without assuming that corruption or repair worked."""
    lines = [
        "# Corruption and Repair Comparison",
        "",
        "## Evaluation comparison",
        "",
        "| Metric | Baseline | Corrupted | Repaired | Corruption delta | Repair delta | Recovery |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for metric in PRIMARY_METRICS:
        baseline = _number(baseline_metrics.get(metric))
        corrupted = _number(corrupted_metrics.get(metric))
        repaired = _number(repaired_metrics.get(metric))
        corruption_delta = corrupted - baseline if baseline is not None and corrupted is not None else None
        repair_delta = repaired - corrupted if corrupted is not None and repaired is not None else None
        denominator = baseline - corrupted if baseline is not None and corrupted is not None else None
        recovery = (
            (repaired - corrupted) / denominator
            if repaired is not None and denominator not in {None, 0.0}
            else None
        )
        lines.append(
            f"| `{metric}` | {_format_value(baseline)} | {_format_value(corrupted)} | "
            f"{_format_value(repaired)} | {_format_value(corruption_delta)} | "
            f"{_format_value(repair_delta)} | {_format_value(recovery)} |"
        )

    lines.extend(
        [
            "",
            "## Quality and freshness signals",
            "",
            "| Signal | Corrupted | Repaired |",
            "| --- | --- | --- |",
            f"| Quality status | **{_quality_status(corrupted_quality).upper()}** | **{_quality_status(repaired_quality).upper()}** |",
            f"| Failed checks | {_format_value(corrupted_quality.get('failed_checks'))} | {_format_value(repaired_quality.get('failed_checks'))} |",
            f"| Warning checks | {_format_value(corrupted_quality.get('warning_checks'))} | {_format_value(repaired_quality.get('warning_checks'))} |",
            f"| Freshness status | **{_freshness_status(corrupted_freshness).upper()}** | **{_freshness_status(repaired_freshness).upper()}** |",
            f"| Stale rows | {_format_value(corrupted_freshness.get('stale_rows'))} | {_format_value(repaired_freshness.get('stale_rows'))} |",
            f"| Invalid date rows | {_format_value(corrupted_freshness.get('invalid_date_rows'))} | {_format_value(repaired_freshness.get('invalid_date_rows'))} |",
            "",
            "### Failed or warning checks",
            "",
            "- Corrupted: "
            + (", ".join(f"`{_escape(name)}`" for name in _failed_check_names(corrupted_quality)) or "none"),
            "- Repaired: "
            + (", ".join(f"`{_escape(name)}`" for name in _failed_check_names(repaired_quality)) or "none"),
            "",
            "## Evidence-based conclusion",
            "",
        ]
    )

    changed_metrics: list[str] = []
    recovered_metrics: list[str] = []
    for metric in PRIMARY_METRICS:
        baseline = _number(baseline_metrics.get(metric))
        corrupted = _number(corrupted_metrics.get(metric))
        repaired = _number(repaired_metrics.get(metric))
        if baseline is not None and corrupted is not None and corrupted < baseline:
            changed_metrics.append(metric)
        if baseline is not None and corrupted is not None and repaired is not None and repaired > corrupted:
            recovered_metrics.append(metric)

    if changed_metrics:
        lines.append(
            "Corruption reduced the following recorded metrics: "
            + ", ".join(f"`{metric}`" for metric in changed_metrics)
            + "."
        )
    else:
        lines.append("The supplied metrics do not show a measurable performance decrease after corruption.")

    if recovered_metrics:
        lines.append(
            "Repair improved the following metrics relative to the corrupted state: "
            + ", ".join(f"`{metric}`" for metric in recovered_metrics)
            + "."
        )
    else:
        lines.append("The supplied metrics do not show measurable recovery after repair.")

    if _quality_status(repaired_quality) != "pass" or _freshness_status(repaired_freshness) != "fresh":
        lines.append("Repair should not be declared complete because repaired quality or freshness still has unresolved signals.")
    else:
        lines.append("The repaired dataset passes the supplied quality and freshness checks.")

    write_text(Path(report_path), "\n".join(lines).rstrip() + "\n")
