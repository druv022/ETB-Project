import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from tools.data_generation.report_generation.run_report_graph import (
    ALL_CATEGORIES,
    main,
)


@pytest.fixture(autouse=True)
def _restore_argv() -> Iterator[None]:
    original = sys.argv.copy()
    try:
        yield
    finally:
        sys.argv = original


def _build_base_argv() -> list[str]:
    return [
        "run_report_graph",
        "--start-date",
        "2020-01-01",
        "--end-date",
        "2020-01-31",
        "--output-dir",
        str(Path("tools/data_generation/report_generation/output")),
    ]


def test_main_with_explicit_category(capsys: pytest.CaptureFixture[str]) -> None:
    """When --category is provided, only that category is executed."""

    sys.argv = _build_base_argv() + ["--category", "sales"]

    main()

    captured = capsys.readouterr().out
    assert "Running workflow for category: sales" in captured

    # Ensure we did not accidentally run other categories.
    for category in ALL_CATEGORIES:
        if category != "sales":
            assert f"Running workflow for category: {category}" not in captured


def test_main_without_category_runs_all(capsys: pytest.CaptureFixture[str]) -> None:
    """When --category is omitted, all categories are executed."""

    sys.argv = _build_base_argv()

    main()

    captured = capsys.readouterr().out
    for category in ALL_CATEGORIES:
        assert f"Running workflow for category: {category}" in captured
