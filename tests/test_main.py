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


def test_main_exits_when_pdf_not_configured() -> None:
    """main() raises SystemExit(1) when config has no valid PDF path."""
    from etb_project.main import main

    with patch("etb_project.main.load_config") as mock_load:
        mock_load.return_value = MagicMock(
            pdf=None,
            query="",
            retriever_k=10,
            log_level="INFO",
        )
        with pytest.raises(SystemExit):
            main()


def test_main_exits_when_pdf_path_missing() -> None:
    """main() raises SystemExit(1) when PDF path does not exist."""
    from etb_project.main import main

    with patch("etb_project.main.load_config") as mock_load:
        mock_load.return_value = MagicMock(
            pdf="/nonexistent/file.pdf",
            query="",
            retriever_k=10,
            log_level="INFO",
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
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = []
    mock_vs = MagicMock()
    mock_vs.as_retriever.return_value = mock_retriever

    with patch("etb_project.main.load_config") as mock_load:
        mock_load.return_value = MagicMock(
            pdf=str(pdf_file),
            query="test query",
            retriever_k=5,
            log_level="INFO",
        )
        with patch("etb_project.main.load_pdf") as mock_load_pdf:
            from langchain_core.documents import Document

            mock_load_pdf.return_value = [
                Document(page_content="x", metadata={}),
            ]
            with patch("etb_project.main.process_documents") as mock_process:
                mock_process.return_value = mock_vs
                main()
    _ = capsys.readouterr()
    mock_retriever.invoke.assert_called_once_with("test query")


def test_main_function_import() -> None:
    """Test that main function can be imported and is callable."""
    from etb_project.main import main

    assert callable(main)
