from __future__ import annotations

from datetime import UTC, datetime
import html
import re
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


_CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "age_days",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "text_for_embedding",
    "abs_url",
    "pdf_url",
    "comment",
]


def _clean_text(value: Any) -> str:
    """Normalize text and remove markup that may remain in source snapshots."""
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_whitespace(text)


def _clean_string_list(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            # Crossref authors are commonly shaped as
            # {"given": "Ada", "family": "Lovelace"}.
            cleaned = _clean_text(" ".join([str(value.get("given", "")), str(value.get("family", ""))]))
            if not cleaned:
                cleaned = _clean_text(value.get("name", ""))
        else:
            cleaned = _clean_text(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _parse_date(value: Any) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a deterministic dataframe ready for indexing."""
    if run_date.tzinfo is None:
        effective_run_date = run_date.replace(tzinfo=UTC)
    else:
        effective_run_date = run_date.astimezone(UTC)
    run_day = pd.Timestamp(effective_run_date).normalize()

    rows: list[dict[str, Any]] = []
    for record in records:
        paper_id = _clean_text(record.paper_id).lower()
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        if not paper_id or not title or len(summary) < 100:
            continue

        published_ts = _parse_date(record.published)
        if published_ts is None:
            continue
        updated_ts = _parse_date(record.updated) or published_ts
        age_days = max(0, int((run_day - published_ts.normalize()).days))

        authors = _clean_string_list(record.authors)
        categories = _clean_string_list(record.categories)
        primary_category = _clean_text(record.primary_category)
        if primary_category and primary_category.casefold() not in {item.casefold() for item in categories}:
            categories.insert(0, primary_category)
        if not primary_category and categories:
            primary_category = categories[0]

        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        text_for_embedding = (
            f"Title: {title} | Authors: {authors_joined} | Summary: {summary}"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published_ts.date().isoformat(),
                "updated": updated_ts.date().isoformat(),
                "age_days": age_days,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "text_for_embedding": text_for_embedding,
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
            }
        )

    if not rows:
        return pd.DataFrame(columns=_CLEAN_COLUMNS)

    df = pd.DataFrame(rows, columns=_CLEAN_COLUMNS)
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    return df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
