"""Static Jyotish reference data.

Pure data only - no computation, no I/O, no imports beyond the standard library.
"""

from __future__ import annotations

# --- Rashis (zodiac signs), sidereal, 30 degrees each -----------------------

SIGNS: tuple[str, ...] = (
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena",
)

SIGNS_EN: tuple[str, ...] = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)

SIGN_LORDS: tuple[str, ...] = (
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
)

# --- Nakshatras, 27 of 13 deg 20 min each -----------------------------------

NAKSHATRAS: tuple[str, ...] = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
)

NAKSHATRA_SPAN = 360.0 / 27.0   # 13.3333... degrees
PADA_SPAN = NAKSHATRA_SPAN / 4  # 3.3333... degrees

# --- Vimshottari dasha -------------------------------------------------------
# The 120-year cycle. Nakshatra index modulo 9 selects the starting lord.

VIMSHOTTARI_ORDER: tuple[str, ...] = (
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
)

VIMSHOTTARI_YEARS: dict[str, int] = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}

VIMSHOTTARI_TOTAL_YEARS = 120
SIDEREAL_YEAR_DAYS = 365.25

# --- Graha dignity -----------------------------------------------------------
# Sign index where each graha is exalted; debilitation is the opposite sign.

EXALTATION_SIGN: dict[str, int] = {
    "Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5,
    "Jupiter": 3, "Venus": 11, "Saturn": 6,
}

OWN_SIGNS: dict[str, tuple[int, ...]] = {
    "Sun": (4,), "Moon": (3,), "Mars": (0, 7), "Mercury": (2, 5),
    "Jupiter": (8, 11), "Venus": (1, 6), "Saturn": (9, 10),
}

# --- Dosha rules -------------------------------------------------------------
# Houses counted from Lagna in which Mars produces Mangal (Kuja) dosha.
# Northern tradition; the 2nd house is included, which some schools omit.

MANGAL_DOSHA_HOUSES: frozenset[int] = frozenset({1, 2, 4, 7, 8, 12})

# Saturn transiting these houses from the natal Moon constitutes Sade Sati.
SADE_SATI_HOUSES: frozenset[int] = frozenset({12, 1, 2})


# --- Naisargika karakas (natural significators) -----------------------------

KARAKAS: dict[str, str] = {
    "Sun": "atma, father, authority, vitality",
    "Moon": "mind, mother, emotion, the public",
    "Mars": "courage, siblings, land, energy",
    "Mercury": "intellect, speech, commerce, learning",
    "Jupiter": "wealth, children, wisdom, dharma",
    "Venus": "spouse, comfort, art, vehicles",
    "Saturn": "longevity, labour, discipline, delay",
    "Rahu": "ambition, foreign, obsession",
    "Ketu": "detachment, moksha, past karma",
}

# The karaka for the marriage partner differs by the native's gender: Venus
# signifies the wife, Jupiter the husband. Both are read; the primary one is
# weighted more heavily.
MARRIAGE_KARAKA: dict[str, str] = {"male": "Venus", "female": "Jupiter"}

BENEFICS: frozenset[str] = frozenset({"Jupiter", "Venus", "Moon", "Mercury"})
MALEFICS: frozenset[str] = frozenset({"Sun", "Mars", "Saturn", "Rahu", "Ketu"})

# --- Bhava classification ----------------------------------------------------

KENDRA: frozenset[int] = frozenset({1, 4, 7, 10})       # angular, strong
TRIKONA: frozenset[int] = frozenset({1, 5, 9})          # trinal, auspicious
DUSTHANA: frozenset[int] = frozenset({6, 8, 12})        # difficult
UPACHAYA: frozenset[int] = frozenset({3, 6, 10, 11})    # improve over time
MARAKA: frozenset[int] = frozenset({2, 7})              # death-inflicting

HOUSE_MEANINGS: dict[int, str] = {
    1: "self, body, temperament",
    2: "accumulated wealth, family, speech",
    3: "siblings, courage, initiative",
    4: "mother, home, property, inner peace",
    5: "children, intelligence, past merit",
    6: "debts, disease, adversaries, service",
    7: "marriage, partnership, the spouse",
    8: "longevity, upheaval, inheritance, the hidden",
    9: "fortune, dharma, father, higher learning",
    10: "career, status, public action",
    11: "gains, income, elder siblings, fulfilment of desire",
    12: "expenditure, loss, foreign lands, liberation",
}

# --- Combustion (asta) -------------------------------------------------------
# Maximum separation from the Sun at which a graha is burnt. Mercury and Venus
# take a tighter orb when retrograde.

COMBUSTION_ORB: dict[str, float] = {
    "Moon": 12.0, "Mars": 17.0, "Mercury": 14.0,
    "Jupiter": 11.0, "Venus": 10.0, "Saturn": 15.0,
}
COMBUSTION_ORB_RETROGRADE: dict[str, float] = {"Mercury": 12.0, "Venus": 8.0}

# --- Panch Mahapurusha yogas -------------------------------------------------
# Formed when the graha sits in its own or exaltation sign AND in a kendra
# from the Lagna. Among the most reliably cited yogas in Parashari texts.

MAHAPURUSHA_YOGAS: dict[str, str] = {
    "Mars": "Ruchaka",
    "Mercury": "Bhadra",
    "Jupiter": "Hamsa",
    "Venus": "Malavya",
    "Saturn": "Sasa",
}

# --- Divisional charts -------------------------------------------------------

VARGA_DIVISIONS: dict[str, int] = {"D1": 1, "D9": 9, "D10": 10}
