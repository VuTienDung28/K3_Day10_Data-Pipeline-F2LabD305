from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json


REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "published",
    "age_days",
    "text_for_embedding",
}
MIN_TITLE_CHARS = 15
MIN_SUMMARY_CHARS = 100
NOISE_PATTERN = re.compile(
    r"\[corrupted[_ -]?noise\]|\bcorrupted[_ -]?noise\b|\blorem ipsum\b|\bnoise[_ -]?token\b|x{8,}",
    flags=re.IGNORECASE,
)


def _check(
    name: str,
    dimension: str,
    success: bool,
    observed: Any,
    expected: str,
    *,
    severity: str = "error",
    details: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "dimension": dimension,
        "severity": severity,
        "success": bool(success),
        "observed": observed,
        "expected": expected,
        "details": details or [],
    }


def _blank_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().eq("")


def _sample_ids(df: pd.DataFrame, mask: pd.Series, limit: int = 10) -> list[str]:
    if "paper_id" not in df.columns:
        return [str(index) for index in df.index[mask][:limit]]
    return df.loc[mask, "paper_id"].astype(str).head(limit).tolist()


def _quality_report_path(settings: Settings, report_name: str) -> Path:
    filename = report_name if report_name.lower().endswith(".json") else f"{report_name}.json"
    return settings.paths.quality_dir / filename


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run deterministic quality checks and persist an auditable JSON report.

    Error checks determine the overall status. Category completeness is recorded
    as a warning because Crossref frequently omits ``subject`` metadata.
    """
    total_rows = int(len(df))
    checks: list[dict[str, Any]] = []

    expected_rows = max(1, int(settings.max_results))
    checks.append(
        _check(
            "row_count",
            "volume",
            total_rows >= expected_rows,
            total_rows,
            f">= {expected_rows} rows",
        )
    )

    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    checks.append(
        _check(
            "required_columns",
            "schema",
            not missing_columns,
            missing_columns,
            f"all required columns present: {sorted(REQUIRED_COLUMNS)}",
        )
    )

    if "paper_id" in df.columns:
        blank_ids = _blank_mask(df["paper_id"])
        duplicate_ids = df["paper_id"].astype(str).str.strip().duplicated(keep=False) & ~blank_ids
        checks.extend(
            [
                _check(
                    "paper_id_not_null",
                    "completeness",
                    not blank_ids.any(),
                    int(blank_ids.sum()),
                    "0 blank paper_id values",
                    details=_sample_ids(df, blank_ids),
                ),
                _check(
                    "paper_id_unique",
                    "uniqueness",
                    not duplicate_ids.any(),
                    int(duplicate_ids.sum()),
                    "0 rows with duplicate paper_id",
                    details=_sample_ids(df, duplicate_ids),
                ),
            ]
        )

    if "title" in df.columns:
        blank_titles = _blank_mask(df["title"])
        short_titles = df["title"].fillna("").astype(str).str.strip().str.len().lt(MIN_TITLE_CHARS)
        checks.extend(
            [
                _check(
                    "title_not_null",
                    "completeness",
                    not blank_titles.any(),
                    int(blank_titles.sum()),
                    "0 blank titles",
                    details=_sample_ids(df, blank_titles),
                ),
                _check(
                    "title_min_length",
                    "validity",
                    not short_titles.any(),
                    int(short_titles.sum()),
                    f"0 titles shorter than {MIN_TITLE_CHARS} characters",
                    details=_sample_ids(df, short_titles),
                ),
            ]
        )

    if "summary" in df.columns:
        summaries = df["summary"].fillna("").astype(str).str.strip()
        blank_summaries = summaries.eq("")
        short_summaries = summaries.str.len().lt(MIN_SUMMARY_CHARS)
        noisy_summaries = summaries.str.contains(NOISE_PATTERN, na=False)
        checks.extend(
            [
                _check(
                    "summary_not_null",
                    "completeness",
                    not blank_summaries.any(),
                    int(blank_summaries.sum()),
                    "0 blank summaries",
                    details=_sample_ids(df, blank_summaries),
                ),
                _check(
                    "summary_min_length",
                    "validity",
                    not short_summaries.any(),
                    int(short_summaries.sum()),
                    f"0 summaries shorter than {MIN_SUMMARY_CHARS} characters",
                    details=_sample_ids(df, short_summaries),
                ),
                _check(
                    "summary_noise_markers",
                    "validity",
                    not noisy_summaries.any(),
                    int(noisy_summaries.sum()),
                    "0 summaries containing known corruption markers",
                    details=_sample_ids(df, noisy_summaries),
                ),
            ]
        )

    if "text_for_embedding" in df.columns:
        embedding_text = df["text_for_embedding"].fillna("").astype(str)
        blank_embedding_text = embedding_text.str.strip().eq("")
        checks.append(
            _check(
                "text_for_embedding_not_null",
                "completeness",
                not blank_embedding_text.any(),
                int(blank_embedding_text.sum()),
                "0 blank text_for_embedding values",
                details=_sample_ids(df, blank_embedding_text),
            )
        )
        if "title" in df.columns:
            titles = df["title"].fillna("").astype(str).str.strip()
            embedding_missing_title = pd.Series(
                [bool(title) and title not in text for title, text in zip(titles, embedding_text, strict=False)],
                index=df.index,
            )
            checks.append(
                _check(
                    "embedding_contains_title",
                    "consistency",
                    not embedding_missing_title.any(),
                    int(embedding_missing_title.sum()),
                    "0 embedding texts missing their current title",
                    details=_sample_ids(df, embedding_missing_title),
                )
            )
        if "summary" in df.columns:
            summaries = df["summary"].fillna("").astype(str).str.strip()
            embedding_missing_summary = pd.Series(
                [
                    bool(summary) and summary not in text
                    for summary, text in zip(summaries, embedding_text, strict=False)
                ],
                index=df.index,
            )
            checks.append(
                _check(
                    "embedding_contains_summary",
                    "consistency",
                    not embedding_missing_summary.any(),
                    int(embedding_missing_summary.sum()),
                    "0 embedding texts missing their current non-blank summary",
                    details=_sample_ids(df, embedding_missing_summary),
                )
            )

    published = None
    if "published" in df.columns:
        published = pd.to_datetime(df["published"], errors="coerce", utc=True)
        invalid_published = published.isna()
        checks.append(
            _check(
                "published_valid",
                "validity",
                not invalid_published.any(),
                int(invalid_published.sum()),
                "0 invalid publication dates",
                details=_sample_ids(df, invalid_published),
            )
        )

    if "age_days" in df.columns:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
        invalid_ages = ages.isna() | ages.lt(0)
        checks.append(
            _check(
                "age_days_valid",
                "validity",
                not invalid_ages.any(),
                int(invalid_ages.sum()),
                "0 missing or negative age_days values",
                details=_sample_ids(df, invalid_ages),
            )
        )

        stale_ages = ages.gt(settings.freshness_threshold_days).fillna(False)
        checks.append(
            _check(
                "freshness_threshold",
                "freshness",
                not stale_ages.any(),
                int(stale_ages.sum()),
                f"0 rows older than {settings.freshness_threshold_days} days",
                details=_sample_ids(df, stale_ages),
            )
        )

        if published is not None:
            today = pd.Timestamp(now_utc()).normalize()
            computed_ages = (today - published.dt.normalize()).dt.days
            comparable = ages.notna() & computed_ages.notna()
            inconsistent = comparable & ages.sub(computed_ages).abs().gt(1)
            checks.append(
                _check(
                    "age_days_consistent_with_published",
                    "consistency",
                    not inconsistent.any(),
                    int(inconsistent.sum()),
                    "0 rows where age_days differs from published by more than 1 day",
                    details=_sample_ids(df, inconsistent),
                )
            )

    if "categories_joined" in df.columns:
        blank_categories = _blank_mask(df["categories_joined"])
        checks.append(
            _check(
                "categories_not_null",
                "completeness",
                not blank_categories.any(),
                int(blank_categories.sum()),
                "0 blank categories_joined values",
                severity="warning",
                details=_sample_ids(df, blank_categories),
            )
        )

    failed_error_checks = [
        item for item in checks if item["severity"] == "error" and not item["success"]
    ]
    failed_warning_checks = [
        item for item in checks if item["severity"] == "warning" and not item["success"]
    ]
    payload = {
        "report_name": report_name.removesuffix(".json"),
        "generated_at": now_utc().isoformat(),
        "status": "pass" if not failed_error_checks else "fail",
        "success": not failed_error_checks,
        "total_rows": total_rows,
        "passed_checks": sum(1 for item in checks if item["success"]),
        "failed_checks": len(failed_error_checks),
        "warning_checks": len(failed_warning_checks),
        "checks": checks,
    }
    write_json(_quality_report_path(settings, report_name), payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Build freshness from publication dates instead of trusting ``age_days``."""
    total_rows = int(len(df))
    generated_at = now_utc()
    threshold = int(settings.freshness_threshold_days)

    if "published" in df.columns:
        published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    else:
        published = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")

    valid_dates = published.dropna()
    ages = (pd.Timestamp(generated_at).normalize() - published.dt.normalize()).dt.days
    stale_mask = ages.gt(threshold).fillna(False)
    future_mask = ages.lt(0).fillna(False)
    invalid_dates = int(published.isna().sum())
    stale_rows = int(stale_mask.sum())
    future_rows = int(future_mask.sum())
    is_fresh = total_rows > 0 and invalid_dates == 0 and stale_rows == 0 and future_rows == 0

    stale_ids = _sample_ids(df, stale_mask) if total_rows else []
    payload = {
        "generated_at": generated_at.isoformat(),
        "status": "fresh" if is_fresh else "unknown" if total_rows == 0 or not len(valid_dates) else "stale",
        "latest_published": valid_dates.max().date().isoformat() if len(valid_dates) else None,
        "oldest_published": valid_dates.min().date().isoformat() if len(valid_dates) else None,
        "stale_rows": stale_rows,
        "stale_paper_ids": stale_ids,
        "future_rows": future_rows,
        "invalid_date_rows": invalid_dates,
        "total_rows": total_rows,
        "freshness_threshold_days": threshold,
        "max_age_days": int(ages.max()) if ages.notna().any() else None,
        "mean_age_days": round(float(ages.mean()), 2) if ages.notna().any() else None,
        "is_fresh": is_fresh,
    }
    write_json(Path(report_path), payload)
    return payload
