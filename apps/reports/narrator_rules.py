"""Deterministic narration.

Turns engine findings into readable prose using fixed rules. No API key, no
network, no model - the report works fully without any AI configured, and the
same chart always produces the same words.

The AI narrator in `narrator_ai.py` is an optional upgrade for fluency and for
languages other than English. It never changes a conclusion, only the wording.
"""

from __future__ import annotations

from apps.astro.constants import HOUSE_MEANINGS

from .phrasing import (
    BAND_OPENER,
    BAND_VERDICT,
    describe_placement,
    listing,
    ordinal,
    strength_phrase,
    verb,
)
from .schema import Evidence, Section

NARRATOR_ID = "rules"


def _house_evidence(picture: dict, label_prefix: str = "") -> list[Evidence]:
    prefix = f"{label_prefix} " if label_prefix else ""
    rows = [
        Evidence(f"{prefix}House", f"{ordinal(picture['house'])} - {picture['signifies']}"),
        Evidence(f"{prefix}Sign", picture["sign"]),
        Evidence(
            f"{prefix}Lord",
            f"{picture['lord']} in the {ordinal(picture['lord_house'])} house"
            f" ({picture['lord_sign']}, {picture['lord_dignity']})",
        ),
    ]
    if picture["occupants"]:
        rows.append(
            Evidence(
                f"{prefix}Occupied by",
                listing([o["body"] for o in picture["occupants"]]),
            )
        )
    if picture["aspected_by"]:
        rows.append(
            Evidence(
                f"{prefix}Aspected by",
                listing([a["body"] for a in picture["aspected_by"]]),
            )
        )
    return rows


def _describe_house_condition(picture: dict, subject: str) -> str:
    """One paragraph on a bhava, its lord, occupants and aspects."""
    lord_band = picture["lord_band"] or "moderate"
    sentences = [
        f"{subject} is read from the {ordinal(picture['house'])} house, which falls "
        f"in {picture['sign']} and is ruled by {picture['lord']}."
    ]

    lord_house = picture["lord_house"]
    lord_in_own_house = lord_house == picture["house"]
    if lord_house:
        sentences.append(
            (
                f"{picture['lord']} occupies its own house here, "
                f"{strength_phrase(lord_band, picture['lord'])}."
                if lord_in_own_house
                else f"{picture['lord']} sits in the {ordinal(lord_house)} house "
                f"({HOUSE_MEANINGS[lord_house]}), {strength_phrase(lord_band, picture['lord'])}."
            )
        )
        if picture["lord_in_dusthana"]:
            sentences.append(
                "Because that lord occupies a difficult house, results in this "
                "area tend to come later than expected and after some effort, "
                "rather than easily."
            )

    occupants = picture["occupants"]
    if occupants:
        # The lord sitting in its own house is already stated above.
        benefics = [
            o["body"] for o in occupants
            if o["nature"] == "benefic" and not (lord_in_own_house and o["body"] == picture["lord"])
        ]
        malefics = [
            o["body"] for o in occupants
            if o["nature"] == "malefic" and not (lord_in_own_house and o["body"] == picture["lord"])
        ]
        if benefics:
            sentences.append(
                f"{listing(benefics)} {verb(benefics, 'occupies', 'occupy')} "
                "the house directly, which protects and softens it."
            )
        if malefics:
            sentences.append(
                f"{listing(malefics)} {verb(malefics, 'sits', 'sit')} there "
                "as well, adding pressure and demanding maturity before the house "
                "yields its best."
            )
    else:
        sentences.append(
            "No graha occupies the house itself, so its lord and the grahas "
            "aspecting it carry the reading."
        )

    aspects = picture["aspected_by"]
    if aspects:
        benefic_aspects = [a["body"] for a in aspects if a["nature"] == "benefic"]
        malefic_aspects = [a["body"] for a in aspects if a["nature"] == "malefic"]
        if benefic_aspects:
            sentences.append(
                f"{listing(benefic_aspects)} "
                f"{verb(benefic_aspects, 'casts', 'cast')} a supportive drishti on it."
            )
        if malefic_aspects:
            sentences.append(
                f"{listing(malefic_aspects)} also "
                f"{verb(malefic_aspects, 'aspects', 'aspect')} the house, which keeps "
                "the area from being entirely smooth."
            )

    return " ".join(sentences)


