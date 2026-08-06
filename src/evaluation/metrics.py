from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import os
from pathlib import Path
from statistics import mean
from typing import Any

from datasets import Dataset
from pydantic import BaseModel, Field

from core.config import Settings, normalized_provider
from core.utils import normalize_whitespace, read_json, write_json
from retrieval.agent import build_agent, run_agent_question
from retrieval.embeddings import MiniLMEmbeddings
from retrieval.index import LocalEmbeddingIndex
from retrieval.llm import build_llm
from retrieval.qa import answer_question


RAGAS_METRICS = (
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "faithfulness",
)


class JudgeVerdict(BaseModel):
    score: int = Field(ge=1, le=5)
    correct: bool
    reasoning: str


@dataclass(frozen=True)
class JudgeResult:
    verdict: JudgeVerdict
    provenance: dict[str, Any]


@dataclass(frozen=True)
class EvaluationBundle:
    summary: dict[str, Any]
    answers: list[dict[str, Any]]


def _token_f1(reference: str, prediction: str) -> float:
    ref_tokens = normalize_whitespace(reference).lower().split()
    pred_tokens = normalize_whitespace(prediction).lower().split()
    if not ref_tokens or not pred_tokens:
        return 0.0
    ref_set = set(ref_tokens)
    pred_set = set(pred_tokens)
    overlap = len(ref_set & pred_set)
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_set)
    recall = overlap / len(ref_set)
    return 2 * precision * recall / (precision + recall)


def _judge_answer(
    settings: Settings,
    question: str,
    reference: str,
    prediction: str,
) -> JudgeResult:
    prompt = f"""
Evaluate the model answer against the reference answer.

Question: {question}
Reference answer: {reference}
Model answer: {prediction}

Return:
- score from 1 to 5
- correct = true only when the answer is materially correct
- short reasoning
""".strip()
    provider = normalized_provider(settings)
    provenance = {
        "provider": provider,
        "model": settings.model_name,
        "used_fallback": False,
        "fallback_reason": None,
    }
    try:
        llm = build_llm(settings=settings, temperature=0.0).with_structured_output(JudgeVerdict)
        verdict = llm.invoke(prompt)
    except Exception as exc:
        score = 5 if _token_f1(reference, prediction) >= 0.95 else 3 if _token_f1(reference, prediction) >= 0.5 else 1
        verdict = JudgeVerdict(
            score=score,
            correct=score >= 3,
            reasoning="Fallback heuristic judge used because the LLM evaluator was unavailable.",
        )
        provenance["used_fallback"] = True
        provenance["fallback_reason"] = type(exc).__name__
    return JudgeResult(verdict=verdict, provenance=provenance)


def _normalize_ragas_result(settings: Settings, result: Any) -> dict[str, Any]:
    scores = list(result.scores)
    envelope: dict[str, Any] = {
        "status": "passed",
        "provider": normalized_provider(settings),
        "model": settings.model_name,
        "embedding_model": settings.embedding_model,
        "samples": len(scores),
    }
    if not scores:
        return envelope | {"status": "failed", "reason": "Ragas returned no sample scores."}

    metrics: dict[str, float] = {}
    for name in RAGAS_METRICS:
        values = [row.get(name) for row in scores]
        if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
            return envelope | {"status": "failed", "reason": f"Ragas returned a non-finite {name} score."}
        metrics[name] = mean(float(value) for value in values)
    envelope["metrics"] = metrics
    return envelope


def _ragas_components():
    import sys
    import types

    try:
        from langchain_community.chat_models.vertexai import ChatVertexAI
    except ModuleNotFoundError:
        vertexai = types.ModuleType("langchain_community.chat_models.vertexai")
        vertexai.ChatVertexAI = type("ChatVertexAI", (), {})
        sys.modules[vertexai.__name__] = vertexai

    import langchain_community.llms as community_llms

    if not hasattr(community_llms, "VertexAI"):
        community_llms.VertexAI = type("VertexAI", (), {})

    from ragas import evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    return evaluate, LangchainLLMWrapper, (answer_relevancy, context_precision, context_recall, faithfulness)


