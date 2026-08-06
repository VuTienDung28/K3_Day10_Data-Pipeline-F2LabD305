from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from retrieval.embeddings import MiniLMEmbeddings
from retrieval.index import LocalEmbeddingIndex


def _settings(tmp_path: Path):
    settings = load_settings(tmp_path)
    return replace(settings, paths=replace(settings.paths, project_dir=tmp_path))


def _dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "paper_id": "10.1234/paper",
                "title": "Portable Vector Index Evidence",
                "text_for_embedding": "Title: Portable Vector Index Evidence | Summary: reproducible retrieval",
                "published": "2026-08-01",
                "authors_joined": "Author",
                "categories_joined": "AI",
                "summary": "reproducible retrieval",
                "abs_url": "https://example.test/paper",
                "pdf_url": "",
            }
        ]
    )


def test_minilm_exposes_model_name_for_ragas_telemetry(monkeypatch) -> None:
    engine = object()
    monkeypatch.setattr("retrieval.embeddings._load_model", lambda model_name: engine)

    embeddings = MiniLMEmbeddings("sentence-transformers/all-MiniLM-L6-v2")

    assert embeddings.model == "sentence-transformers/all-MiniLM-L6-v2"
    assert embeddings._engine is engine


def test_manifest_uses_portable_path_and_load_rebuilds_missing_collection(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    output_path = settings.paths.embeddings_json
    created: dict[str, object] = {}

    class FakeCollection:
        def add(self, **kwargs):
            created["added"] = kwargs

    class FakeClient:
        def __init__(self, path):
            created.setdefault("paths", []).append(path)

        def delete_collection(self, name):
            raise ValueError("missing")

        def create_collection(self, name, configuration):
            created["collection"] = name
            return FakeCollection()

        def get_collection(self, name):
            if created.get("loaded"):
                return FakeCollection()
            raise ValueError("missing")

    class FakeEmbeddings:
        def __init__(self, model_name):
            created["model"] = model_name

        def embed_documents(self, texts):
            return [[1.0] for _ in texts]

    monkeypatch.setattr("retrieval.index.chromadb.PersistentClient", FakeClient)
    monkeypatch.setattr("retrieval.index.MiniLMEmbeddings", FakeEmbeddings)
    monkeypatch.setattr(LocalEmbeddingIndex, "__init__", lambda self, **kwargs: self.__dict__.update(kwargs))

    LocalEmbeddingIndex.build(_dataframe(), settings, output_path)
    manifest = read_json(output_path)

    assert manifest["schema_version"] == 2
    assert manifest["persist_path"] == "data/chroma"
    assert not Path(manifest["persist_path"]).is_absolute()

    created.pop("collection", None)
    LocalEmbeddingIndex.load(settings, output_path)
    assert created["collection"] == settings.baseline_collection_name
    assert created["added"]["ids"] == ["10.1234/paper::0"]