# --- Life ---------------------------------------------------------------------


def life_section(reading: dict, chart: dict) -> Section:
    lagna = reading["lagna"]
    moon, sun = reading["moon"], reading["sun"]
    period = reading["current_period"]
    ascendant = chart["ascendant"]

    paragraphs = [
        f"Your ascendant is {ascendant['sign']}, rising at "
        f"{ascendant['degree_in_sign']:.1f} degrees in {ascendant['nakshatra']}. "
        f"{ascendant['lord']} rules your chart, and its condition colours "
        f"everything else in it. "
        + _describe_house_condition(lagna, "Your constitution"),

        f"The Moon governs the mind. Yours is in {moon['sign']}, in the "
        f"{ordinal(moon['house'])} house, in the nakshatra {moon['nakshatra']}, "
        f"and reads as {strength_phrase(moon['band'], 'Moon')}. "
        f"The Sun, which carries vitality and sense of self, occupies "
        f"{sun['sign']} in the {ordinal(sun['house'])} house.",
    ]

    if reading["strongest"]:
        paragraphs.append(
            f"The strongest grahas in your chart are {listing(reading['strongest'])}. "
            f"These are the faculties that work for you most reliably. "
            + (
                f"{listing(reading['weakest'])} carry the least support, and the "
                "areas they govern ask for more conscious attention."
                if reading["weakest"]
                else ""
            )
        )

    if period["mahadasha"]:
        ruled = period["rules_houses"]
        paragraphs.append(
            f"You are currently running the {period['mahadasha']} mahadasha"
            + (
                f", with {period['antardasha']} as the sub-period"
                if period["antardasha"]
                else ""
            )
            + f". {period['mahadasha']} sits in your {ordinal(period['lord_house'])} "
            f"house in {period['lord_sign']}"
            + (
                f" and rules the {listing([ordinal(h) for h in ruled])} "
                f"{'house' if len(ruled) == 1 else 'houses'}"
                if ruled
                else ""
            )
            + ". "
            + (
                "That is the practical theme of this period: "
                + listing(period["rules_meanings"])
                + "."
                if period["rules_meanings"]
                else ""
            )
        )

    yogas = reading["yogas"]
    if yogas:
        paragraphs.append(
            "Your chart carries "
            + listing([y["name"] for y in yogas])
            + ". "
            + " ".join(y["detail"] for y in yogas[:3])
        )

    key_points = [
        f"{ascendant['sign']} ascendant, ruled by {ascendant['lord']}",
        f"Moon in {moon['sign']} ({moon['nakshatra']})",
    ]
    if period["mahadasha"]:
        key_points.append(f"Running {period['mahadasha']} mahadasha")
    if yogas:
        key_points.append(f"{len(yogas)} yoga{'s' if len(yogas) != 1 else ''} present")

    return Section(
        key="life",
        title="Your Life Reading",
        summary=f"Your chart reads as {BAND_VERDICT[reading['band']]}.",
        band=reading["band"],
        score=reading["score"],
        paragraphs=paragraphs,
        key_points=key_points,
        evidence=[
            Evidence("Ascendant", f"{ascendant['sign']} {ascendant['degree_in_sign']:.2f}"),
            Evidence("Ascendant lord", f"{ascendant['lord']} in the {ordinal(lagna['lord_house'])} house"),
            Evidence("Moon", f"{moon['sign']}, {moon['nakshatra']}, {ordinal(moon['house'])} house"),
            Evidence("Current period", f"{period['mahadasha']} / {period['antardasha']}"),
        ],
        is_free=True,
    )