def _run_ragas(settings: Settings, answers: list[dict[str, Any]]) -> dict[str, Any]:
    provenance = {
        "provider": normalized_provider(settings),
        "model": settings.model_name,
        "embedding_model": settings.embedding_model,
    }
    if os.getenv("RUN_RAGAS", "").lower() not in {"1", "true", "yes"}:
        return provenance | {"status": "skipped", "reason": "Set RUN_RAGAS=1 to enable the slower Ragas pass."}
    try:
        evaluate, wrapper, ragas_metrics = _ragas_components()
        dataset = Dataset.from_dict(
            {
                "question": [item["question"] for item in answers],
                "answer": [item["answer"] for item in answers],
                "ground_truth": [item["ground_truth"] for item in answers],
                "contexts": [item["retrieved_contexts"] for item in answers],
            }
        )
        result = evaluate(
            dataset,
            metrics=list(ragas_metrics),
            llm=wrapper(
                build_llm(settings=settings, temperature=0.0),
                bypass_temperature=True,
                bypass_n=True,
            ),
            embeddings=MiniLMEmbeddings(settings.embedding_model),
        )
        return _normalize_ragas_result(settings, result)
    except Exception as exc:  # pragma: no cover
        return provenance | {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}


def _test_set_sha256(test_set_path: Path) -> str:
    return sha256(test_set_path.read_bytes()).hexdigest()


def _summarize(
    settings: Settings,
    answers: list[dict[str, Any]],
    test_set_path: Path,
    evaluation_mode: str,
    ragas: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "evaluation_mode": evaluation_mode,
        "samples": len(answers),
        "test_set_sha256": _test_set_sha256(test_set_path),
        "retrieval_hit_rate": mean(1.0 if item["retrieval_hit"] else 0.0 for item in answers),
        "mean_token_f1": mean(item["token_f1"] for item in answers),
        "judge_accuracy": mean(1.0 if item["judge"]["correct"] else 0.0 for item in answers),
        "mean_judge_score": mean(item["judge"]["score"] for item in answers),
        "judge_provider": normalized_provider(settings),
        "judge_model": settings.model_name,
        "judge_calls": len(answers),
        "fallback_count": sum(bool(item["judge_provenance"]["used_fallback"]) for item in answers),
        "ragas": ragas,
    }


def _answer_record(item: dict[str, Any], answer: str, retrieved_ids: list[str], contexts: list[str], judged: JudgeResult) -> dict[str, Any]:
    return {
        "id": item["id"],
        "question_type": item["question_type"],
        "question": item["question"],
        "question_basis": item.get("question_basis"),
        "ground_truth": item["ground_truth"],
        "ground_truth_doc_ids": item["ground_truth_doc_ids"],
        "answer": answer,
        "retrieved_doc_ids": retrieved_ids,
        "retrieved_contexts": contexts,
        "retrieval_hit": any(doc_id in item["ground_truth_doc_ids"] for doc_id in retrieved_ids),
        "token_f1": _token_f1(item["ground_truth"], answer),
        "judge": judged.verdict.model_dump(),
        "judge_provenance": judged.provenance,
    }


def evaluate_pipeline(
    settings: Settings,
    index: LocalEmbeddingIndex,
    test_set_path,
    metrics_output_path,
    answers_output_path,
) -> EvaluationBundle:
    path = Path(test_set_path)
    answers: list[dict[str, Any]] = []
    for item in read_json(path):
        result = answer_question(item["question"], settings=settings, index=index)
        judged = _judge_answer(settings, item["question"], item["ground_truth"], result.answer)
        answers.append(_answer_record(item, result.answer, result.retrieved_doc_ids, result.retrieved_contexts, judged))
    summary = _summarize(settings, answers, path, "deterministic", {"status": "not_run_for_reference_mode"})
    bundle = EvaluationBundle(summary=summary, answers=answers)
    write_json(Path(metrics_output_path), summary)
    write_json(Path(answers_output_path), answers)
    return bundle


def evaluate_agent_pipeline(
    settings: Settings,
    index: LocalEmbeddingIndex,
    test_set_path,
    metrics_output_path,
    answers_output_path,
) -> EvaluationBundle:
    path = Path(test_set_path)
    trace: list[dict[str, Any]] = []
    agent = build_agent(settings, index, trace)
    answers: list[dict[str, Any]] = []
    for item in read_json(path):
        trace_start = len(trace)
        answer = run_agent_question(agent, item["question"])
        item_trace = trace[trace_start:]
        retrieved_ids = list(dict.fromkeys(doc_id for call in item_trace for doc_id in call["retrieved_doc_ids"]))
        contexts = list(dict.fromkeys(context for call in item_trace for context in call["retrieved_contexts"]))
        judged = _judge_answer(settings, item["question"], item["ground_truth"], answer)
        record = _answer_record(item, answer, retrieved_ids, contexts, judged)
        record["agent_trace"] = item_trace
        answers.append(record)
    ragas = _run_ragas(settings, answers)
    summary = _summarize(settings, answers, path, "agent", ragas)
    bundle = EvaluationBundle(summary=summary, answers=answers)
    write_json(Path(metrics_output_path), summary)
    write_json(Path(answers_output_path), answers)
    return bundle
