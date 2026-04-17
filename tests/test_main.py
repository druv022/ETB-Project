"""Tests for main module."""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from etb_project import __version__

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


pytest.importorskip("langchain_core")


def test_version() -> None:
    """Test that version is defined."""
    assert __version__ is not None
    assert isinstance(__version__, str)


def test_import() -> None:
    """Test that the package can be imported."""
    from etb_project import main

    assert main is not None


def test_main_exits_when_pdf_not_configured(tmp_path: Path) -> None:
    """main() raises SystemExit(1) when config has no valid PDF path."""
    from etb_project.main import main

    with patch("etb_project.main.load_config") as mock_load:
        mock_load.return_value = MagicMock(
            pdf=None,
            query="",
            retriever_k=10,
            log_level="INFO",
            vector_store_path=str(tmp_path / "vector_index"),
            vector_store_backend="faiss",
        )
        with pytest.raises(SystemExit):
            main()


def test_main_exits_when_pdf_path_missing(tmp_path: Path) -> None:
    """main() raises SystemExit(1) when PDF path does not exist."""
    from etb_project.main import main

    with patch("etb_project.main.load_config") as mock_load:
        mock_load.return_value = MagicMock(
            pdf="/nonexistent/file.pdf",
            query="",
            retriever_k=10,
            log_level="INFO",
            vector_store_path=str(tmp_path / "vector_index"),
            vector_store_backend="faiss",
        )
        with pytest.raises(SystemExit):
            main()


def test_main_runs_with_mocked_pipeline(
    tmp_path: Path, capsys: "CaptureFixture[str]"
) -> None:
    """main() runs without error when config and pipeline are mocked."""
    from etb_project.main import main

    pdf_file = tmp_path / "dummy.pdf"
    pdf_file.write_bytes(b"")
    mock_text_retriever = MagicMock()
    mock_text_retriever.invoke.return_value = []
    mock_caption_retriever = MagicMock()
    mock_caption_retriever.invoke.return_value = []
    mock_text_vs = MagicMock()
    mock_text_vs.as_retriever.return_value = mock_text_retriever
    mock_caption_vs = MagicMock()
    mock_caption_vs.as_retriever.return_value = mock_caption_retriever
    mock_dual_retriever = MagicMock()
    mock_dual_retriever.invoke.return_value = []

    vector_store_root = tmp_path / "vector_index"
    with (
        patch("etb_project.main.load_config") as mock_load,
        patch("etb_project.main.FaissDualVectorStoreBackend") as mock_backend_cls,
        patch("etb_project.main.get_embeddings") as mock_get_embeddings,
        patch("etb_project.main.DualRetriever") as mock_dual_cls,
    ):
        mock_load.return_value = MagicMock(
            pdf=str(pdf_file),
            query="test query",
            retriever_k=5,
            log_level="INFO",
            vector_store_path=str(vector_store_root),
            vector_store_backend="faiss",
        )
        mock_backend = MagicMock()
        mock_backend.is_ready.return_value = True
        mock_backend.load.return_value = (mock_text_vs, mock_caption_vs)
        mock_backend_cls.return_value = mock_backend
        mock_get_embeddings.return_value = MagicMock()
        mock_dual_cls.return_value = mock_dual_retriever

        main()
    _ = capsys.readouterr()
    mock_dual_retriever.invoke.assert_called_once_with("test query")


def test_main_uses_dual_vectorstore_pipeline(tmp_path: Path) -> None:
    """main() builds dual vector stores and wraps both retrievers."""
    from etb_project.main import main

    pdf_file = tmp_path / "dummy.pdf"
    pdf_file.write_bytes(b"")
    mock_text_vs = MagicMock()
    mock_caption_vs = MagicMock()
    mock_text_retriever = MagicMock()
    mock_caption_retriever = MagicMock()
    mock_text_vs.as_retriever.return_value = mock_text_retriever
    mock_caption_vs.as_retriever.return_value = mock_caption_retriever
    mock_dual_retriever = MagicMock()
    mock_dual_retriever.invoke.return_value = []

    vector_store_root = tmp_path / "vector_index"

    with (
        patch("etb_project.main.load_config") as mock_load,
        patch("etb_project.main.FaissDualVectorStoreBackend") as mock_backend_cls,
        patch("etb_project.main.get_embeddings") as mock_get_embeddings,
        patch("etb_project.main.DualRetriever") as mock_dual_cls,
    ):
        mock_load.return_value = MagicMock(
            pdf=str(pdf_file),
            query="test query",
            retriever_k=4,
            log_level="INFO",
            vector_store_path=str(vector_store_root),
            vector_store_backend="faiss",
        )
        mock_backend = MagicMock()
        mock_backend.is_ready.return_value = True
        mock_backend.load.return_value = (mock_text_vs, mock_caption_vs)
        mock_backend_cls.return_value = mock_backend
        mock_get_embeddings.return_value = MagicMock()
        mock_dual_cls.return_value = mock_dual_retriever

        main()

    assert mock_backend.load.call_count == 1
    mock_text_vs.as_retriever.assert_called_once_with(search_kwargs={"k": 4})
    mock_caption_vs.as_retriever.assert_called_once_with(search_kwargs={"k": 4})
    mock_dual_cls.assert_called_once_with(
        text_retriever=mock_text_retriever,
        caption_retriever=mock_caption_retriever,
        k_total=4,
    )


def test_main_interactive_uses_graph_with_dual_retriever(tmp_path: Path) -> None:
    """Interactive mode builds graph with the dual retriever adapter."""
    from etb_project.main import main

    pdf_file = tmp_path / "dummy.pdf"
    pdf_file.write_bytes(b"")
    mock_text_vs = MagicMock()
    mock_caption_vs = MagicMock()
    mock_text_vs.as_retriever.return_value = MagicMock()
    mock_caption_vs.as_retriever.return_value = MagicMock()
    mock_dual_retriever = MagicMock()
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"answer": "ok"}

    vector_store_root = tmp_path / "vector_index"
    with (
        patch("etb_project.main.load_config") as mock_load,
        patch("etb_project.main.FaissDualVectorStoreBackend") as mock_backend_cls,
        patch("etb_project.main.get_embeddings") as mock_get_embeddings,
        patch("etb_project.main.DualRetriever") as mock_dual_cls,
        patch("etb_project.main.build_rag_graph") as mock_build_graph,
        patch("builtins.input", side_effect=["hello", ""]),
        patch("builtins.print"),
    ):
        mock_load.return_value = MagicMock(
            pdf=str(pdf_file),
            query="",
            retriever_k=3,
            log_level="INFO",
            vector_store_path=str(vector_store_root),
            vector_store_backend="faiss",
        )
        mock_backend = MagicMock()
        mock_backend.is_ready.return_value = True
        mock_backend.load.return_value = (mock_text_vs, mock_caption_vs)
        mock_backend_cls.return_value = mock_backend
        mock_get_embeddings.return_value = MagicMock()
        mock_dual_cls.return_value = mock_dual_retriever
        mock_build_graph.return_value = mock_graph

        main()

    mock_build_graph.assert_called_once()
    assert mock_build_graph.call_args.kwargs["retriever"] is mock_dual_retriever
    mock_graph.invoke.assert_called_once()
    args, kwargs = mock_graph.invoke.call_args
    assert args[0] == {"query": "hello"}
    assert "config" in kwargs


def test_main_function_import() -> None:
    """Test that main function can be imported and is callable."""
    from etb_project.main import main

    assert callable(main)