# --- Marriage -----------------------------------------------------------------


def marriage_section(reading: dict) -> Section:
    seventh = reading["seventh_house"]
    karaka = reading["karaka"]
    navamsa = reading["navamsa"]
    mangal = reading["mangal_dosha"]

    paragraphs = [
        BAND_OPENER[reading["band"]]
        + " "
        + _describe_house_condition(seventh, "Marriage"),

        f"{karaka['body']} is the natural significator of your partner - "
        f"{karaka['why']} It stands "
        f"{describe_placement(karaka['body'], karaka['sign'], karaka['house'], karaka['dignity']).removeprefix(karaka['body'] + ' ')}, "
        f"reading as {strength_phrase(karaka['band'], karaka['body'])}."
        + (
            " It is also combust, close enough to the Sun that its significations "
            "are partly obscured - partnership matters may take longer to become "
            "clear than you would like."
            if karaka["combust"]
            else ""
        ),
    ]

    if navamsa:
        occupants = navamsa["seventh_occupants"]
        paragraphs.append(
            "The Navamsa, the divisional chart that carries the deepest reading on "
            f"marriage, rises in {navamsa['ascendant_sign']}. Its 7th house falls in "
            f"{navamsa['seventh_sign']}, ruled by {navamsa['seventh_lord']}"
            + (
                f", with {listing(occupants)} placed there"
                if occupants
                else ", with no graha placed there"
            )
            + ". A marriage reading that differs between the birth chart and the "
            "Navamsa usually means the relationship changes character over time "
            "rather than simply succeeding or failing."
        )

    if mangal:
        if mangal["present"] and not mangal["is_cancelled"]:
            basis = mangal["basis"]
            paragraphs.append(
                f"Mangal dosha is present. Mars sits in {basis['mars_sign']}"
                + (
                    f", the {ordinal(basis['house_from_lagna'])} house from your ascendant"
                    if basis["house_from_lagna"]
                    else ""
                )
                + f" and the {ordinal(basis['house_from_moon'])} from your Moon. "
                "Traditionally this indicates friction in the early years of "
                "marriage and a partner match that needs care. It is a well-known "
                "condition with well-known remedies, and it is routinely offset "
                "when the prospective partner's chart carries the same placement."
            )
        elif mangal["present"] and mangal["is_cancelled"]:
            paragraphs.append(
                f"Mangal dosha is technically present but cancelled: Mars is in its "
                f"{mangal['basis']['mars_dignity']} sign, which classical texts hold "
                "to neutralise the affliction. It should not be treated as an "
                "obstacle to marriage."
            )
        else:
            paragraphs.append(
                "Mangal dosha is not present in your chart. Mars sits in "
                f"{mangal['basis']['mars_sign']}, clear of the houses that produce it."
            )

    key_points = [
        f"7th house in {seventh['sign']}, ruled by {seventh['lord']}",
        f"{seventh['lord']} placed in the {ordinal(seventh['lord_house'])} house",
        f"{karaka['body']} as partner karaka, in {karaka['sign']}",
    ]
    if mangal:
        key_points.append(
            "Mangal dosha present" if mangal["present"] and not mangal["is_cancelled"]
            else "Mangal dosha cancelled" if mangal["present"]
            else "No Mangal dosha"
        )

    return Section(
        key="marriage",
        title="Marriage and Partnership",
        summary=f"Marriage in your chart reads as {BAND_VERDICT[reading['band']]}.",
        band=reading["band"],
        score=reading["score"],
        paragraphs=paragraphs,
        key_points=key_points,
        evidence=_house_evidence(seventh, "7th")
        + [
            Evidence("Partner karaka", f"{karaka['body']} in {karaka['sign']}, {ordinal(karaka['house'])} house"),
            *(
                [Evidence("Navamsa 7th", f"{navamsa['seventh_sign']}, ruled by {navamsa['seventh_lord']}")]
                if navamsa else []
            ),
        ],
    )


