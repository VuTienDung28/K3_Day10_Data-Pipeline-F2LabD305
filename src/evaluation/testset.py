from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
}


def _valid_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a reproducible factual evaluation set from cleaned documents."""
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Clean dataframe is missing required columns: {sorted(missing)}")
    if len(df) < 4:
        raise ValueError("At least 4 cleaned documents are required to build the evaluation set.")

    candidates = df.copy()
    candidates = candidates[
        candidates["paper_id"].map(_valid_text)
        & candidates["title"].map(_valid_text)
        & candidates["summary"].map(_valid_text)
    ]
    # qa.answer_question recognizes titles surrounded by single quotes. Avoid
    # ambiguous questions for the uncommon case where the title itself has one.
    candidates = candidates[~candidates["title"].str.contains("'", regex=False)]
    candidates = candidates.sort_values(["published", "paper_id"], ascending=[False, True])
    if len(candidates) < 4:
        raise ValueError("At least 4 eligible documents are required to build the evaluation set.")

    question_specs = [
        (
            "summary",
            lambda row: f"What is the paper '{row.title}' about?",
            lambda row: first_sentence(row.summary),
        ),
        (
            "authors",
            lambda row: f"Who authored the paper '{row.title}'?",
            lambda row: row.authors_joined,
        ),
        (
            "date",
            lambda row: f"When was the paper '{row.title}' published?",
            lambda row: row.published,
        ),
        (
            "categories",
            lambda row: f"What categories are listed for the paper '{row.title}'?",
            lambda row: row.categories_joined,
        ),
    ]

    test_set: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for question_type, question_builder, answer_builder in question_specs:
        answer_column = "authors_joined" if question_type == "authors" else "categories_joined"
        eligible = candidates
        if question_type in {"authors", "categories"}:
            eligible = eligible[eligible[answer_column].map(_valid_text)]
        eligible = eligible[~eligible["paper_id"].isin(used_ids)]
        if eligible.empty:
            # Reusing a document is preferable to omitting an evaluation type.
            eligible = candidates
            if question_type in {"authors", "categories"}:
                eligible = eligible[eligible[answer_column].map(_valid_text)]
        if eligible.empty:
            continue

        row = next(eligible.itertuples(index=False))
        ground_truth = str(answer_builder(row)).strip()
        if not ground_truth:
            continue
        paper_id = str(row.paper_id)
        used_ids.add(paper_id)
        test_set.append(
            {
                "id": f"eval-{len(test_set) + 1:02d}-{question_type}",
                "question_type": question_type,
                "question": question_builder(row),
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    required_types = {"summary", "authors", "date"}
    actual_types = {item["question_type"] for item in test_set}
    if not required_types.issubset(actual_types):
        raise ValueError("The cleaned data cannot support summary, authors, and date questions.")

    write_json(output_path, test_set)
    return test_set
