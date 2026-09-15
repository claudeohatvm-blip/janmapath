"""Domain analysis: life, marriage, wealth, career.

Each function assembles the classical evidence for one area of life - the
governing bhava, its lord, its occupants, the grahas aspecting it, the natural
karaka, and the relevant divisional chart - then scores that evidence against a
fixed rubric.

The scores are transparent by design. Every finding carries the placements that
produced it, so a reader can check the conclusion against the chart instead of
taking it on trust. No narrative text is generated here; that happens later,
outside the engine.
"""

from __future__ import annotations

from .aspects import aspects_on_house
from .constants import (
    BENEFICS,
    DUSTHANA,
    HOUSE_MEANINGS,
    KENDRA,
    MALEFICS,
    MARRIAGE_KARAKA,
    SIGN_LORDS,
    SIGNS,
    TRIKONA,
)
from .types import Position
from .varga import house_of, occupants_of
from .yogas import house_lords


def _find(positions: list[Position], body: str) -> Position | None:
    return next((p for p in positions if p.body == body), None)


def _occupants(positions: list[Position], house: int) -> list[Position]:
    return [p for p in positions if p.house == house]


def _band(score: int) -> str:
    if score >= 68:
        return "supported"
    if score >= 45:
        return "mixed"
    return "challenged"


def _house_sign(ascendant_sign: int, house: int) -> int:
    return (ascendant_sign + house - 1) % 12


def examine_house(
    positions: list[Position],
    ascendant_sign: int,
    strengths: dict,
    house: int,
) -> dict:
    """The complete classical picture of one bhava."""
    sign_index = _house_sign(ascendant_sign, house)
    lord_name = SIGN_LORDS[sign_index]
    lord = _find(positions, lord_name)

    occupants = _occupants(positions, house)
    aspecting = aspects_on_house(positions, house)

    return {
        "house": house,
        "signifies": HOUSE_MEANINGS[house],
        "sign": SIGNS[sign_index],
        "lord": lord_name,
        "lord_house": lord.house if lord else None,
        "lord_sign": lord.sign if lord else None,
        "lord_dignity": lord.dignity if lord else None,
        "lord_strength": strengths.get(lord_name, {}).get("score"),
        "lord_band": strengths.get(lord_name, {}).get("band"),
        "lord_in_dusthana": (lord.house in DUSTHANA) if lord and lord.house else False,
        "occupants": [
            {
                "body": p.body,
                "nature": "benefic" if p.body in BENEFICS else "malefic",
                "dignity": p.dignity,
                "strength": strengths.get(p.body, {}).get("score"),
            }
            for p in occupants
        ],
        "aspected_by": [
            {"body": b, "nature": "benefic" if b in BENEFICS else "malefic"}
            for b in aspecting
        ],
        "benefic_count": sum(1 for p in occupants if p.body in BENEFICS)
        + sum(1 for b in aspecting if b in BENEFICS),
        "malefic_count": sum(1 for p in occupants if p.body in MALEFICS)
        + sum(1 for b in aspecting if b in MALEFICS),
    }


def _score_house(picture: dict) -> int:
    """Rubric shared by every domain, so the bands mean the same thing.

    Lord strength carries the most weight, then where the lord sits, then the
    balance of benefic and malefic influence on the bhava itself.
    """
    score = 0

    lord_strength = picture["lord_strength"] or 0
    score += int(lord_strength * 0.45)                       # up to 45

    lord_house = picture["lord_house"]
    if lord_house in DUSTHANA:
        score += 3
    elif lord_house in KENDRA or lord_house in TRIKONA:
        score += 25
    elif lord_house is not None:
        score += 15                                          # up to 25

    balance = picture["benefic_count"] - picture["malefic_count"]
    score += max(0, min(30, 15 + balance * 7))               # up to 30

    return max(0, min(100, score))


# --- Life ---------------------------------------------------------------------


