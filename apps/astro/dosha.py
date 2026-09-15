"""Dosha detection.

Each rule returns a structured finding, never prose. Narration happens later,
outside the engine, and may only describe what these findings contain.
"""

from __future__ import annotations

from .constants import MANGAL_DOSHA_HOUSES, SADE_SATI_HOUSES, SIGNS
from .types import Position, TimeAccuracy

_SEVEN_GRAHAS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")


def _by_body(positions: list[Position]) -> dict[str, Position]:
    return {p.body: p for p in positions}


def _house_from(reference_sign: int, target_sign: int) -> int:
    return ((target_sign - reference_sign) % 12) + 1


def check_mangal(positions: list[Position], accuracy: TimeAccuracy) -> dict:
    """Mangal (Kuja) dosha - Mars in houses 1, 2, 4, 7, 8 or 12.

    Assessed from the Lagna when the birth time is reliable, and from the Moon
    regardless. The Moon-based reading needs no birth time, so a useful finding
    survives even when the ascendant cannot be trusted.
    """
    bodies = _by_body(positions)
    mars, moon = bodies["Mars"], bodies["Moon"]

    from_lagna = None
    if accuracy is not TimeAccuracy.UNKNOWN and mars.house is not None:
        from_lagna = mars.house in MANGAL_DOSHA_HOUSES

    house_from_moon = _house_from(moon.sign_index, mars.sign_index)
    from_moon = house_from_moon in MANGAL_DOSHA_HOUSES

    present = bool(from_lagna) or from_moon

    # Mars in its own or exalted sign is traditionally held to neutralise the
    # dosha; this is the most widely accepted cancellation rule.
    cancelled = present and mars.dignity in {"own", "exalted"}

    if not present:
        severity = "none"
    elif cancelled:
        severity = "cancelled"
    elif from_lagna and mars.house in {7, 8}:
        severity = "high"
    else:
        severity = "moderate"

    return {
        "code": "mangal",
        "name": "Mangal Dosha",
        "present": present,
        "severity": severity,
        "is_cancelled": cancelled,
        "basis": {
            "mars_sign": mars.sign,
            "mars_dignity": mars.dignity,
            "house_from_lagna": mars.house,
            "house_from_moon": house_from_moon,
            "flagged_from_lagna": from_lagna,
            "flagged_from_moon": from_moon,
        },
        "requires_birth_time": False,
    }


def check_kaal_sarp(positions: list[Position]) -> dict:
    """Kaal Sarp dosha - all seven grahas hemmed between Rahu and Ketu."""
    bodies = _by_body(positions)
    rahu = bodies["Rahu"]

    # Measure every graha's angular distance forward from Rahu. If all fall
    # within the first 180 degrees they lie on one side of the nodal axis.
    offsets = {
        name: (bodies[name].longitude - rahu.longitude) % 360.0
        for name in _SEVEN_GRAHAS
    }

    all_after_rahu = all(0.0 < value < 180.0 for value in offsets.values())
    all_after_ketu = all(180.0 < value < 360.0 for value in offsets.values())
    present = all_after_rahu or all_after_ketu

    return {
        "code": "kaal_sarp",
        "name": "Kaal Sarp Dosha",
        "present": present,
        "severity": "moderate" if present else "none",
        "is_cancelled": False,
        "basis": {
            "rahu_sign": rahu.sign,
            "ketu_sign": bodies["Ketu"].sign,
            "axis": "rahu_to_ketu" if all_after_rahu else ("ketu_to_rahu" if all_after_ketu else None),
            "grahas_outside_axis": [
                name for name, value in offsets.items()
                if not (0.0 < value < 180.0) and not (180.0 < value < 360.0)
            ] if not present else [],
        },
        "requires_birth_time": False,
    }


def check_sade_sati(positions: list[Position], saturn_transit_sign: int | None) -> dict:
    """Sade Sati - Saturn transiting the 12th, 1st or 2nd from the natal Moon.

    A transit condition rather than a birth condition: it depends on where
    Saturn is now, not where it was at birth.
    """
    moon = _by_body(positions)["Moon"]

    if saturn_transit_sign is None:
        return {
            "code": "sade_sati",
            "name": "Sade Sati",
            "present": False,
            "severity": "unknown",
            "is_cancelled": False,
            "basis": {"reason": "transit position unavailable"},
            "requires_birth_time": False,
        }

    house = _house_from(moon.sign_index, saturn_transit_sign)
    present = house in SADE_SATI_HOUSES
    phase = {12: "rising", 1: "peak", 2: "setting"}.get(house)

    return {
        "code": "sade_sati",
        "name": "Sade Sati",
        "present": present,
        "severity": ("high" if house == 1 else "moderate") if present else "none",
        "is_cancelled": False,
        "basis": {
            "natal_moon_sign": moon.sign,
            "saturn_transit_sign": SIGNS[saturn_transit_sign],
            "house_from_moon": house,
            "phase": phase,
        },
        "requires_birth_time": False,
    }


def scan(
    positions: list[Position],
    accuracy: TimeAccuracy,
    saturn_transit_sign: int | None = None,
) -> list[dict]:
    """Run every dosha rule and return the findings that fired."""
    return [
        check_mangal(positions, accuracy),
        check_kaal_sarp(positions),
        check_sade_sati(positions, saturn_transit_sign),
    ]
