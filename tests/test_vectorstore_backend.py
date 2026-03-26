from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from etb_project.vectorstore.faiss_backend import FaissDualVectorStoreBackend
from etb_project.vectorstore.manifest import IndexManifest


def test_index_manifest_roundtrip(tmp_path: Path) -> None:
    manifest = IndexManifest.create(
        backend="faiss",
        pdf_path="/some/doc.pdf",
        chunk_size=1000,
        chunk_overlap=200,
        embedding_model_id="ollama:qwen3-embedding:0.6b",
    )

    manifest_path = tmp_path / "manifest.json"
    manifest.save(manifest_path)

    loaded = IndexManifest.load(manifest_path)
    assert loaded == manifest


def test_index_manifest_load_fallback_created_at(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "backend": "faiss",
                "pdf_path": "/some/doc.pdf",
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "embedding_model_id": "ollama:qwen3-embedding:0.6b",
            }
        ),
        encoding="utf-8",
    )

    loaded = IndexManifest.load(manifest_path)
    assert loaded.backend == "faiss"
    assert loaded.created_at  # not empty


def test_faiss_backend_is_ready_false_initial(tmp_path: Path) -> None:
    backend = FaissDualVectorStoreBackend()
    assert not backend.is_ready(tmp_path)


def test_faiss_backend_persist_creates_dirs_and_manifest(tmp_path: Path) -> None:
    backend = FaissDualVectorStoreBackend()

    text_vs = MagicMock()
    caption_vs = MagicMock()

    manifest = IndexManifest.create(
        backend="faiss",
        pdf_path="/some/doc.pdf",
        chunk_size=1000,
        chunk_overlap=200,
        embedding_model_id="ollama:qwen3-embedding:0.6b",
    )

    backend.persist(
        tmp_path,
        text_vectorstore=text_vs,
        caption_vectorstore=caption_vs,
        manifest=manifest,
    )

    assert backend.is_ready(tmp_path)

    text_vs.save_local.assert_called_once_with(str(tmp_path / "text"))
    caption_vs.save_local.assert_called_once_with(str(tmp_path / "captions"))

    loaded_manifest = IndexManifest.load(tmp_path / "manifest.json")
    assert loaded_manifest == manifest


def test_faiss_backend_load_raises_when_not_ready(tmp_path: Path) -> None:
    backend = FaissDualVectorStoreBackend()
    embeddings = MagicMock()
    with pytest.raises(FileNotFoundError):
        backend.load(tmp_path, embeddings=embeddings)


def test_faiss_backend_load_validates_backend_mismatch(tmp_path: Path) -> None:
    backend = FaissDualVectorStoreBackend()
    embeddings = MagicMock()

    (tmp_path / "text").mkdir(parents=True)
    (tmp_path / "captions").mkdir(parents=True)
    bad_manifest = IndexManifest.create(
        backend="chroma",
        pdf_path="/some/doc.pdf",
        chunk_size=1000,
        chunk_overlap=200,
        embedding_model_id="ollama:qwen3-embedding:0.6b",
    )
    bad_manifest.save(tmp_path / "manifest.json")

    with pytest.raises(ValueError):
        backend.load(tmp_path, embeddings=embeddings)


class _DummySig:
    def __init__(self, keys: list[str]):
        self.parameters = dict.fromkeys(keys)


def test_faiss_backend_load_uses_allow_dangerous_deserialization(
    tmp_path: Path,
) -> None:
    backend = FaissDualVectorStoreBackend()
    embeddings = MagicMock()

    # Make it ready.
    (tmp_path / "text").mkdir(parents=True)
    (tmp_path / "captions").mkdir(parents=True)
    manifest = IndexManifest.create(
        backend="faiss",
        pdf_path="/some/doc.pdf",
        chunk_size=1000,
        chunk_overlap=200,
        embedding_model_id="ollama:qwen3-embedding:0.6b",
    )
    manifest.save(tmp_path / "manifest.json")

    text_store = MagicMock()
    caption_store = MagicMock()

    # Ensure both optional kwargs branches are exercised.
    with (
        patch(
            "etb_project.vectorstore.faiss_backend.inspect.signature",
            return_value=_DummySig(
                keys=["allow_dangerous_deserialization", "index_name"]
            ),
        ),
        patch(
            "etb_project.vectorstore.faiss_backend.FAISS.load_local",
            side_effect=[text_store, caption_store],
        ) as mock_load_local,
    ):
        loaded_text, loaded_caption = backend.load(tmp_path, embeddings=embeddings)

    assert loaded_text is text_store
    assert loaded_caption is caption_store

    # First call = text store
    assert mock_load_local.call_args_list[0].args[0] == str(tmp_path / "text")
    assert mock_load_local.call_args_list[0].args[1] is embeddings
    assert mock_load_local.call_args_list[0].kwargs["allow_dangerous_deserialization"]
    assert mock_load_local.call_args_list[0].kwargs["index_name"] == "index"

    # Second call = captions store
    assert mock_load_local.call_args_list[1].args[0] == str(tmp_path / "captions")
    assert mock_load_local.call_args_list[1].args[1] is embeddings
    assert mock_load_local.call_args_list[1].kwargs["allow_dangerous_deserialization"]
    assert mock_load_local.call_args_list[1].kwargs["index_name"] == "index"
