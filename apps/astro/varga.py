"""Divisional charts (vargas).

D1 is the birth chart itself. D9 (Navamsa) governs marriage, dharma and the
inner strength of every graha. D10 (Dashamsha) governs career and public
standing. A graha that is weak in D1 but strong in D9 is read as delivering
late rather than not at all.
"""

from __future__ import annotations

from .constants import SIGNS
from .types import Position


def navamsa_sign(longitude: float) -> int:
    """D9 sign index.

    Each rashi divides into nine parts of 3 deg 20 min. Counting those parts
    continuously from 0 deg Mesha and taking the remainder modulo 12 reproduces
    the classical element rule exactly: movable signs begin from themselves,
    fixed signs from the ninth, dual signs from the fifth.
    """
    return min(int((longitude % 360.0) * 3.0 / 10.0), 107) % 12


def dashamsha_sign(longitude: float) -> int:
    """D10 sign index.

    Each rashi divides into ten parts of 3 degrees. Odd signs count from the
    sign itself; even signs count from the ninth sign from it.
    """
    longitude %= 360.0
    sign = int(longitude // 30)
    part = min(int((longitude % 30.0) / 3.0), 9)
    offset = 0 if sign % 2 == 0 else 8      # sign % 2 == 0 is an odd rashi (1st, 3rd, ...)
    return (sign + offset + part) % 12


_DIVISORS = {"D9": navamsa_sign, "D10": dashamsha_sign}


def build_varga(
    name: str, positions: list[Position], ascendant: float
) -> dict:
    """A divisional chart with its own ascendant and house placements."""
    divisor = _DIVISORS[name]
    varga_asc = divisor(ascendant)

    placements = []
    for position in positions:
        sign_index = divisor(position.longitude)
        placements.append(
            {
                "body": position.body,
                "sign": SIGNS[sign_index],
                "sign_index": sign_index,
                "house": ((sign_index - varga_asc) % 12) + 1,
            }
        )

    return {
        "varga": name,
        "ascendant_sign": SIGNS[varga_asc],
        "ascendant_sign_index": varga_asc,
        "placements": placements,
    }


def house_of(varga: dict, body: str) -> int | None:
    for placement in varga["placements"]:
        if placement["body"] == body:
            return placement["house"]
    return None


def occupants_of(varga: dict, house: int) -> list[str]:
    return [p["body"] for p in varga["placements"] if p["house"] == house]
