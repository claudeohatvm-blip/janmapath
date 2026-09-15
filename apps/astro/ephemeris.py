"""Sidereal planetary positions via the Swiss Ephemeris.

Everything here is deterministic: identical input always produces identical
output. No AI model is involved at any point in this module, and none should
ever be introduced - these are numerical results with correct answers.
"""

from __future__ import annotations

import threading
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

from .constants import EXALTATION_SIGN, NAKSHATRAS, OWN_SIGNS, SIGNS
from .types import BirthData, Position, TimeAccuracy

# Swiss Ephemeris keeps global state (ayanamsa mode, ephemeris path), so calls
# into it are serialised. Celery workers are separate processes and contend
# rarely; gunicorn worker threads would otherwise race on set_sid_mode.
_SWE_LOCK = threading.Lock()

# Rahu is the mean lunar node in the Vedic tradition; Ketu is exactly opposite.
_BODIES: tuple[tuple[str, int], ...] = (
    ("Sun", swe.SUN),
    ("Moon", swe.MOON),
    ("Mars", swe.MARS),
    ("Mercury", swe.MERCURY),
    ("Jupiter", swe.JUPITER),
    ("Venus", swe.VENUS),
    ("Saturn", swe.SATURN),
    ("Rahu", swe.MEAN_NODE),
)

_FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED


def resolve_utc(birth: BirthData) -> datetime:
    """Convert local birth time to UTC using the zone's historical rules.

    This is the single most dangerous calculation in the engine. India observed
    DST in 1942-45 and used different local offsets before 1955, so a hardcoded
    UTC+05:30 silently produces a wrong chart for every older user. zoneinfo
    applies the offset that was actually in force on the birth date.
    """
    tz = ZoneInfo(birth.tz_id)

    # When the birth time is unknown we still need a moment to place the slow
    # bodies. Noon minimises the Moon's error across the day. Every house-based
    # finding is suppressed downstream, so this never produces a false ascendant.
    local_time = birth.birth_time if birth.birth_time is not None else time(12, 0)

    local = datetime.combine(birth.birth_date, local_time, tzinfo=tz)
    return local.astimezone(timezone.utc)


def julian_day(moment_utc: datetime) -> float:
    """Julian Day Number in Universal Time."""
    hour = (
        moment_utc.hour
        + moment_utc.minute / 60.0
        + moment_utc.second / 3600.0
        + moment_utc.microsecond / 3_600_000_000.0
    )
    return swe.julday(moment_utc.year, moment_utc.month, moment_utc.day, hour)


def division_index(longitude: float) -> int:
    """Index of the 3 deg 20 min division containing this longitude, 0-107.

    Nakshatra padas and navamsas share identical boundaries, so one division
    drives nakshatra, pada and D9 alike. Computing it once keeps all three
    mutually consistent.

    Scaled multiplication (x * 3 / 10) rather than floor division by a stored
    3.3333... constant: that constant is fractionally above 10/3, so
    `30.0 // PADA_SPAN` yields 8 where the correct answer is 9. Every exact sign
    boundary would otherwise land one division low.
    """
    return min(int((longitude % 360.0) * 3.0 / 10.0), 107)


def describe_longitude(longitude: float) -> dict:
    """Break a sidereal longitude into sign, nakshatra and pada."""
    longitude %= 360.0
    sign_index = min(int(longitude * 12.0 / 360.0), 11)
    division = division_index(longitude)
    nakshatra_index = division // 4
    pada = (division % 4) + 1
    return {
        "sign_index": sign_index,
        "sign": SIGNS[sign_index],
        "degree_in_sign": longitude % 30.0,
        "nakshatra_index": nakshatra_index,
        "nakshatra": NAKSHATRAS[nakshatra_index],
        "pada": pada,
    }


def _dignity(body: str, sign_index: int) -> str:
    exalted = EXALTATION_SIGN.get(body)
    if exalted is not None:
        if sign_index == exalted:
            return "exalted"
        if sign_index == (exalted + 6) % 12:
            return "debilitated"
    if sign_index in OWN_SIGNS.get(body, ()):
        return "own"
    return "neutral"


def compute_positions(jd_ut: float) -> tuple[list[Position], float]:
    """Sidereal positions of the nine grahas, plus the ayanamsa used.

    Returns positions without house placement; houses require the ascendant,
    which requires a reliable birth time and is applied in charts.py.
    """
    positions: list[Position] = []

    with _SWE_LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        ayanamsa = swe.get_ayanamsa_ut(jd_ut)

        for name, body_id in _BODIES:
            values, _retflag = swe.calc_ut(jd_ut, body_id, _FLAGS)
            longitude, speed = values[0] % 360.0, values[3]
            parts = describe_longitude(longitude)
            positions.append(
                Position(
                    body=name,
                    longitude=longitude,
                    retrograde=speed < 0,
                    speed=speed,
                    dignity=_dignity(name, parts["sign_index"]),
                    **parts,
                )
            )

    # Ketu is always 180 degrees from Rahu and shares its retrograde motion.
    rahu = next(p for p in positions if p.body == "Rahu")
    ketu_longitude = (rahu.longitude + 180.0) % 360.0
    ketu_parts = describe_longitude(ketu_longitude)
    positions.append(
        Position(
            body="Ketu",
            longitude=ketu_longitude,
            retrograde=rahu.retrograde,
            speed=rahu.speed,
            dignity=_dignity("Ketu", ketu_parts["sign_index"]),
            **ketu_parts,
        )
    )

    return positions, ayanamsa


def compute_ascendant(jd_ut: float, latitude: float, longitude: float) -> float:
    """Sidereal ascendant in degrees.

    Whole Sign houses ('W') are the Vedic standard: the ascendant's sign is the
    entire first house, and each following sign is the next house.
    """
    with _SWE_LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        _cusps, ascmc = swe.houses_ex(jd_ut, latitude, longitude, b"W", swe.FLG_SIDEREAL)
    return ascmc[0] % 360.0


def is_time_reliable(accuracy: TimeAccuracy) -> bool:
    """Whether house-dependent output may be trusted."""
    return accuracy is not TimeAccuracy.UNKNOWN
