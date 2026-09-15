"""A simplified graha strength index.

This is deliberately NOT Shadbala. Full Shadbala sums six weighted components
and is a substantial computation in its own right; presenting an approximation
under that name would be dishonest. What follows is a transparent index built
from four factors that materially change a reading, and it is labelled as such
everywhere it surfaces.
"""

from __future__ import annotations

from .constants import (
    COMBUSTION_ORB,
    COMBUSTION_ORB_RETROGRADE,
    DUSTHANA,
    KENDRA,
    TRIKONA,
)
from .types import Position

# Contribution of each factor, in points. Dignity dominates because sign
# placement is the single strongest classical determinant of a graha's ability
# to deliver its significations.
_DIGNITY_POINTS = {"exalted": 40, "own": 30, "neutral": 15, "debilitated": 0}
_HOUSE_POINTS = {"kendra": 25, "trikona": 25, "dusthana": 5, "other": 15}
_MOTION_POINTS = {"direct": 15, "retrograde": 10}
_COMBUSTION_PENALTY = 20


def separation(a: float, b: float) -> float:
    """Shortest angular distance between two longitudes, 0-180."""
    delta = abs(a - b) % 360.0
    return min(delta, 360.0 - delta)


def is_combust(position: Position, sun_longitude: float) -> bool:
    """Whether the graha is burnt by proximity to the Sun.

    A combust graha keeps its placement but loses much of its capacity to
    deliver results - a materially different reading from a strong one in the
    same house.
    """
    if position.body in {"Sun", "Rahu", "Ketu"}:
        return False
    orb = (
        COMBUSTION_ORB_RETROGRADE.get(position.body, COMBUSTION_ORB.get(position.body))
        if position.retrograde
        else COMBUSTION_ORB.get(position.body)
    )
    if orb is None:
        return False
    return separation(position.longitude, sun_longitude) <= orb


def house_class(house: int | None) -> str:
    if house is None:
        return "other"
    if house in KENDRA and house in TRIKONA:
        return "trikona"          # the 1st is both; trinal rulership prevails
    if house in KENDRA:
        return "kendra"
    if house in TRIKONA:
        return "trikona"
    if house in DUSTHANA:
        return "dusthana"
    return "other"


def score(position: Position, sun_longitude: float) -> dict:
    """Strength index from 0 to 100, with every contributing factor exposed."""
    combust = is_combust(position, sun_longitude)
    klass = house_class(position.house)

    points = (
        _DIGNITY_POINTS.get(position.dignity, 15)
        + _HOUSE_POINTS[klass]
        + (_MOTION_POINTS["retrograde"] if position.retrograde else _MOTION_POINTS["direct"])
    )
    if combust:
        points -= _COMBUSTION_PENALTY

    total = max(0, min(100, points))

    if total >= 70:
        band = "strong"
    elif total >= 45:
        band = "moderate"
    else:
        band = "weak"

    return {
        "body": position.body,
        "score": total,
        "band": band,
        "factors": {
            "dignity": position.dignity,
            "house_class": klass,
            "retrograde": position.retrograde,
            "combust": combust,
        },
    }


def score_all(positions: list[Position]) -> dict[str, dict]:
    sun = next(p for p in positions if p.body == "Sun")
    return {p.body: score(p, sun.longitude) for p in positions}
