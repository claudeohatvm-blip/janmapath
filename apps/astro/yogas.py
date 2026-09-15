"""Yoga detection.

Only well-attested Parashari combinations are implemented. Each finding records
the exact placements that produced it, so a reader can verify the conclusion
against the chart rather than take it on trust.
"""

from __future__ import annotations

from .aspects import aspected_houses
from .constants import (
    EXALTATION_SIGN,
    KENDRA,
    MAHAPURUSHA_YOGAS,
    SIGN_LORDS,
    SIGNS,
    TRIKONA,
)
from .types import Position


def house_lords(ascendant_sign: int) -> dict[int, str]:
    """Which graha rules each of the twelve bhavas for this ascendant."""
    return {
        house: SIGN_LORDS[(ascendant_sign + house - 1) % 12]
        for house in range(1, 13)
    }


def _placement(positions: list[Position], body: str) -> Position | None:
    for position in positions:
        if position.body == body:
            return position
    return None


def _finding(code: str, name: str, category: str, detail: str, **extra) -> dict:
    return {"code": code, "name": name, "category": category, "detail": detail, **extra}


def mahapurusha(positions: list[Position]) -> list[dict]:
    """Panch Mahapurusha - own or exalted sign, in a kendra from the Lagna."""
    found = []
    for body, yoga_name in MAHAPURUSHA_YOGAS.items():
        position = _placement(positions, body)
        if position is None or position.house is None:
            continue
        if position.dignity in {"own", "exalted"} and position.house in KENDRA:
            found.append(
                _finding(
                    f"mahapurusha_{yoga_name.lower()}",
                    f"{yoga_name} Yoga",
                    "strength",
                    f"{body} is {position.dignity} in {position.sign} "
                    f"and occupies the {position.house}th house, a kendra.",
                    body=body,
                )
            )
    return found


def gaja_kesari(positions: list[Position]) -> list[dict]:
    """Jupiter in a kendra from the Moon."""
    jupiter, moon = _placement(positions, "Jupiter"), _placement(positions, "Moon")
    if jupiter is None or moon is None:
        return []
    house_from_moon = ((jupiter.sign_index - moon.sign_index) % 12) + 1
    if house_from_moon not in KENDRA:
        return []
    return [
        _finding(
            "gaja_kesari",
            "Gaja Kesari Yoga",
            "fortune",
            f"Jupiter in {jupiter.sign} stands {house_from_moon} houses from the "
            f"Moon in {moon.sign}, a kendra.",
            house_from_moon=house_from_moon,
        )
    ]


def budhaditya(positions: list[Position], strengths: dict) -> list[dict]:
    """Sun and Mercury in the same sign - intellect, discernment."""
    sun, mercury = _placement(positions, "Sun"), _placement(positions, "Mercury")
    if sun is None or mercury is None or sun.sign_index != mercury.sign_index:
        return []
    combust = strengths.get("Mercury", {}).get("factors", {}).get("combust", False)
    return [
        _finding(
            "budhaditya",
            "Budhaditya Yoga",
            "intellect",
            f"Sun and Mercury are together in {sun.sign}."
            + (
                " Mercury is combust, which tempers the result."
                if combust
                else ""
            ),
            weakened_by_combustion=combust,
        )
    ]


def chandra_mangala(positions: list[Position]) -> list[dict]:
    """Moon conjunct Mars - earning capacity, often through effort or risk."""
    moon, mars = _placement(positions, "Moon"), _placement(positions, "Mars")
    if moon is None or mars is None or moon.sign_index != mars.sign_index:
        return []
    return [
        _finding(
            "chandra_mangala",
            "Chandra-Mangala Yoga",
            "wealth",
            f"Moon and Mars are conjunct in {moon.sign}.",
        )
    ]


def _connected(a: Position, b: Position) -> str | None:
    """How two grahas relate: conjunction, exchange, or mutual aspect."""
    if a.house is None or b.house is None:
        return None
    if a.house == b.house:
        return "conjunction"
    if b.house in aspected_houses(a.body, a.house) and a.house in aspected_houses(
        b.body, b.house
    ):
        return "mutual aspect"
    return None


def parivartana(
    positions: list[Position], lords: dict[int, str], house_a: int, house_b: int
) -> bool:
    """Sign exchange between the lords of two houses."""
    lord_a, lord_b = lords[house_a], lords[house_b]
    pos_a, pos_b = _placement(positions, lord_a), _placement(positions, lord_b)
    if pos_a is None or pos_b is None:
        return False
    return pos_a.house == house_b and pos_b.house == house_a


