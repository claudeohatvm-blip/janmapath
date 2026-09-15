"""Input and output value types for the astrology engine.

Deliberately framework-free: these are plain dataclasses and enums so the engine
can be unit-tested with no database, no settings module, and no Django import.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from enum import Enum


class TimeAccuracy(str, Enum):
    """How reliable the user's stated birth time is.

    Many users genuinely do not know their birth time. Rather than silently
    defaulting to noon and emitting an ascendant we have no basis for, the
    engine records the accuracy and suppresses every house-dependent finding
    when it is UNKNOWN.
    """

    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BirthData:
    """Everything the engine needs, and nothing it does not.

    Latitude, longitude and tz_id are passed in already resolved. Geocoding is
    I/O and therefore lives outside this module.
    """

    birth_date: date
    latitude: float
    longitude: float
    tz_id: str
    birth_time: time | None = None
    time_accuracy: TimeAccuracy = TimeAccuracy.EXACT
    name: str = ""
    gender: str = ""
    place_name: str = ""

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"latitude out of range: {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"longitude out of range: {self.longitude}")
        if self.time_accuracy is not TimeAccuracy.UNKNOWN and self.birth_time is None:
            raise ValueError(
                f"birth_time is required when time_accuracy is {self.time_accuracy.value}"
            )


@dataclass(frozen=True)
class Position:
    """A graha's position at a moment, in the sidereal zodiac."""

    body: str
    longitude: float          # 0-360, sidereal
    sign_index: int           # 0-11
    sign: str
    degree_in_sign: float
    nakshatra: str
    nakshatra_index: int      # 0-26
    pada: int                 # 1-4
    retrograde: bool
    speed: float              # degrees per day
    dignity: str              # exalted | debilitated | own | neutral
    house: int | None = None  # None when the birth time is unknown

    def as_dict(self) -> dict:
        return {
            "body": self.body,
            "longitude": round(self.longitude, 4),
            "sign": self.sign,
            "sign_index": self.sign_index,
            "degree_in_sign": round(self.degree_in_sign, 4),
            "nakshatra": self.nakshatra,
            "pada": self.pada,
            "retrograde": self.retrograde,
            "speed": round(self.speed, 6),
            "dignity": self.dignity,
            "house": self.house,
        }


class Stage(str, Enum):
    """Real stages of the computation, streamed to the progress screen.

    These are emitted as each step genuinely completes. They are not a
    decorative timer.
    """

    RESOLVING_TIME = "Resolving your birth moment"
    PLANETARY = "Computing planetary longitudes"
    CHARTS = "Casting Rashi, Navamsa and Dashamsha"
    STRENGTH = "Weighing the strength of each graha"
    DASHA = "Running your Vimshottari dasha"
    YOGAS = "Searching for yogas in your chart"
    DOSHA = "Scanning for doshas"
    ANALYSIS = "Reading life, marriage, wealth and career"
    ASSEMBLING = "Assembling your report"
