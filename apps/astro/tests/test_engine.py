"""Engine correctness tests.

The reference-chart suite these will grow into is the highest-value test asset
in the codebase: if the charts are wrong, nothing built on top of them matters.
"""

from __future__ import annotations

from datetime import date, time

import pytest

from apps.astro.varga import dashamsha_sign, navamsa_sign as navamsa_sign_index
from apps.astro.engine import compute_chart, input_checksum
from apps.astro.ephemeris import resolve_utc
from apps.astro.types import BirthData, TimeAccuracy

TRIVANDRUM = {"latitude": 8.5241, "longitude": 76.9366, "tz_id": "Asia/Kolkata"}
AS_OF = date(2026, 9, 15)


def make_birth(**overrides) -> BirthData:
    defaults = {
        "birth_date": date(1996, 4, 12),
        "birth_time": time(14, 35),
        **TRIVANDRUM,
    }
    return BirthData(**{**defaults, **overrides})


class TestDeterminism:
    def test_identical_input_produces_identical_chart(self):
        birth = make_birth()
        first = compute_chart(birth, as_of=AS_OF)
        second = compute_chart(birth, as_of=AS_OF)
        assert first == second

    def test_checksum_is_stable_across_instances(self):
        assert input_checksum(make_birth()) == input_checksum(make_birth())

    def test_checksum_changes_with_birth_time(self):
        assert input_checksum(make_birth()) != input_checksum(
            make_birth(birth_time=time(14, 36))
        )


class TestHistoricalTimezone:
    """India observed DST in 1942-45 and used other offsets before 1955.

    A hardcoded UTC+05:30 silently produces a wrong chart for every older user.
    """

    def test_wartime_dst_offset_is_applied(self):
        wartime = resolve_utc(
            make_birth(birth_date=date(1943, 6, 15), birth_time=time(12, 0))
        )
        modern = resolve_utc(
            make_birth(birth_date=date(1996, 6, 15), birth_time=time(12, 0))
        )
        # 1943 ran on +06:30, so noon local is an hour earlier in UTC than today.
        assert wartime.hour == 5 and wartime.minute == 30
        assert modern.hour == 6 and modern.minute == 30

    def test_wartime_birth_produces_different_ascendant(self):
        with_history = compute_chart(
            make_birth(birth_date=date(1943, 6, 15), birth_time=time(12, 0)),
            as_of=AS_OF,
        )
        assert with_history["ascendant"] is not None


class TestUnknownBirthTime:
    def test_house_dependent_output_is_suppressed(self):
        chart = compute_chart(
            make_birth(birth_time=None, time_accuracy=TimeAccuracy.UNKNOWN),
            as_of=AS_OF,
        )
        assert chart["ascendant"] is None
        assert chart["houses"] == []
        assert chart["vargas"]["D9"] is None
        assert chart["vargas"]["D10"] is None
        assert chart["readings"] == {}
        assert "ascendant" in chart["analysis"]["suppressed"]
        assert all(p["house"] is None for p in chart["planets"])

    def test_dasha_still_computed_without_birth_time(self):
        chart = compute_chart(
            make_birth(birth_time=None, time_accuracy=TimeAccuracy.UNKNOWN),
            as_of=AS_OF,
        )
        assert chart["dashas"]["vimshottari"]["current"]["mahadasha"] is not None

    def test_moon_based_dosha_rules_still_fire(self):
        chart = compute_chart(
            make_birth(birth_time=None, time_accuracy=TimeAccuracy.UNKNOWN),
            as_of=AS_OF,
        )
        mangal = next(d for d in chart["analysis"]["doshas"] if d["code"] == "mangal")
        assert mangal["basis"]["house_from_moon"] is not None
        assert mangal["basis"]["flagged_from_lagna"] is None

    def test_birth_time_required_when_accuracy_is_exact(self):
        with pytest.raises(ValueError, match="birth_time is required"):
            BirthData(birth_date=date(1996, 4, 12), **TRIVANDRUM)


class TestPositions:
    def test_ketu_is_opposite_rahu(self):
        chart = compute_chart(make_birth(), as_of=AS_OF)
        bodies = {p["body"]: p for p in chart["planets"]}
        separation = (bodies["Ketu"]["longitude"] - bodies["Rahu"]["longitude"]) % 360
        assert separation == pytest.approx(180.0, abs=1e-6)

    def test_all_nine_grahas_present(self):
        chart = compute_chart(make_birth(), as_of=AS_OF)
        assert {p["body"] for p in chart["planets"]} == {
            "Sun", "Moon", "Mars", "Mercury", "Jupiter",
            "Venus", "Saturn", "Rahu", "Ketu",
        }

    def test_every_graha_lands_in_a_valid_house(self):
        chart = compute_chart(make_birth(), as_of=AS_OF)
        assert all(1 <= p["house"] <= 12 for p in chart["planets"])


class TestNavamsa:
    """The continuous-division formula must reproduce the element-based rule."""

    @pytest.mark.parametrize(
        "sign_start_degrees,expected_first_navamsa",
        [
            (0, 0),    # Mesha, movable -> starts from itself
            (30, 9),   # Vrishabha, fixed -> starts from the 9th
            (60, 6),   # Mithuna, dual -> starts from the 5th
            (90, 3),   # Karka, movable -> itself
            (120, 0),  # Simha, fixed -> 9th from Simha
            (150, 9),  # Kanya, dual -> 5th from Kanya
        ],
    )
    def test_navamsa_start_matches_tradition(
        self, sign_start_degrees, expected_first_navamsa
    ):
        assert navamsa_sign_index(sign_start_degrees) == expected_first_navamsa


class TestVimshottari:
    def test_periods_are_contiguous(self):
        chart = compute_chart(make_birth(), as_of=AS_OF)
        periods = chart["dashas"]["vimshottari"]["periods"]
        for earlier, later in zip(periods, periods[1:]):
            assert earlier["end"] == later["start"]

    def test_first_period_is_partial(self):
        chart = compute_chart(make_birth(), as_of=AS_OF)
        periods = chart["dashas"]["vimshottari"]["periods"]
        assert periods[0]["is_partial"] is True
        assert periods[1]["is_partial"] is False

    def test_antardashas_sum_to_the_mahadasha(self):
        chart = compute_chart(make_birth(), as_of=AS_OF)
        for period in chart["dashas"]["vimshottari"]["periods"]:
            total = sum(a["years"] for a in period["antardashas"])
            # Nine values each rounded to 4dp accumulate up to 4.5e-4 of drift.
            assert total == pytest.approx(period["years"], abs=1e-3)