def dhana_yogas(positions: list[Position], lords: dict[int, str]) -> list[dict]:
    """Wealth combinations from the lords of the 2nd, 5th, 9th and 11th."""
    pairs = [(2, 11), (2, 9), (5, 9), (5, 11), (9, 11), (1, 2)]
    found = []
    for house_a, house_b in pairs:
        lord_a, lord_b = lords[house_a], lords[house_b]
        if lord_a == lord_b:
            continue
        pos_a, pos_b = _placement(positions, lord_a), _placement(positions, lord_b)
        if pos_a is None or pos_b is None:
            continue

        relation = _connected(pos_a, pos_b)
        if parivartana(positions, lords, house_a, house_b):
            relation = "sign exchange"
        if relation is None:
            continue

        found.append(
            _finding(
                f"dhana_{house_a}_{house_b}",
                f"Dhana Yoga ({house_a}th-{house_b}th)",
                "wealth",
                f"{lord_a}, lord of the {house_a}th, and {lord_b}, lord of the "
                f"{house_b}th, are linked by {relation}.",
                houses=[house_a, house_b],
                relation=relation,
            )
        )
    return found


def raja_yogas(positions: list[Position], lords: dict[int, str]) -> list[dict]:
    """Kendra lord linked to a trikona lord - status and authority."""
    found = []
    seen: set[tuple[str, str]] = set()
    for kendra in sorted(KENDRA):
        for trikona in sorted(TRIKONA):
            if kendra == trikona:
                continue
            lord_k, lord_t = lords[kendra], lords[trikona]
            if lord_k == lord_t:
                continue
            key = tuple(sorted((lord_k, lord_t)))
            if key in seen:
                continue

            pos_k, pos_t = _placement(positions, lord_k), _placement(positions, lord_t)
            if pos_k is None or pos_t is None:
                continue

            relation = _connected(pos_k, pos_t)
            if parivartana(positions, lords, kendra, trikona):
                relation = "sign exchange"
            if relation is None:
                continue

            seen.add(key)
            found.append(
                _finding(
                    f"raja_{kendra}_{trikona}",
                    f"Raja Yoga ({kendra}th-{trikona}th)",
                    "status",
                    f"{lord_k}, lord of the {kendra}th kendra, and {lord_t}, lord of "
                    f"the {trikona}th trikona, are linked by {relation}.",
                    houses=[kendra, trikona],
                    relation=relation,
                )
            )
    return found


def kemadruma(positions: list[Position]) -> list[dict]:
    """Moon isolated - no graha in the 2nd or 12th from it, and none with it.

    Sun, Rahu and Ketu are excluded from the count, as is standard.
    """
    moon = _placement(positions, "Moon")
    if moon is None:
        return []

    neighbours = []
    for position in positions:
        if position.body in {"Moon", "Sun", "Rahu", "Ketu"}:
            continue
        offset = (position.sign_index - moon.sign_index) % 12
        if offset in {0, 1, 11}:
            neighbours.append(position.body)

    if neighbours:
        return []
    return [
        _finding(
            "kemadruma",
            "Kemadruma Yoga",
            "challenge",
            f"No graha accompanies or flanks the Moon in {moon.sign}. Classical "
            "texts read this as periods of isolation and uneven support, often "
            "easing once other strengths in the chart mature.",
        )
    ]


def neecha_bhanga(positions: list[Position]) -> list[dict]:
    """Cancellation of debilitation.

    Applied when the dispositor of the debilitation sign, or the graha exalted
    in that sign, occupies a kendra from the Lagna.
    """
    found = []
    for position in positions:
        if position.dignity != "debilitated" or position.house is None:
            continue

        dispositor = SIGN_LORDS[position.sign_index]
        exalted_here = next(
            (body for body, sign in EXALTATION_SIGN.items() if sign == position.sign_index),
            None,
        )

        reasons = []
        for body, label in ((dispositor, "dispositor"), (exalted_here, "exaltation lord")):
            if body is None:
                continue
            other = _placement(positions, body)
            if other is not None and other.house in KENDRA:
                reasons.append(f"{body}, the {label} of {position.sign}, is in a kendra")

        if reasons:
            found.append(
                _finding(
                    f"neecha_bhanga_{position.body.lower()}",
                    f"Neecha Bhanga for {position.body}",
                    "mitigation",
                    f"{position.body} is debilitated in {position.sign}, but "
                    + " and ".join(reasons)
                    + ". The debilitation is substantially cancelled.",
                    body=position.body,
                )
            )
    return found


def scan(positions: list[Position], ascendant_sign: int, strengths: dict) -> list[dict]:
    """Every yoga rule, run in order of interpretive weight."""
    lords = house_lords(ascendant_sign)
    return [
        *mahapurusha(positions),
        *raja_yogas(positions, lords),
        *dhana_yogas(positions, lords),
        *gaja_kesari(positions),
        *budhaditya(positions, strengths),
        *chandra_mangala(positions),
        *neecha_bhanga(positions),
        *kemadruma(positions),
    ]
