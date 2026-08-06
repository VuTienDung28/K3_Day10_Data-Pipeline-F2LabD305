from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


CROSSREF_API_URL = "https://api.crossref.org/works"
RETRY_STATUS_CODES = {429, 503}
MAX_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return normalize_whitespace(item)
        return ""
    if isinstance(value, str):
        return normalize_whitespace(value)
    return ""


def _clean_crossref_markup(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return normalize_whitespace(text)


def _date_parts_to_iso(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    date_parts = value.get("date-parts")
    if not date_parts or not isinstance(date_parts, list) or not date_parts[0]:
        return ""

    parts = [int(part) for part in date_parts[0] if isinstance(part, int)]
    if not parts:
        return ""

    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _best_date(item: dict, keys: list[str]) -> str:
    for key in keys:
        parsed = _date_parts_to_iso(item.get(key))
        if parsed:
            return parsed
    return ""


def _authors(item: dict) -> list[str]:
    authors: list[str] = []
    for author in item.get("author") or []:
        if not isinstance(author, dict):
            continue
        name = normalize_whitespace(" ".join([author.get("given", ""), author.get("family", "")]))
        if name:
            authors.append(name)
    return authors


def _subjects(item: dict) -> list[str]:
    return [normalize_whitespace(subject) for subject in item.get("subject", []) if isinstance(subject, str)]


def _pdf_url(item: dict) -> str:
    for link in item.get("link") or []:
        if not isinstance(link, dict):
            continue
        url = link.get("URL", "")
        content_type = link.get("content-type", "")
        if isinstance(url, str) and isinstance(content_type, str) and "pdf" in content_type.lower():
            return url
    return ""


def _paper_id(item: dict, index: int) -> str:
    doi = normalize_whitespace(item.get("DOI", "")) if isinstance(item.get("DOI"), str) else ""
    url = normalize_whitespace(item.get("URL", "")) if isinstance(item.get("URL"), str) else ""
    if doi:
        return doi
    if url:
        return url
    return f"crossref-record-{index + 1}"


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        title = _first_text(item.get("title"))
        raw_summary = _first_text(item.get("abstract")) or _first_text(item.get("description"))
        summary = _clean_crossref_markup(raw_summary)
        if not title or not summary:
            continue

        doi = normalize_whitespace(item.get("DOI", "")) if isinstance(item.get("DOI"), str) else ""
        url = normalize_whitespace(item.get("URL", "")) if isinstance(item.get("URL"), str) else ""
        subjects = _subjects(item)
        comment_parts = [
            f"publisher={item.get('publisher')}" if item.get("publisher") else "",
            f"type={item.get('type')}" if item.get("type") else "",
        ]

        records.append(
            PaperRecord(
                paper_id=_paper_id(item, index),
                title=title,
                summary=summary,
                authors=_authors(item),
                categories=subjects,
                primary_category=subjects[0] if subjects else "",
                published=_best_date(item, ["published-print", "published-online", "published", "issued", "created"]),
                updated=_best_date(item, ["indexed", "deposited", "updated-by"]),
                abs_url=url or (f"https://doi.org/{doi}" if doi else ""),
                pdf_url=_pdf_url(item),
                comment=normalize_whitespace(" | ".join(part for part in comment_parts if part)),
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi Crossref API, luu raw response, parse thanh records."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {
        "User-Agent": "day10-data-observability-lab/0.1 (mailto:student@example.com)",
    }

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(
                CROSSREF_API_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES:
                retry_after = response.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(delay)
                continue

            response.raise_for_status()
            payload = response.json()
            write_json(settings.paths.raw_api_response, payload)

            records = parse_crossref_payload(payload)
            write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
            return records
        except requests.HTTPError as exc:
            last_error = exc
            break
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                break
            time.sleep(2**attempt)

    raise RuntimeError(f"Failed to fetch Crossref records after {MAX_RETRIES + 1} attempts.") from last_error


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    payload = read_json(path)
    records: list[PaperRecord] = []

    for item in payload:
        records.append(
            PaperRecord(
                paper_id=str(item.get("paper_id", "")),
                title=str(item.get("title", "")),
                summary=str(item.get("summary", "")),
                authors=list(item.get("authors") or []),
                categories=list(item.get("categories") or []),
                primary_category=str(item.get("primary_category", "")),
                published=str(item.get("published", "")),
                updated=str(item.get("updated", "")),
                abs_url=str(item.get("abs_url", "")),
                pdf_url=str(item.get("pdf_url", "")),
                comment=str(item.get("comment", "")),
            )
        )

    return records