# --- Finance ------------------------------------------------------------------


def finance_section(reading: dict) -> Section:
    second, eleventh = reading["second_house"], reading["eleventh_house"]
    ninth, twelfth = reading["ninth_house"], reading["twelfth_house"]
    jupiter = reading["dhana_karaka"]
    dhana = reading["dhana_yogas"]

    paragraphs = [
        BAND_OPENER[reading["band"]]
        + " Wealth is read from two bhavas working together - the 2nd and the 11th. "
        + _describe_house_condition(second, "What you accumulate and keep"),

        _describe_house_condition(eleventh, "What comes in"),

        f"The 9th house of fortune falls in {ninth['sign']}, ruled by {ninth['lord']} "
        f"from the {ordinal(ninth['lord_house'])} house. Jupiter, the natural "
        f"significator of wealth, stands "
        f"{describe_placement('Jupiter', jupiter['sign'], jupiter['house'], jupiter['dignity']).removeprefix('Jupiter ')} "
        f"and reads as {strength_phrase(jupiter['band'], 'Jupiter')}.",
    ]

    if dhana:
        paragraphs.append(
            "Your chart carries "
            + listing([y["name"] for y in dhana])
            + " - specific wealth combinations formed when the lords of the "
            "money houses connect. "
            + " ".join(y["detail"] for y in dhana[:3])
            + " These tend to activate during the dasha periods of the grahas involved."
        )
    else:
        paragraphs.append(
            "No classical Dhana Yoga is formed in your chart. That is not a "
            "prediction of scarcity - most charts do not carry one. It means "
            "financial growth is likely to follow steady effort and the strength "
            "of the money houses themselves, rather than arriving through a single "
            "fortunate combination."
        )

    if reading["outflow_pressure"]:
        paragraphs.append(
            f"The 12th house of expenditure, in {twelfth['sign']}, carries more "
            "difficult influence than supportive. Outflow deserves conscious "
            "management; the capacity to earn is read separately and is not "
            "reduced by this."
        )

    return Section(
        key="finance",
        title="Financial Forecast",
        summary=f"Your financial indications read as {BAND_VERDICT[reading['band']]}.",
        band=reading["band"],
        score=reading["score"],
        paragraphs=paragraphs,
        key_points=[
            f"2nd house in {second['sign']}, ruled by {second['lord']}",
            f"11th house in {eleventh['sign']}, ruled by {eleventh['lord']}",
            f"Jupiter in {jupiter['sign']}, {ordinal(jupiter['house'])} house",
            f"{len(dhana)} Dhana Yoga{'s' if len(dhana) != 1 else ''} present",
        ],
        evidence=_house_evidence(second, "2nd") + _house_evidence(eleventh, "11th"),
    )


# --- Career -------------------------------------------------------------------


def career_section(reading: dict) -> Section:
    tenth = reading["tenth_house"]
    saturn, sun = reading["karma_karaka"], reading["authority_karaka"]
    dashamsha = reading["dashamsha"]

    paragraphs = [
        BAND_OPENER[reading["band"]]
        + " "
        + _describe_house_condition(tenth, "Your career and public standing"),

        f"Saturn carries the significance of work and sustained effort; yours is in "
        f"{saturn['sign']}, the {ordinal(saturn['house'])} house. The Sun, which "
        f"governs authority and recognition, is in {sun['sign']}, the "
        f"{ordinal(sun['house'])} house.",
    ]

    if dashamsha:
        occupants = dashamsha["tenth_occupants"]
        paragraphs.append(
            f"The Dashamsha, the divisional chart read specifically for profession, "
            f"rises in {dashamsha['ascendant_sign']}. Its 10th house falls in "
            f"{dashamsha['tenth_sign']}, ruled by {dashamsha['tenth_lord']}"
            + (f", with {listing(occupants)} placed there." if occupants else ".")
        )

    return Section(
        key="career",
        title="Career and Work",
        summary=f"Your career indications read as {BAND_VERDICT[reading['band']]}.",
        band=reading["band"],
        score=reading["score"],
        paragraphs=paragraphs,
        key_points=[
            f"10th house in {tenth['sign']}, ruled by {tenth['lord']}",
            f"{tenth['lord']} in the {ordinal(tenth['lord_house'])} house",
            f"Saturn in {saturn['sign']}",
        ],
        evidence=_house_evidence(tenth, "10th"),
    )


