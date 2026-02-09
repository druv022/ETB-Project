"""Tests for main module."""

from typing import TYPE_CHECKING

import pytest

from etb_project import __version__

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


def test_version() -> None:
    """Test that version is defined."""
    assert __version__ is not None
    assert isinstance(__version__, str)


def test_import() -> None:
    """Test that the package can be imported."""
    from etb_project import main

    assert main is not None


def test_main_function_execution(capsys: "CaptureFixture[str]") -> None:
    """Test that main function executes without errors."""
    from etb_project import main

    main()
    _ = capsys.readouterr()  # consume stdout/stderr
    assert main is not None


def test_main_function_import() -> None:
    """Test that main function can be imported and called."""
    from etb_project.main import main

    # Verify function exists and is callable
    assert callable(main)

    # Call function and verify no exceptions
    try:
        main()
    except Exception as e:
        pytest.fail(f"main() raised {e} unexpectedly")
