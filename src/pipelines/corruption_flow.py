from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _require_artifacts(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise RuntimeError("Run the baseline pipeline first; missing artifacts: " + ", ".join(missing))


def _save_dataframe(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def main() -> None:
    settings = load_settings()
    _require_artifacts(
        [
            settings.paths.raw_records_json,
            settings.paths.clean_json,
            settings.paths.eval_testset,
            settings.paths.baseline_metrics,
        ]
    )

    baseline = pd.DataFrame(read_json(settings.paths.clean_json))
    if baseline.empty:
        raise RuntimeError("Baseline clean artifact is empty; cannot run corruption flow.")
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_quality = run_data_quality_checks(baseline, settings, "baseline_quality")
    baseline_freshness = build_freshness_report(
        baseline, settings, settings.paths.freshness_report
    )

    corrupted = corrupt_clean_dataframe(baseline, settings.paths.corruption_log)
    _save_dataframe(
        corrupted,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted, settings, settings.paths.corrupted_embeddings_json
    )
    corrupted_evaluation = evaluate_pipeline(
        settings,
        corrupted_index,
        settings.paths.eval_testset,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted, settings, "corrupted_quality")
    corrupted_freshness = build_freshness_report(
        corrupted,
        settings,
        settings.paths.quality_dir / "corrupted_freshness.json",
    )

    repaired = build_clean_dataframe(
        load_raw_records(settings.paths.raw_records_json),
        now_utc(),
    )
    if repaired.empty:
        raise RuntimeError("Repair from raw records produced no clean records.")
    _save_dataframe(
        repaired,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )
    repaired_index = LocalEmbeddingIndex.build(
        repaired, settings, settings.paths.repaired_embeddings_json
    )
    repaired_evaluation = evaluate_pipeline(
        settings,
        repaired_index,
        settings.paths.eval_testset,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired, settings, "repaired_quality")
    repaired_freshness = build_freshness_report(
        repaired,
        settings,
        settings.paths.quality_dir / "repaired_freshness.json",
    )

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_evaluation.summary,
        repaired_evaluation.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        baseline_quality=baseline_quality,
        baseline_freshness=baseline_freshness,
    )
