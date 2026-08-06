from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_json
from pipelines import corruption_flow, phase1


def _settings(tmp_path: Path):
    settings = load_settings(tmp_path)
    return replace(settings, max_results=1, refresh_source=False, refresh_test_set=False)


def _clean_dataframe() -> pd.DataFrame:
    summary = "A sufficiently detailed summary that is long enough for the clean data contract and pipeline tests."
    return pd.DataFrame(
        [
            {
                "paper_id": "10.1234/paper",
                "title": "A sufficiently descriptive paper title",
                "summary": summary,
                "authors": ["Author"],
                "categories": ["AI"],
                "primary_category": "AI",
                "published": "2026-08-01",
                "updated": "2026-08-01",
                "age_days": 5,
                "authors_joined": "Author",
                "categories_joined": "AI",
                "summary_chars": len(summary),
                "text_for_embedding": f"Title: A sufficiently descriptive paper title | Authors: Author | Summary: {summary}",
                "abs_url": "https://example.test/paper",
                "pdf_url": "",
                "comment": "",
            }
        ]
    )


def test_phase1_reuses_raw_and_testset_and_writes_baseline_artifacts(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    settings.paths.raw_records_json.parent.mkdir(parents=True)
    settings.paths.raw_records_json.write_text("[]", encoding="utf-8")
    settings.paths.eval_testset.parent.mkdir(parents=True)
    settings.paths.eval_testset.write_text("[]", encoding="utf-8")
    clean = _clean_dataframe()
    calls: list[str] = []

    monkeypatch.setattr(phase1, "load_settings", lambda: settings)
    monkeypatch.setattr(phase1, "load_raw_records", lambda path: calls.append("load_raw") or [object()])
    monkeypatch.setattr(phase1, "fetch_source_records", lambda _settings: (_ for _ in ()).throw(AssertionError("must reuse raw")))
    monkeypatch.setattr(phase1, "build_clean_dataframe", lambda records, run_date: clean)
    monkeypatch.setattr(
        phase1.LocalEmbeddingIndex,
        "build",
        lambda df, current_settings, output_path: calls.append("index")
        or SimpleNamespace(collection_name="papers-baseline"),
    )
    monkeypatch.setattr(phase1, "build_test_set", lambda *args: (_ for _ in ()).throw(AssertionError("must reuse test set")))
    monkeypatch.setattr(
        phase1,
        "evaluate_pipeline",
        lambda *args: SimpleNamespace(summary={"samples": 0}),
    )
    monkeypatch.setattr(phase1, "run_data_quality_checks", lambda *args: {"status": "pass"})
    monkeypatch.setattr(phase1, "build_freshness_report", lambda *args: {"status": "fresh"})
    monkeypatch.setattr(phase1, "generate_phase1_report", lambda *args: calls.append("report"))

    phase1.main()

    assert calls == ["load_raw", "index", "report"]
    assert settings.paths.clean_csv.exists()
    assert settings.paths.clean_json.exists()


def test_corruption_flow_uses_same_testset_and_repairs_from_raw(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    clean = _clean_dataframe()
    settings.paths.clean_json.parent.mkdir(parents=True)
    clean.to_json(settings.paths.clean_json, orient="records", indent=2)
    write_json(settings.paths.raw_records_json, [])
    write_json(settings.paths.eval_testset, [{"id": "same-test-set"}])
    write_json(settings.paths.baseline_metrics, {"retrieval_hit_rate": 1.0})
    evaluated_testsets: list[Path] = []
    report_args = None
    report_kwargs = None

    monkeypatch.setattr(corruption_flow, "load_settings", lambda: settings)
    monkeypatch.setattr(corruption_flow, "corrupt_clean_dataframe", lambda df, path: df.copy())
    monkeypatch.setattr(corruption_flow, "load_raw_records", lambda path: [object()])
    monkeypatch.setattr(corruption_flow, "build_clean_dataframe", lambda records, run_date: clean.copy())
    monkeypatch.setattr(corruption_flow.LocalEmbeddingIndex, "build", lambda *args: object())

    def evaluate(_settings, index, test_set_path, metrics_path, answers_path):
        evaluated_testsets.append(test_set_path)
        return SimpleNamespace(summary={"retrieval_hit_rate": 0.5})

    monkeypatch.setattr(corruption_flow, "evaluate_pipeline", evaluate)
    monkeypatch.setattr(corruption_flow, "run_data_quality_checks", lambda df, settings, name: {"status": "pass", "checks": []})
    monkeypatch.setattr(corruption_flow, "build_freshness_report", lambda df, settings, path: {"status": "fresh"})

    def capture_report(*args, **kwargs):
        nonlocal report_args, report_kwargs
        report_args = args
        report_kwargs = kwargs

    monkeypatch.setattr(corruption_flow, "generate_corruption_report", capture_report)

    corruption_flow.main()

    assert evaluated_testsets == [settings.paths.eval_testset, settings.paths.eval_testset]
    assert settings.paths.corrupted_clean_csv.exists()
    assert settings.paths.repaired_clean_json.exists()
    assert report_args is not None
    assert len(report_args) == 8
    assert report_kwargs is not None
    assert set(report_kwargs) == {"baseline_quality", "baseline_freshness"}
    assert read_json(settings.paths.eval_testset) == [{"id": "same-test-set"}]
