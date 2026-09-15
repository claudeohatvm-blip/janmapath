"""Graha drishti - planetary aspects.

Every graha aspects the seventh house from itself. Mars, Jupiter and Saturn
carry additional special aspects. Rahu and Ketu are given the Jupiter-like
5-7-9 pattern followed by most modern Parashari practice.

Aspects matter for accuracy: a malefic in the 7th and a malefic aspecting the
7th from elsewhere produce different readings, and omitting drishti would make
half the classical rules unusable.
"""

from __future__ import annotations

from .types import Position

SPECIAL_ASPECTS: dict[str, tuple[int, ...]] = {
    "Mars": (4, 7, 8),
    "Jupiter": (5, 7, 9),
    "Saturn": (3, 7, 10),
    "Rahu": (5, 7, 9),
    "Ketu": (5, 7, 9),
}
DEFAULT_ASPECTS: tuple[int, ...] = (7,)


def aspected_houses(body: str, from_house: int) -> list[int]:
    """Houses this graha casts drishti upon, counted from its own house."""
    pattern = SPECIAL_ASPECTS.get(body, DEFAULT_ASPECTS)
    return sorted(((from_house - 1 + step - 1) % 12) + 1 for step in pattern)


def aspects_on_house(positions: list[Position], house: int) -> list[str]:
    """Which grahas aspect a given house."""
    result = []
    for position in positions:
        if position.house is None or position.house == house:
            continue
        if house in aspected_houses(position.body, position.house):
            result.append(position.body)
    return result


def build_aspect_map(positions: list[Position]) -> dict[int, list[str]]:
    """Every house mapped to the grahas aspecting it."""
    return {house: aspects_on_house(positions, house) for house in range(1, 13)}
