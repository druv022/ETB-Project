from datetime import date

from tools.data_generation.report_generation import time_windows


def test_get_weeks_basic() -> None:
    start = date(2020, 1, 1)
    end = date(2020, 1, 31)
    periods = time_windows.get_weeks(start, end)
    assert periods, "Expected at least one weekly period"
    assert periods[0].start == start
    assert periods[-1].end == end


def test_get_months_basic() -> None:
    start = date(2020, 1, 10)
    end = date(2020, 3, 5)
    periods = time_windows.get_months(start, end)
    labels = [p.label for p in periods]
    assert labels == ["2020-01", "2020-02", "2020-03"]
    assert periods[0].start == start
    assert periods[-1].end == end


def test_get_years_basic() -> None:
    start = date(2020, 6, 1)
    end = date(2022, 2, 1)
    periods = time_windows.get_years(start, end)
    labels = [p.label for p in periods]
    assert labels == ["2020", "2021", "2022"]
    assert periods[0].start == start
    assert periods[-1].end == end
