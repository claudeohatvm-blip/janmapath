"""Vimshottari dasha - the 120-year planetary period cycle.

The Moon's nakshatra at birth selects the ruling graha, and the portion of that
nakshatra already traversed determines how much of its period had elapsed before
birth. Everything after that is arithmetic.
"""

from __future__ import annotations

from datetime import date, timedelta

from .constants import (
    NAKSHATRA_SPAN,
    SIDEREAL_YEAR_DAYS,
    VIMSHOTTARI_ORDER,
    VIMSHOTTARI_TOTAL_YEARS,
    VIMSHOTTARI_YEARS,
)
from .types import Position


def _years_to_days(years: float) -> timedelta:
    return timedelta(days=years * SIDEREAL_YEAR_DAYS)


def _antardashas(maha_lord: str, start: date, maha_years: float) -> list[dict]:
    """Sub-periods within a mahadasha.

    An antardasha of lord A inside a mahadasha of lord M runs for
    (years_M * years_A) / 120 years, in the standard cyclic order beginning
    with M itself.
    """
    begin = VIMSHOTTARI_ORDER.index(maha_lord)
    cursor = start
    periods = []
    for step in range(9):
        lord = VIMSHOTTARI_ORDER[(begin + step) % 9]
        years = maha_years * VIMSHOTTARI_YEARS[lord] / VIMSHOTTARI_TOTAL_YEARS
        end = cursor + _years_to_days(years)
        periods.append(
            {
                "lord": lord,
                "start": cursor.isoformat(),
                "end": end.isoformat(),
                "years": round(years, 4),
            }
        )
        cursor = end
    return periods


def compute_vimshottari(
    moon: Position, birth_date: date, *, cycles: int = 9, as_of: date | None = None
) -> dict:
    """Full mahadasha sequence from birth, with the active period marked."""
    as_of = as_of or date.today()

    elapsed_fraction = (moon.longitude % NAKSHATRA_SPAN) / NAKSHATRA_SPAN
    start_index = moon.nakshatra_index % 9
    start_lord = VIMSHOTTARI_ORDER[start_index]

    # The portion of the starting lord's period still unspent at birth.
    balance_years = VIMSHOTTARI_YEARS[start_lord] * (1.0 - elapsed_fraction)

    periods: list[dict] = []
    cursor = birth_date

    for step in range(cycles):
        lord = VIMSHOTTARI_ORDER[(start_index + step) % 9]
        years = balance_years if step == 0 else float(VIMSHOTTARI_YEARS[lord])
        end = cursor + _years_to_days(years)
        periods.append(
            {
                "lord": lord,
                "start": cursor.isoformat(),
                "end": end.isoformat(),
                "years": round(years, 4),
                "is_partial": step == 0,
                "antardashas": _antardashas(lord, cursor, years),
            }
        )
        cursor = end

    current = _locate(periods, as_of)
    current_antar = None
    if current is not None:
        current_antar = _locate(periods[current]["antardashas"], as_of)

    return {
        "balance_at_birth": {
            "lord": start_lord,
            "years": round(balance_years, 4),
        },
        "periods": periods,
        "current": {
            "mahadasha": periods[current]["lord"] if current is not None else None,
            "antardasha": (
                periods[current]["antardashas"][current_antar]["lord"]
                if current is not None and current_antar is not None
                else None
            ),
            "as_of": as_of.isoformat(),
        },
    }


def _locate(periods: list[dict], moment: date) -> int | None:
    """Index of the period containing `moment`, if any."""
    for index, period in enumerate(periods):
        if date.fromisoformat(period["start"]) <= moment < date.fromisoformat(period["end"]):
            return index
    return None
