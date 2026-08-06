from __future__ import annotations

import pandas as pd

from core.utils import normalize_whitespace, write_json


REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
}


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _question_basis(row: object) -> str:
    title_cue = " ".join(normalize_whitespace(str(row.title)).split()[:4])
    summary_cue = " ".join(normalize_whitespace(str(row.summary)).split()[:8])
    return f"{title_cue}; {summary_cue}"


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, object]]:
    """Build a reproducible semantic factual evaluation set from clean documents."""
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Clean dataframe is missing required columns: {sorted(missing)}")

    candidates = df[
        df["paper_id"].map(_valid_text)
        & df["title"].map(_valid_text)
        & df["summary"].map(_valid_text)
    ].sort_values(["published", "paper_id"], ascending=[False, True])
    if len(candidates) < 6:
        raise ValueError("At least 6 eligible documents are required to build the evaluation set.")

    test_set: list[dict[str, object]] = []
    specs = ("summary", "summary", "authors", "authors", "date", "date")
    used_ids: set[str] = set()
    for question_type in specs:
        eligible = candidates[~candidates["paper_id"].isin(used_ids)]
        if question_type == "authors":
            eligible = eligible[eligible["authors_joined"].map(_valid_text)]
        if eligible.empty:
            eligible = candidates
            if question_type == "authors":
                eligible = eligible[eligible["authors_joined"].map(_valid_text)]
        if eligible.empty:
            raise ValueError(f"The cleaned data cannot support {question_type} questions.")

        row = next(eligible.itertuples(index=False))
        paper_id = str(row.paper_id)
        basis = _question_basis(row)
        if question_type == "summary":
            question = f"Which paper discusses {basis}, and what is it about?"
            ground_truth = f"{str(row.title).strip()}: {normalize_whitespace(str(row.summary))}"
        elif question_type == "authors":
            question = f"Who authored the study described by {basis}?"
            ground_truth = str(row.authors_joined).strip()
        else:
            question = f"What is the publication date for the paper identified by {basis}?"
            ground_truth = str(row.published).strip()
        if not ground_truth:
            continue
        used_ids.add(paper_id)
        test_set.append(
            {
                "id": f"eval-{len(test_set) + 1:02d}-{question_type}",
                "question_type": question_type,
                "question": question,
                "question_basis": basis,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    write_json(output_path, test_set)
    return test_set
