"""Chart casting - house placement and divisional charts."""

from __future__ import annotations

from dataclasses import replace

from .constants import SIGN_LORDS, SIGNS
from .ephemeris import describe_longitude, division_index
from .types import Position


def assign_houses(positions: list[Position], ascendant: float) -> list[Position]:
    """Place each graha in a Whole Sign house counted from the Lagna.

    Whole Sign is the Vedic standard: the ascendant's entire sign is the first
    house, the next sign the second, and so on. No interpolation, no cusps.
    """
    asc_sign = int(ascendant // 30)
    return [
        replace(position, house=((position.sign_index - asc_sign) % 12) + 1)
        for position in positions
    ]


def build_houses(ascendant: float, positions: list[Position]) -> list[dict]:
    """The twelve bhavas with their lords and occupants."""
    asc_sign = int(ascendant // 30)
    houses = []
    for offset in range(12):
        sign_index = (asc_sign + offset) % 12
        houses.append(
            {
                "number": offset + 1,
                "sign": SIGNS[sign_index],
                "sign_index": sign_index,
                "lord": SIGN_LORDS[sign_index],
                "occupants": [
                    p.body for p in positions if p.sign_index == sign_index
                ],
            }
        )
    return houses


def navamsa_sign_index(longitude: float) -> int:
    """D9 sign for a sidereal longitude.

    Each rashi divides into nine navamsas of 3 deg 20 min. Counting those
    divisions continuously from 0 deg Mesha and taking the remainder modulo 12
    reproduces the traditional element-based rule exactly: movable signs begin
    from themselves, fixed from the ninth, dual from the fifth.
    """
    return division_index(longitude) % 12


def build_navamsa(positions: list[Position], ascendant: float) -> dict:
    """The D9 chart - the primary divisional chart for marriage and dharma."""
    asc_navamsa = navamsa_sign_index(ascendant)
    placements = []
    for position in positions:
        sign_index = navamsa_sign_index(position.longitude)
        placements.append(
            {
                "body": position.body,
                "sign": SIGNS[sign_index],
                "sign_index": sign_index,
                "house": ((sign_index - asc_navamsa) % 12) + 1,
            }
        )
    return {
        "ascendant_sign": SIGNS[asc_navamsa],
        "ascendant_sign_index": asc_navamsa,
        "placements": placements,
    }


def describe_ascendant(ascendant: float) -> dict:
    parts = describe_longitude(ascendant)
    return {
        "longitude": round(ascendant, 4),
        "sign": parts["sign"],
        "sign_index": parts["sign_index"],
        "degree_in_sign": round(parts["degree_in_sign"], 4),
        "nakshatra": parts["nakshatra"],
        "pada": parts["pada"],
        "lord": SIGN_LORDS[parts["sign_index"]],
    }
