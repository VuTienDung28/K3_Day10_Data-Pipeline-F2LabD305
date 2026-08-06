from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ingestion.corruption import NOISE_MARKER, corrupt_clean_dataframe


def _clean_dataframe(row_count: int = 20) -> pd.DataFrame:
    today = pd.Timestamp.now(tz="UTC").normalize()
    rows = []
    for index in range(row_count):
        title = f"A descriptive paper title number {index:02d}"
        summary = (
            f"Summary for paper {index:02d}. "
            "This abstract has enough detail to satisfy the clean data contract "
            "and support a meaningful retrieval evaluation before corruption."
        )
        rows.append(
            {
                "paper_id": f"10.1234/paper-{index:02d}",
                "title": title,
                "summary": summary,
                "published": (today - pd.Timedelta(days=index)).date().isoformat(),
                "age_days": index,
                "authors_joined": f"Author {index}",
                "categories_joined": "computer science",
                "text_for_embedding": (
                    f"Title: {title} | Authors: Author {index} | Summary: {summary}"
                ),
            }
        )
    return pd.DataFrame(rows)


def test_corruption_is_reproducible_auditable_and_does_not_mutate_input(tmp_path: Path) -> None:
    clean = _clean_dataframe()
    original = clean.copy(deep=True)
    first_log = tmp_path / "first.json"
    second_log = tmp_path / "second.json"

    first = corrupt_clean_dataframe(clean, first_log)
    second = corrupt_clean_dataframe(clean, second_log)

    pd.testing.assert_frame_equal(clean, original)
    pd.testing.assert_frame_equal(first, second)

    assert first["paper_id"].duplicated(keep=False).any()
    assert first["summary"].eq("").any()
    assert first["summary"].str.contains(NOISE_MARKER, regex=False).any()
    assert first["title"].str.len().lt(15).any()
    assert pd.to_numeric(first["age_days"]).gt(3650).any()
    assert all(
        title in text and summary in text
        for title, summary, text in zip(
            first["title"], first["summary"], first["text_for_embedding"], strict=False
        )
    )

    log = json.loads(first_log.read_text(encoding="utf-8"))
    assert log["input_rows"] == 20
    assert log["event_count"] == sum(log["counts_by_type"].values())
    assert set(log["counts_by_type"]) == {
        "drop_latest_record",
        "blank_summary",
        "inject_summary_noise",
        "truncate_title",
        "stale_published_date",
        "duplicate_record",
    }


def test_corruption_rejects_data_outside_clean_contract(tmp_path: Path) -> None:
    malformed = pd.DataFrame([{"paper_id": "10.1234/incomplete"}])

    try:
        corrupt_clean_dataframe(malformed, tmp_path / "log.json")
    except ValueError as exc:
        assert "required clean-schema columns are missing" in str(exc)
        assert "summary" in str(exc)
    else:
        raise AssertionError("Expected a clear schema validation error")