# --- Doshas -------------------------------------------------------------------

_REMEDIES = {
    "mangal": [
        "Recite the Hanuman Chalisa on Tuesdays.",
        "Offer red lentils or red cloth at a Hanuman or Kartikeya temple.",
        "Where both charts carry the same placement, the affliction is "
        "traditionally held to cancel - this is checked during matching.",
    ],
    "kaal_sarp": [
        "Perform Kaal Sarp shanti at Trimbakeshwar or another recognised kshetra.",
        "Recite the Maha Mrityunjaya mantra regularly.",
        "Offer water and milk at a Shiva temple on Nag Panchami.",
    ],
    "sade_sati": [
        "Recite the Shani stotra or Hanuman Chalisa on Saturdays.",
        "Offer sesame oil at a Shani or Hanuman temple.",
        "Keep commitments carefully during this period; Saturn rewards "
        "consistency and penalises shortcuts.",
    ],
}


def dosha_section(doshas: list[dict]) -> Section:
    found = [d for d in doshas if d["present"]]
    cancelled = [d for d in doshas if d["present"] and d["is_cancelled"]]
    active = [d for d in found if not d["is_cancelled"]]

    if not found:
        summary = "No dosha is active in your chart."
        paragraphs = [
            "All three doshas scanned - Mangal, Kaal Sarp and Sade Sati - are "
            "absent from your chart. This is a clean result and needs no remedy."
        ]
    else:
        summary = (
            f"{len(active)} active dosha{'s' if len(active) != 1 else ''} found"
            + (f", {len(cancelled)} cancelled" if cancelled else "")
            + "."
        )
        paragraphs = [
            "A dosha is a specific affliction defined by placement, not a verdict "
            "on your life. Each one below states the placement that produced it, "
            "so you can verify the finding rather than take it on trust."
        ]

    key_points = []
    for dosha in doshas:
        basis = dosha["basis"]
        if dosha["code"] == "mangal":
            detail = (
                f"Mars in {basis['mars_sign']}, "
                f"{ordinal(basis['house_from_moon'])} house from the Moon"
                + (
                    f" and {ordinal(basis['house_from_lagna'])} from the ascendant"
                    if basis.get("house_from_lagna")
                    else ""
                )
            )
        elif dosha["code"] == "kaal_sarp":
            detail = f"Rahu in {basis['rahu_sign']}, Ketu in {basis['ketu_sign']}"
        else:
            detail = (
                f"Saturn transiting {basis.get('saturn_transit_sign')}, "
                f"{ordinal(basis.get('house_from_moon'))} from natal Moon in "
                f"{basis.get('natal_moon_sign')}"
            )

        state = (
            "cancelled" if dosha["is_cancelled"]
            else dosha["severity"] if dosha["present"]
            else "not present"
        )
        key_points.append(f"{dosha['name']}: {state}")
        paragraphs.append(f"**{dosha['name']}** - {state}. {detail}.")

        if dosha["present"] and not dosha["is_cancelled"]:
            for remedy in _REMEDIES.get(dosha["code"], []):
                paragraphs.append(f"    {remedy}")

    return Section(
        key="doshas",
        title="Doshas and Remedies",
        summary=summary,
        band="challenged" if active else "supported",
        score=None,
        paragraphs=paragraphs,
        key_points=key_points,
        evidence=[
            Evidence(
                d["name"],
                "cancelled" if d["is_cancelled"] else d["severity"],
            )
            for d in doshas
        ],
    )
