from __future__ import annotations

from datetime import UTC, datetime
import math
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json


CORRUPTION_SEED = 42
CORRUPTION_RATE = 0.10
STALE_SHIFT_DAYS = 3650
NOISE_MARKER = "[CORRUPTED_NOISE] noise_token"

_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "published",
    "age_days",
    "authors_joined",
    "text_for_embedding",
}


def _sample_size(row_count: int) -> int:
    """Return a visible but bounded number of rows to corrupt."""
    if row_count <= 0:
        return 0
    return max(1, math.ceil(row_count * CORRUPTION_RATE))


def _preview(value: Any, limit: int = 180) -> Any:
    """Keep the audit log readable without losing useful before/after evidence."""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}..."


def _paper_id(df: pd.DataFrame, index: Any) -> str:
    return str(df.at[index, "paper_id"])


def _event(
    corruption_type: str,
    paper_id: str,
    field: str,
    before: Any,
    after: Any,
) -> dict[str, Any]:
    return {
        "corruption_type": corruption_type,
        "paper_id": paper_id,
        "field": field,
        "before": _preview(before),
        "after": _preview(after),
    }


def _rebuild_embedding_text(df: pd.DataFrame) -> None:
    """Rebuild the derived field using the same contract as cleaning.py."""
    titles = df["title"].fillna("").astype(str)
    authors = df["authors_joined"].fillna("").astype(str)
    summaries = df["summary"].fillna("").astype(str)
    df["text_for_embedding"] = [
        f"Title: {title} | Authors: {author} | Summary: {summary}"
        for title, author, summary in zip(titles, authors, summaries, strict=False)
    ]


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Create a deterministic, auditable corrupted copy of a clean dataframe.

    The input dataframe is never modified. Six realistic failure modes are
    introduced: missing newest records, blank summaries, noisy summaries,
    truncated titles, stale publication dates, and duplicate records. The
    derived embedding text is rebuilt after mutation so the corrupted artifact
    remains internally usable by the retrieval pipeline.
    """
    missing_columns = sorted(_REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(
            "Cannot corrupt dataframe because required clean-schema columns are missing: "
            + ", ".join(missing_columns)
        )

    corrupted = df.copy(deep=True)
    events: list[dict[str, Any]] = []
    input_rows = int(len(corrupted))

    if input_rows:
        # Scenario 1: an incomplete incremental load loses the newest records.
        published = pd.to_datetime(corrupted["published"], errors="coerce", utc=True)
        newest_order = (
            pd.DataFrame(
                {
                    "published": published,
                    "paper_id": corrupted["paper_id"].astype(str),
                },
                index=corrupted.index,
            )
            .sort_values(
                ["published", "paper_id"],
                ascending=[False, True],
                na_position="last",
                kind="stable",
            )
            .index.tolist()
        )
        drop_count = min(_sample_size(input_rows), max(0, input_rows - 1))
        drop_indices = newest_order[:drop_count]
        for index in drop_indices:
            events.append(
                _event(
                    "drop_latest_record",
                    _paper_id(corrupted, index),
                    "row",
                    "present",
                    "dropped",
                )
            )
        corrupted = corrupted.drop(index=drop_indices)

    if len(corrupted):
        # A fixed random order prevents bias toward adjacent source rows and
        # guarantees reproducible artifacts for demos and grading.
        candidates = corrupted.sample(frac=1, random_state=CORRUPTION_SEED).index.tolist()
        mutation_count = _sample_size(len(corrupted))

        def selected(offset: int) -> list[Any]:
            return [candidates[(offset + position) % len(candidates)] for position in range(mutation_count)]

        blank_indices = selected(0)
        noise_indices = selected(mutation_count)
        title_indices = selected(mutation_count * 2)
        stale_indices = selected(mutation_count * 3)
        duplicate_indices = selected(mutation_count * 4)

        # Scenario 2: an upstream mapping bug drops abstracts.
        for index in blank_indices:
            before = corrupted.at[index, "summary"]
            corrupted.at[index, "summary"] = ""
            events.append(
                _event("blank_summary", _paper_id(corrupted, index), "summary", before, "")
            )

        # Scenario 3: scraping/encoding noise leaks into otherwise valid text.
        for index in noise_indices:
            before = str(corrupted.at[index, "summary"] or "")
            after = f"{before} {NOISE_MARKER}".strip()
            corrupted.at[index, "summary"] = after
            events.append(
                _event("inject_summary_noise", _paper_id(corrupted, index), "summary", before, after)
            )

        # Scenario 4: a bad field-width limit truncates titles below 15 chars.
        for index in title_indices:
            before = str(corrupted.at[index, "title"] or "")
            after = before[:8]
            corrupted.at[index, "title"] = after
            events.append(
                _event("truncate_title", _paper_id(corrupted, index), "title", before, after)
            )

        # Scenario 5: a date conversion error shifts publication by ten years.
        today = pd.Timestamp(datetime.now(UTC)).normalize()
        for index in stale_indices:
            before = corrupted.at[index, "published"]
            parsed = pd.to_datetime(before, errors="coerce", utc=True)
            stale_date = (
                parsed - pd.Timedelta(days=STALE_SHIFT_DAYS)
                if not pd.isna(parsed)
                else today - pd.Timedelta(days=STALE_SHIFT_DAYS)
            )
            after = stale_date.date().isoformat()
            corrupted.at[index, "published"] = after
            corrupted.at[index, "age_days"] = max(
                0, int((today - stale_date.normalize()).days)
            )
            events.append(
                _event("stale_published_date", _paper_id(corrupted, index), "published", before, after)
            )

        # Scenario 6: an at-least-once load inserts the same records twice.
        duplicate_rows = corrupted.loc[duplicate_indices].copy(deep=True)
        for index in duplicate_indices:
            events.append(
                _event(
                    "duplicate_record",
                    _paper_id(corrupted, index),
                    "paper_id",
                    "1 occurrence",
                    "2 occurrences",
                )
            )
        corrupted = pd.concat([corrupted, duplicate_rows], ignore_index=True)

    _rebuild_embedding_text(corrupted)
    if "summary_chars" in corrupted.columns:
        corrupted["summary_chars"] = corrupted["summary"].fillna("").astype(str).str.len()
    corrupted = corrupted.reset_index(drop=True)

    counts: dict[str, int] = {}
    for item in events:
        corruption_type = item["corruption_type"]
        counts[corruption_type] = counts.get(corruption_type, 0) + 1

    log_payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "seed": CORRUPTION_SEED,
        "corruption_rate": CORRUPTION_RATE,
        "input_rows": input_rows,
        "output_rows": int(len(corrupted)),
        "event_count": len(events),
        "counts_by_type": counts,
        "events": events,
    }
    write_json(Path(output_log_path), log_payload)
    return corrupted