def analyse_life(
    positions: list[Position],
    ascendant_sign: int,
    strengths: dict,
    yoga_findings: list[dict],
    current_dasha: dict,
) -> dict:
    """Constitution, temperament, and the theme of the period now running."""
    lagna = examine_house(positions, ascendant_sign, strengths, 1)
    moon, sun = _find(positions, "Moon"), _find(positions, "Sun")
    lords = house_lords(ascendant_sign)

    # The running mahadasha lord, and what it rules, is the single most
    # informative statement about the present phase of life.
    dasha_lord = current_dasha.get("mahadasha")
    dasha_position = _find(positions, dasha_lord) if dasha_lord else None
    ruled = [h for h, lord in lords.items() if lord == dasha_lord]

    strong = sorted(
        (s for s in strengths.values() if s["band"] == "strong"),
        key=lambda s: -s["score"],
    )
    weak = sorted(
        (s for s in strengths.values() if s["band"] == "weak"),
        key=lambda s: s["score"],
    )

    return {
        "lagna": lagna,
        "moon": {
            "sign": moon.sign if moon else None,
            "nakshatra": moon.nakshatra if moon else None,
            "house": moon.house if moon else None,
            "strength": strengths.get("Moon", {}).get("score"),
            "band": strengths.get("Moon", {}).get("band"),
        },
        "sun": {
            "sign": sun.sign if sun else None,
            "house": sun.house if sun else None,
            "strength": strengths.get("Sun", {}).get("score"),
            "band": strengths.get("Sun", {}).get("band"),
        },
        "current_period": {
            "mahadasha": dasha_lord,
            "antardasha": current_dasha.get("antardasha"),
            "lord_house": dasha_position.house if dasha_position else None,
            "lord_sign": dasha_position.sign if dasha_position else None,
            "lord_dignity": dasha_position.dignity if dasha_position else None,
            "lord_strength": strengths.get(dasha_lord, {}).get("score") if dasha_lord else None,
            "rules_houses": ruled,
            "rules_meanings": [HOUSE_MEANINGS[h] for h in ruled],
        },
        "strongest": [s["body"] for s in strong[:3]],
        "weakest": [s["body"] for s in weak[:3]],
        "yogas": [y for y in yoga_findings if y["category"] in {"strength", "status", "fortune", "intellect", "mitigation", "challenge"}],
        "score": _score_house(lagna),
        "band": _band(_score_house(lagna)),
    }


# --- Marriage -----------------------------------------------------------------


def analyse_marriage(
    positions: list[Position],
    ascendant_sign: int,
    strengths: dict,
    navamsa: dict | None,
    doshas: list[dict],
    gender: str,
) -> dict:
    """The 7th bhava, its lord, the marriage karaka, and the Navamsa."""
    seventh = examine_house(positions, ascendant_sign, strengths, 7)
    second = examine_house(positions, ascendant_sign, strengths, 2)

    karaka_name = MARRIAGE_KARAKA.get((gender or "").lower(), "Venus")
    karaka = _find(positions, karaka_name)

    # The Navamsa is the decisive divisional chart for marriage. A weak 7th in
    # D1 supported by a strong D9 7th reads as a marriage that strengthens with
    # time rather than one that fails.
    navamsa_view = None
    if navamsa is not None:
        d9_seventh_sign = (navamsa["ascendant_sign_index"] + 6) % 12
        navamsa_view = {
            "ascendant_sign": navamsa["ascendant_sign"],
            "seventh_sign": SIGNS[d9_seventh_sign],
            "seventh_lord": SIGN_LORDS[d9_seventh_sign],
            "seventh_occupants": occupants_of(navamsa, 7),
            "karaka_house": house_of(navamsa, karaka_name),
        }

    mangal = next((d for d in doshas if d["code"] == "mangal"), None)

    score = _score_house(seventh)
    # The karaka's own condition modulates the reading either way.
    karaka_score = strengths.get(karaka_name, {}).get("score", 50)
    score = int(score * 0.75 + karaka_score * 0.25)
    if mangal and mangal["present"] and not mangal["is_cancelled"]:
        score -= 10
    score = max(0, min(100, score))

    return {
        "seventh_house": seventh,
        "second_house": second,
        "karaka": {
            "body": karaka_name,
            "why": "Venus signifies the wife; Jupiter signifies the husband.",
            "sign": karaka.sign if karaka else None,
            "house": karaka.house if karaka else None,
            "dignity": karaka.dignity if karaka else None,
            "strength": karaka_score,
            "band": strengths.get(karaka_name, {}).get("band"),
            "combust": strengths.get(karaka_name, {}).get("factors", {}).get("combust"),
        },
        "navamsa": navamsa_view,
        "mangal_dosha": mangal,
        "score": score,
        "band": _band(score),
    }


