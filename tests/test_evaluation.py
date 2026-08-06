from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from evaluation import metrics
from evaluation.testset import build_test_set


def _settings(tmp_path: Path):
    settings = load_settings(tmp_path)
    return replace(settings, llm_provider="openrouter", model_name="openai/o4-mini")


def _clean_dataframe(row_count: int = 8) -> pd.DataFrame:
    rows = []
    for index in range(row_count):
        title = f"Distinctive Research Topic {index} for Reliable Data Systems"
        summary = (
            f"Unique concept {index} studies resilient scholarly retrieval with signal token-{index}. "
            "The method evaluates factual grounding, reproducible indexing, and observable data repair."
        )
        rows.append(
            {
                "paper_id": f"10.1234/paper-{index}",
                "title": title,
                "summary": summary,
                "authors_joined": f"Author {index}",
                "categories_joined": "data systems",
                "published": f"2026-07-{index + 1:02d}",
            }
        )
    return pd.DataFrame(rows)


def test_testset_has_six_semantic_questions_without_exact_titles(tmp_path: Path) -> None:
    clean = _clean_dataframe()

    test_set = build_test_set(clean, tmp_path / "test_set.json")

    assert len(test_set) == 6
    assert {item["question_type"] for item in test_set} == {"summary", "authors", "date"}
    assert all(len(item["ground_truth_doc_ids"]) == 1 for item in test_set)
    titles = clean.set_index("paper_id")["title"].to_dict()
    assert all(titles[item["ground_truth_doc_ids"][0]] not in item["question"] for item in test_set)
    assert all(item["question_basis"] in item["question"] for item in test_set)
    assert all(
        " ".join(titles[item["ground_truth_doc_ids"][0]].split()[:4]) in item["question_basis"]
        for item in test_set
    )
    summaries = [item for item in test_set if item["question_type"] == "summary"]
    assert all(titles[item["ground_truth_doc_ids"][0]] in item["ground_truth"] for item in summaries)
    assert all(
        clean.set_index("paper_id").loc[item["ground_truth_doc_ids"][0], "summary"] in item["ground_truth"]
        for item in summaries
    )
    assert read_json(tmp_path / "test_set.json") == test_set


def test_judge_fallback_is_structured_and_countable(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(metrics, "build_llm", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    judged = metrics._judge_answer(settings, "question", "correct answer", "correct answer")

    assert judged.verdict.score == 5
    assert judged.provenance == {
        "provider": "openrouter",
        "model": "openai/o4-mini",
        "used_fallback": True,
        "fallback_reason": "RuntimeError",
    }


def test_ragas_imports_are_compatible_with_installed_langchain() -> None:
    evaluate, wrapper, ragas_metrics = metrics._ragas_components()

    assert callable(evaluate)
    assert wrapper.__name__ == "LangchainLLMWrapper"
    assert len(ragas_metrics) == 4


def test_ragas_result_is_normalized_and_rejects_nan(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    result = SimpleNamespace(
        scores=[
            {
                "answer_relevancy": 0.8,
                "context_precision": 0.7,
                "context_recall": 0.9,
                "faithfulness": 1.0,
            },
            {
                "answer_relevancy": 1.0,
                "context_precision": 0.9,
                "context_recall": 0.7,
                "faithfulness": 0.8,
            },
        ]
    )

    normalized = metrics._normalize_ragas_result(settings, result)

    assert normalized["status"] == "passed"
    assert normalized["samples"] == 2
    assert normalized["metrics"] == {
        "answer_relevancy": 0.9,
        "context_precision": 0.8,
        "context_recall": 0.8,
        "faithfulness": 0.9,
    }
    result.scores[0]["faithfulness"] = math.nan
    failed = metrics._normalize_ragas_result(settings, result)
    assert failed["status"] == "failed"
    assert failed["reason"] == "Ragas returned a non-finite faithfulness score."


def test_agent_evaluation_records_tools_provenance_and_fallback_count(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    test_set_path = tmp_path / "test_set.json"
    test_set = [
        {
            "id": "eval-01-summary",
            "question_type": "summary",
            "question": "What is the study using unique semantic evidence about?",
            "question_basis": "unique semantic evidence",
            "ground_truth": "grounded answer",
            "ground_truth_doc_ids": ["10.1234/paper"],
        }
    ]
    from core.utils import write_json

    write_json(test_set_path, test_set)

    class FakeAgent:
        def __init__(self, trace):
            self.trace = trace

        def invoke(self, payload):
            self.trace.append(
                {
                    "tool": "semantic_search_papers",
                    "arguments": {"query": payload["messages"][0]["content"], "top_k": 4},
                    "retrieved_doc_ids": ["10.1234/paper"],
                    "retrieved_titles": ["Paper"],
                    "retrieved_contexts": ["Context"],
                }
            )
            return {"messages": [SimpleNamespace(content="grounded answer")]}

    monkeypatch.setattr(metrics, "build_agent", lambda settings, index, trace: FakeAgent(trace))
    monkeypatch.setattr(
        metrics,
        "_judge_answer",
        lambda *args: metrics.JudgeResult(
            verdict=metrics.JudgeVerdict(score=5, correct=True, reasoning="LLM verified"),
            provenance={
                "provider": "openrouter",
                "model": "openai/o4-mini",
                "used_fallback": False,
                "fallback_reason": None,
            },
        ),
    )
    monkeypatch.setattr(metrics, "_run_ragas", lambda *args: {"status": "skipped"})

    bundle = metrics.evaluate_agent_pipeline(
        settings,
        object(),
        test_set_path,
        tmp_path / "metrics.json",
        tmp_path / "answers.json",
    )

    assert bundle.summary["evaluation_mode"] == "agent"
    assert bundle.summary["judge_calls"] == 1
    assert bundle.summary["fallback_count"] == 0
    assert bundle.summary["test_set_sha256"]
    assert bundle.answers[0]["agent_trace"][0]["tool"] == "semantic_search_papers"
    assert bundle.answers[0]["retrieval_hit"] is True
