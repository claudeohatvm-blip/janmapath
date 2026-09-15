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