# --- Wealth -------------------------------------------------------------------


def analyse_finance(
    positions: list[Position],
    ascendant_sign: int,
    strengths: dict,
    yoga_findings: list[dict],
) -> dict:
    """The dhana trikona - 2nd, 11th, 9th and 5th - plus Jupiter."""
    second = examine_house(positions, ascendant_sign, strengths, 2)    # accumulation
    eleventh = examine_house(positions, ascendant_sign, strengths, 11) # income
    ninth = examine_house(positions, ascendant_sign, strengths, 9)     # fortune
    fifth = examine_house(positions, ascendant_sign, strengths, 5)     # past merit
    twelfth = examine_house(positions, ascendant_sign, strengths, 12)  # outflow

    jupiter = _find(positions, "Jupiter")
    dhana = [y for y in yoga_findings if y["category"] == "wealth"]

    # Accumulation and income are weighted above fortune and merit; outflow is
    # informative but does not by itself reduce the capacity to earn.
    score = int(
        _score_house(second) * 0.30
        + _score_house(eleventh) * 0.30
        + _score_house(ninth) * 0.20
        + _score_house(fifth) * 0.10
        + (strengths.get("Jupiter", {}).get("score", 50)) * 0.10
    )
    score = min(100, score + min(12, 4 * len(dhana)))

    return {
        "second_house": second,
        "eleventh_house": eleventh,
        "ninth_house": ninth,
        "fifth_house": fifth,
        "twelfth_house": twelfth,
        "dhana_karaka": {
            "body": "Jupiter",
            "sign": jupiter.sign if jupiter else None,
            "house": jupiter.house if jupiter else None,
            "dignity": jupiter.dignity if jupiter else None,
            "strength": strengths.get("Jupiter", {}).get("score"),
            "band": strengths.get("Jupiter", {}).get("band"),
        },
        "dhana_yogas": dhana,
        "outflow_pressure": twelfth["malefic_count"] > twelfth["benefic_count"],
        "score": score,
        "band": _band(score),
    }


# --- Career -------------------------------------------------------------------


def analyse_career(
    positions: list[Position],
    ascendant_sign: int,
    strengths: dict,
    dashamsha: dict | None,
) -> dict:
    """The 10th bhava and the Dashamsha."""
    tenth = examine_house(positions, ascendant_sign, strengths, 10)
    sixth = examine_house(positions, ascendant_sign, strengths, 6)

    saturn = _find(positions, "Saturn")
    sun = _find(positions, "Sun")

    dashamsha_view = None
    if dashamsha is not None:
        d10_tenth_sign = (dashamsha["ascendant_sign_index"] + 9) % 12
        dashamsha_view = {
            "ascendant_sign": dashamsha["ascendant_sign"],
            "tenth_sign": SIGNS[d10_tenth_sign],
            "tenth_lord": SIGN_LORDS[d10_tenth_sign],
            "tenth_occupants": occupants_of(dashamsha, 10),
        }

    score = int(_score_house(tenth) * 0.7 + strengths.get("Saturn", {}).get("score", 50) * 0.3)

    return {
        "tenth_house": tenth,
        "sixth_house": sixth,
        "karma_karaka": {
            "body": "Saturn",
            "sign": saturn.sign if saturn else None,
            "house": saturn.house if saturn else None,
            "strength": strengths.get("Saturn", {}).get("score"),
        },
        "authority_karaka": {
            "body": "Sun",
            "sign": sun.sign if sun else None,
            "house": sun.house if sun else None,
            "strength": strengths.get("Sun", {}).get("score"),
        },
        "dashamsha": dashamsha_view,
        "score": score,
        "band": _band(score),
    }
