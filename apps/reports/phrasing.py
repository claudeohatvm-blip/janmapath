"""Shared vocabulary for turning findings into sentences.

Kept separate from the narrators so the rule-based and AI paths describe the
same placement with the same words.
"""

from __future__ import annotations

ORDINALS = {
    1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th",
    7: "7th", 8: "8th", 9: "9th", 10: "10th", 11: "11th", 12: "12th",
}

BAND_VERDICT = {
    "supported": "well supported",
    "mixed": "mixed, with real strengths and real friction",
    "challenged": "under strain, and asks for deliberate effort",
}

BAND_OPENER = {
    "supported": "The chart supports this area of life.",
    "mixed": "The chart gives this area both support and difficulty.",
    "challenged": "This area carries more resistance than most in your chart.",
}

# Several phrasings per band, chosen deterministically by the graha's name so
# a section never repeats one wording while the output stays reproducible.
STRENGTH_PHRASES = {
    "strong": (
        "well placed and able to deliver its results",
        "strong enough to act on its significations directly",
        "in good condition, and dependable in what it governs",
    ),
    "moderate": (
        "reasonably placed, delivering steadily rather than dramatically",
        "workable, giving its results gradually",
        "neither obstructed nor especially favoured",
    ),
    "weak": (
        "under pressure, and needing support from the rest of the chart",
        "not well supported, so its results come slowly",
        "constrained, and reliant on stronger grahas to carry it",
    ),
}


def strength_phrase(band: str | None, seed: str = "") -> str:
    options = STRENGTH_PHRASES.get(band or "moderate", STRENGTH_PHRASES["moderate"])
    return options[sum(ord(c) for c in seed) % len(options)]


def verb(items: list[str], singular: str, plural: str) -> str:
    """Agreement helper - 'Rahu aspects' but 'Saturn and Rahu aspect'."""
    return singular if len(items) == 1 else plural

DIGNITY_PHRASE = {
    "exalted": "at its strongest",
    "own": "in its own sign, comfortable and self-reliant",
    "neutral": "in neutral territory",
    "debilitated": "in its sign of weakness",
}

HOUSE_CLASS_PHRASE = {
    "kendra": "an angular house, which gives it prominence in daily life",
    "trikona": "a trine, one of the most fortunate placements available",
    "dusthana": "a difficult house, so its results tend to arrive through struggle",
    "other": "a neutral house",
}


def ordinal(n: int | None) -> str:
    return ORDINALS.get(n, str(n)) if n is not None else "an unknown"


def listing(items: list[str]) -> str:
    """Join names the way a person would say them."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])} and {items[-1]}"


def describe_placement(body: str, sign: str | None, house: int | None,
                       dignity: str | None = None) -> str:
    """'Saturn in Makara, the 7th house, in its own sign'."""
    parts = [body]
    if sign:
        parts.append(f"in {sign}")
    if house:
        parts.append(f"in the {ordinal(house)} house")
    text = " ".join(parts[:2]) + (", " + parts[2] if len(parts) > 2 else "")
    if dignity and dignity != "neutral":
        text += f", {DIGNITY_PHRASE[dignity]}"
    return text
