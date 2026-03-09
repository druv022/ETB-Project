"""
Utilities for generating common reporting time windows.

These helpers provide weekly, bi-weekly, monthly, quarterly, semi-annual,
and yearly ranges suitable for aggregating transaction data.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Period:
    """Represents a reporting period with a label and inclusive date range."""

    label: str
    start: date
    end: date


def _daterange(start: date, end: date, step_days: int) -> Iterable[tuple[date, date]]:
    current = start
    delta = timedelta(days=step_days)
    while current <= end:
        next_end = min(current + delta - timedelta(days=1), end)
        yield current, next_end
        current = next_end + timedelta(days=1)


def get_weeks(start: date, end: date) -> list[Period]:
    periods: list[Period] = []
    for s, e in _daterange(start, end, 7):
        label = f"{s.isocalendar().year}-W{s.isocalendar().week:02d}"
        periods.append(Period(label=label, start=s, end=e))
    return periods


def get_biweeks(start: date, end: date) -> list[Period]:
    periods: list[Period] = []
    for s, e in _daterange(start, end, 14):
        iso = s.isocalendar()
        label = f"{iso.year}-BW{iso.week:02d}"
        periods.append(Period(label=label, start=s, end=e))
    return periods


def get_months(start: date, end: date) -> list[Period]:
    periods: list[Period] = []
    year, month = start.year, start.month

    while True:
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year, 12, 31)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        if month_end < start:
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
            continue

        if month_start > end:
            break

        period_start = max(month_start, start)
        period_end = min(month_end, end)
        label = f"{year}-{month:02d}"
        periods.append(Period(label=label, start=period_start, end=period_end))

        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1

    return periods


def get_quarters(start: date, end: date) -> list[Period]:
    periods: list[Period] = []
    year, month = start.year, ((start.month - 1) // 3) * 3 + 1

    while True:
        quarter_start = date(year, month, 1)
        if month == 10:
            quarter_end = date(year, 12, 31)
        else:
            quarter_end = date(year, month + 3, 1) - timedelta(days=1)

        if quarter_end < start:
            if month == 10:
                year, month = year + 1, 1
            else:
                month += 3
            continue

        if quarter_start > end:
            break

        period_start = max(quarter_start, start)
        period_end = min(quarter_end, end)
        quarter_index = ((month - 1) // 3) + 1
        label = f"{year}-Q{quarter_index}"
        periods.append(Period(label=label, start=period_start, end=period_end))

        if month == 10:
            year, month = year + 1, 1
        else:
            month += 3

    return periods


def get_semiannual(start: date, end: date) -> list[Period]:
    periods: list[Period] = []
    year = start.year

    while True:
        h1_start = date(year, 1, 1)
        h1_end = date(year, 6, 30)
        h2_start = date(year, 7, 1)
        h2_end = date(year, 12, 31)

        for half_index, (half_start, half_end) in enumerate(
            ((h1_start, h1_end), (h2_start, h2_end)), start=1
        ):
            if half_end < start or half_start > end:
                continue

            period_start = max(half_start, start)
            period_end = min(half_end, end)
            label = f"{year}-H{half_index}"
            periods.append(Period(label=label, start=period_start, end=period_end))

        if h2_start > end:
            break

        year += 1

    return periods


def get_years(start: date, end: date) -> list[Period]:
    periods: list[Period] = []
    year = start.year

    while True:
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        if year_end < start:
            year += 1
            continue
        if year_start > end:
            break

        period_start = max(year_start, start)
        period_end = min(year_end, end)
        label = f"{year}"
        periods.append(Period(label=label, start=period_start, end=period_end))
        year += 1

    return periods
