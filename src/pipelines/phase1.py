from __future__ import annotations

from uuid import uuid4

from core.config import load_settings, normalized_provider
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_agent_pipeline, evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    started_at = now_utc()
    run_id = str(uuid4())
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(settings.paths.raw_records_json)

    clean = build_clean_dataframe(records, now_utc())
    if clean.empty:
        raise RuntimeError("Cleaning produced no records; cannot build the baseline pipeline.")
    write_csv(clean, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(clean, settings, settings.paths.embeddings_json)
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        build_test_set(clean, settings.paths.eval_testset)

    evaluation = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    agent_evaluation = evaluate_agent_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_agent_metrics,
        settings.paths.baseline_agent_answers,
    )
    write_json(
        settings.paths.demo_answers,
        {
            "schema_version": 1,
            "provider": normalized_provider(settings),
            "model": settings.model_name,
            "states": {"baseline": str(settings.paths.baseline_agent_answers.relative_to(settings.paths.project_dir))},
        },
    )
    quality = run_data_quality_checks(clean, settings, "baseline_quality")
    freshness = build_freshness_report(clean, settings, settings.paths.freshness_report)
    generate_phase1_report(
        settings.paths.baseline_report,
        {
            "source_api": settings.source_api,
            "query": settings.source_query,
            "filter": settings.source_filter,
            "raw_records": len(records),
            "clean_records": len(clean),
            "embedding_model": settings.embedding_model,
            "collection_name": index.collection_name,
        },
        evaluation.summary,
        quality,
        freshness,
        agent_metrics=agent_evaluation.summary,
    )
    write_json(
        settings.paths.baseline_run,
        {
            "schema_version": 1,
            "run_id": run_id,
            "started_at": started_at.isoformat(),
            "completed_at": now_utc().isoformat(),
            "provider": normalized_provider(settings),
            "model": settings.model_name,
            "embedding_model": settings.embedding_model,
            "test_set_sha256": evaluation.summary["test_set_sha256"],
            "artifacts": {
                "reference_metrics": str(settings.paths.baseline_metrics.relative_to(settings.paths.project_dir)),
                "agent_metrics": str(settings.paths.baseline_agent_metrics.relative_to(settings.paths.project_dir)),
                "report": str(settings.paths.baseline_report.relative_to(settings.paths.project_dir)),
            },
        },
    )
