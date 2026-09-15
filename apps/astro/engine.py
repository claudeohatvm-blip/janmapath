"""Top-level chart computation.

The single public entry point for the engine. Pure: identical input always
produces identical output, there is no I/O, and no Django import appears
anywhere beneath this module.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import date

from . import charts, dasha, dosha
from .ephemeris import (
    compute_ascendant,
    compute_positions,
    is_time_reliable,
    julian_day,
    resolve_utc,
)
from .types import BirthData, Stage, TimeAccuracy

ENGINE_VERSION = "0.1.0"
AYANAMSA = "lahiri"

StageCallback = Callable[[Stage, int, int], None]

_STAGES: tuple[Stage, ...] = (
    Stage.RESOLVING_TIME,
    Stage.PLANETARY,
    Stage.CHARTS,
    Stage.DASHA,
    Stage.DOSHA,
    Stage.ASSEMBLING,
)


def input_checksum(birth: BirthData) -> str:
    """Stable hash of the inputs that determine a chart.

    Paired with engine_version and ayanamsa this makes recomputation idempotent:
    the same person's chart is only ever computed once per engine version.
    """
    payload = json.dumps(
        {
            "date": birth.birth_date.isoformat(),
            "time": birth.birth_time.isoformat() if birth.birth_time else None,
            "accuracy": birth.time_accuracy.value,
            "lat": round(birth.latitude, 6),
            "lon": round(birth.longitude, 6),
            "tz": birth.tz_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_chart(
    birth: BirthData,
    *,
    as_of: date | None = None,
    on_stage: StageCallback | None = None,
) -> dict:
    """Compute a complete Vedic chart.

    `on_stage` is invoked as each stage genuinely completes. The progress screen
    reports real work, not a decorative timer.
    """
    as_of = as_of or date.today()
    total = len(_STAGES)

    def done(stage: Stage) -> None:
        if on_stage is not None:
            on_stage(stage, _STAGES.index(stage) + 1, total)

    # 1. Birth moment, in UTC, using the offset actually in force on that date.
    moment_utc = resolve_utc(birth)
    jd = julian_day(moment_utc)
    done(Stage.RESOLVING_TIME)

    # 2. Sidereal graha positions.
    positions, ayanamsa_value = compute_positions(jd)
    done(Stage.PLANETARY)

    # 3. Houses and divisional charts, only where the birth time supports them.
    time_reliable = is_time_reliable(birth.time_accuracy)
    suppressed: list[str] = []

    if time_reliable:
        ascendant = compute_ascendant(jd, birth.latitude, birth.longitude)
        positions = charts.assign_houses(positions, ascendant)
        ascendant_info = charts.describe_ascendant(ascendant)
        house_list = charts.build_houses(ascendant, positions)
        navamsa = charts.build_navamsa(positions, ascendant)
    else:
        ascendant = None
        ascendant_info = None
        house_list = []
        navamsa = None
        suppressed = [
            "ascendant",
            "houses",
            "navamsa",
            "house_based_dosha_rules",
        ]
    done(Stage.CHARTS)

    # 4. Vimshottari dasha - driven by the Moon, so it survives an unknown time.
    moon = next(p for p in positions if p.body == "Moon")
    vimshottari = dasha.compute_vimshottari(moon, birth.birth_date, as_of=as_of)
    done(Stage.DASHA)

    # 5. Doshas. Sade Sati needs Saturn's position now, not at birth.
    transit_jd = julian_day(
        resolve_utc(
            BirthData(
                birth_date=as_of,
                birth_time=birth.birth_time or None,
                time_accuracy=TimeAccuracy.UNKNOWN,
                latitude=birth.latitude,
                longitude=birth.longitude,
                tz_id=birth.tz_id,
            )
        )
    )
    transit_positions, _ = compute_positions(transit_jd)
    saturn_transit = next(p for p in transit_positions if p.body == "Saturn")
    findings = dosha.scan(positions, birth.time_accuracy, saturn_transit.sign_index)
    done(Stage.DOSHA)

    # 6. Assemble.
    chart = {
        "engine": {
            "version": ENGINE_VERSION,
            "ayanamsa": AYANAMSA,
            "ayanamsa_value": round(ayanamsa_value, 6),
            "input_checksum": input_checksum(birth),
        },
        "input": {
            "name": birth.name,
            "gender": birth.gender,
            "birth_date": birth.birth_date.isoformat(),
            "birth_time": birth.birth_time.isoformat() if birth.birth_time else None,
            "time_accuracy": birth.time_accuracy.value,
            "latitude": birth.latitude,
            "longitude": birth.longitude,
            "tz_id": birth.tz_id,
            "utc_datetime": moment_utc.isoformat(),
            "julian_day": round(jd, 6),
        },
        "ascendant": ascendant_info,
        "planets": [p.as_dict() for p in positions],
        "houses": house_list,
        "navamsa": navamsa,
        "dashas": {"vimshottari": vimshottari},
        "analysis": {
            "doshas": findings,
            "doshas_found": [f["code"] for f in findings if f["present"]],
            "suppressed": suppressed,
        },
        "transits": {
            "as_of": as_of.isoformat(),
            "saturn_sign": saturn_transit.sign,
        },
    }
    done(Stage.ASSEMBLING)
    return chart
