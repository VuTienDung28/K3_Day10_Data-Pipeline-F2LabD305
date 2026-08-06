from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report, generate_phase1_report


def _settings(tmp_path: Path, max_results: int = 3):
    settings = load_settings()
    paths = replace(
        settings.paths,
        quality_dir=tmp_path / "quality",
        freshness_report=tmp_path / "quality" / "freshness.json",
        baseline_report=tmp_path / "reports" / "phase1.md",
        comparison_report=tmp_path / "reports" / "corruption.md",
    )
    return replace(settings, max_results=max_results, paths=paths)


def _clean_dataframe() -> pd.DataFrame:
    today = pd.Timestamp(now_utc()).normalize()
    rows = []
    for index, age_days in enumerate([10, 20, 30], start=1):
        title = f"A sufficiently descriptive scholarly paper title number {index}"
        summary = (
            f"This is the complete summary for scholarly paper {index}. "
            "It contains enough factual context for retrieval, evaluation, and data quality validation. "
            "The remaining words make the abstract safely longer than the configured minimum length."
        )
        rows.append(
            {
                "paper_id": f"10.1234/paper-{index}",
                "title": title,
                "summary": summary,
                "published": (today - pd.Timedelta(days=age_days)).date().isoformat(),
                "age_days": age_days,
                "authors_joined": f"Author {index}",
                "categories_joined": "computer science",
                "text_for_embedding": f"Title: {title} | Summary: {summary}",
            }
        )
    return pd.DataFrame(rows)


def _check_map(payload: dict) -> dict[str, dict]:
    return {check["name"]: check for check in payload["checks"]}


def test_clean_dataset_passes_quality_and_freshness(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    df = _clean_dataframe()

    quality = run_data_quality_checks(df, settings, "baseline_quality")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

    assert quality["success"] is True
    assert quality["status"] == "pass"
    assert quality["failed_checks"] == 0
    assert freshness["is_fresh"] is True
    assert freshness["status"] == "fresh"
    assert read_json(tmp_path / "quality" / "baseline_quality.json")["success"] is True
    assert read_json(settings.paths.freshness_report)["is_fresh"] is True


def test_corruption_signals_are_detected_without_crashing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    corrupted = _clean_dataframe()
    corrupted.loc[0, "summary"] = ""
    corrupted.loc[1, "title"] = "short"
    corrupted.loc[2, "summary"] += " [CORRUPTED_NOISE]"
    old_date = pd.Timestamp(now_utc()).normalize() - pd.Timedelta(days=400)
    corrupted.loc[2, "published"] = old_date.date().isoformat()
    corrupted.loc[2, "age_days"] = 400
    corrupted = pd.concat([corrupted, corrupted.iloc[[0]]], ignore_index=True)

    quality = run_data_quality_checks(corrupted, settings, "corrupted_quality")
    freshness = build_freshness_report(
        corrupted,
        settings,
        tmp_path / "quality" / "corrupted_freshness.json",
    )
    checks = _check_map(quality)

    assert quality["success"] is False
    assert checks["paper_id_unique"]["success"] is False
    assert checks["title_min_length"]["success"] is False
    assert checks["summary_not_null"]["success"] is False
    assert checks["summary_noise_markers"]["success"] is False
    assert checks["freshness_threshold"]["success"] is False
    assert checks["embedding_contains_title"]["success"] is False
    assert checks["embedding_contains_summary"]["success"] is False
    assert freshness["is_fresh"] is False
    assert freshness["stale_rows"] == 1


def test_dropped_rows_and_missing_schema_fail_cleanly(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    dropped = _clean_dataframe().iloc[:2].copy()
    dropped_quality = run_data_quality_checks(dropped, settings, "dropped_quality")
    assert _check_map(dropped_quality)["row_count"]["success"] is False

    malformed = pd.DataFrame([{"paper_id": "10.1/incomplete"}])
    malformed_quality = run_data_quality_checks(malformed, settings, "malformed_quality")
    malformed_freshness = build_freshness_report(
        malformed,
        settings,
        tmp_path / "quality" / "malformed_freshness.json",
    )
    assert malformed_quality["success"] is False
    assert _check_map(malformed_quality)["required_columns"]["success"] is False
    assert malformed_freshness["status"] == "unknown"
    assert malformed_freshness["invalid_date_rows"] == 1


def test_reports_render_real_values_and_comparison_deltas(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    clean = _clean_dataframe()
    corrupted = clean.copy()
    corrupted.loc[0, "summary"] = ""
    repaired_quality = run_data_quality_checks(clean, settings, "repaired_quality")
    corrupted_quality = run_data_quality_checks(corrupted, settings, "corrupted_quality")
    repaired_freshness = build_freshness_report(
        clean, settings, tmp_path / "quality" / "repaired_freshness.json"
    )
    corrupted_freshness = build_freshness_report(
        corrupted, settings, tmp_path / "quality" / "corrupted_freshness.json"
    )

    baseline_metrics = {
        "samples": 12,
        "retrieval_hit_rate": 1.0,
        "mean_token_f1": 0.9,
        "judge_accuracy": 1.0,
        "mean_judge_score": 4.8,
        "ragas": {"skipped": "test fixture"},
    }
    corrupted_metrics = {
        "samples": 12,
        "retrieval_hit_rate": 0.5,
        "mean_token_f1": 0.4,
        "judge_accuracy": 0.5,
        "mean_judge_score": 2.5,
    }
    repaired_metrics = {
        "samples": 12,
        "retrieval_hit_rate": 1.0,
        "mean_token_f1": 0.85,
        "judge_accuracy": 1.0,
        "mean_judge_score": 4.6,
    }

    generate_phase1_report(
        settings.paths.baseline_report,
        {
            "source_api": "Crossref REST API",
            "query": "RAG",
            "filter": "has-abstract:true",
            "raw_records": 3,
            "clean_records": 3,
            "embedding_model": "MiniLM",
            "collection_name": "papers-baseline",
        },
        baseline_metrics,
        repaired_quality,
        repaired_freshness,
    )
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )

    baseline_text = settings.paths.baseline_report.read_text(encoding="utf-8")
    comparison_text = settings.paths.comparison_report.read_text(encoding="utf-8")
    assert "Phase 1 Baseline Report" in baseline_text
    assert "`retrieval_hit_rate` | 1.0000" in baseline_text
    assert "Corruption and Repair Comparison" in comparison_text
    assert "`retrieval_hit_rate` | 1.0000 | 0.5000 | 1.0000 | -0.5000 | 0.5000 | 1.0000" in comparison_text
    assert "Repair improved" in comparison_text
