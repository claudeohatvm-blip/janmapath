"""Tests for the reading layer - strength, aspects, yogas, domain analysis."""

from __future__ import annotations

from datetime import date, time

import pytest

from apps.astro.aspects import aspected_houses
from apps.astro.engine import compute_chart
from apps.astro.strength import is_combust, separation
from apps.astro.types import BirthData, Position, TimeAccuracy
from apps.astro.varga import dashamsha_sign
from apps.astro.yogas import house_lords

TRIVANDRUM = {"latitude": 8.5241, "longitude": 76.9366, "tz_id": "Asia/Kolkata"}
AS_OF = date(2026, 9, 15)


def make_birth(**overrides) -> BirthData:
    defaults = {
        "birth_date": date(1996, 4, 12),
        "birth_time": time(14, 35),
        "gender": "female",
        **TRIVANDRUM,
    }
    return BirthData(**{**defaults, **overrides})


@pytest.fixture(scope="module")
def chart():
    return compute_chart(make_birth(), as_of=AS_OF)


class TestAspects:
    def test_every_graha_aspects_the_seventh(self):
        for body in ("Sun", "Moon", "Venus", "Mercury"):
            assert aspected_houses(body, 1) == [7]

    @pytest.mark.parametrize(
        "body,expected",
        [("Mars", [4, 7, 8]), ("Jupiter", [5, 7, 9]), ("Saturn", [3, 7, 10])],
    )
    def test_special_aspects(self, body, expected):
        assert aspected_houses(body, 1) == expected

    def test_aspects_wrap_around_the_zodiac(self):
        # Jupiter in the 10th aspects the 2nd (10 + 5 - 1 = 14 -> 2).
        assert aspected_houses("Jupiter", 10) == [2, 4, 6]


class TestStrength:
    def test_separation_takes_the_short_arc(self):
        assert separation(10.0, 350.0) == pytest.approx(20.0)
        assert separation(350.0, 10.0) == pytest.approx(20.0)

    def test_sun_is_never_combust(self):
        sun = Position(
            body="Sun", longitude=100.0, sign_index=3, sign="Karka",
            degree_in_sign=10.0, nakshatra="Pushya", nakshatra_index=7, pada=1,
            retrograde=False, speed=1.0, dignity="neutral",
        )
        assert is_combust(sun, 100.0) is False

    def test_mercury_combust_within_orb(self):
        mercury = Position(
            body="Mercury", longitude=105.0, sign_index=3, sign="Karka",
            degree_in_sign=15.0, nakshatra="Ashlesha", nakshatra_index=8, pada=1,
            retrograde=False, speed=1.2, dignity="neutral",
        )
        assert is_combust(mercury, 100.0) is True      # 5 deg, orb is 14
        assert is_combust(mercury, 80.0) is False      # 25 deg

    def test_retrograde_venus_takes_the_tighter_orb(self):
        venus = Position(
            body="Venus", longitude=109.0, sign_index=3, sign="Karka",
            degree_in_sign=19.0, nakshatra="Ashlesha", nakshatra_index=8, pada=2,
            retrograde=True, speed=-0.3, dignity="neutral",
        )
        assert is_combust(venus, 100.0) is False       # 9 deg, retro orb is 8
        venus_direct = Position(**{**venus.__dict__, "retrograde": False, "speed": 1.0})
        assert is_combust(venus_direct, 100.0) is True  # 9 deg, direct orb is 10

    def test_every_graha_scored(self, chart):
        assert len(chart["strengths"]) == 9
        for entry in chart["strengths"].values():
            assert 0 <= entry["score"] <= 100
            assert entry["band"] in {"strong", "moderate", "weak"}


class TestHouseLords:
    def test_mesha_lagna_lords(self):
        lords = house_lords(0)
        assert lords[1] == "Mars"       # Mesha
        assert lords[7] == "Venus"      # Tula
        assert lords[10] == "Saturn"    # Makara

    def test_all_twelve_assigned(self):
        assert sorted(house_lords(5).keys()) == list(range(1, 13))


class TestDashamsha:
    @pytest.mark.parametrize(
        "longitude,expected_sign_index",
        [
            (0.0, 0),    # Mesha, odd sign -> starts from itself
            (3.0, 1),    # Mesha 2nd part
            (30.0, 9),   # Vrishabha, even sign -> starts from the 9th
            (33.0, 10),
        ],
    )
    def test_dashamsha_follows_the_odd_even_rule(self, longitude, expected_sign_index):
        assert dashamsha_sign(longitude) == expected_sign_index


class TestReadings:
    def test_all_four_domains_present(self, chart):
        assert set(chart["readings"]) == {"life", "marriage", "finance", "career"}

    def test_every_domain_scored_and_banded(self, chart):
        for name, reading in chart["readings"].items():
            assert 0 <= reading["score"] <= 100, name
            assert reading["band"] in {"supported", "mixed", "challenged"}, name

    def test_marriage_cites_the_seventh_house_and_karaka(self, chart):
        marriage = chart["readings"]["marriage"]
        assert marriage["seventh_house"]["house"] == 7
        assert marriage["karaka"]["body"] == "Jupiter"   # female -> husband karaka
        assert marriage["navamsa"]["seventh_sign"]

    def test_marriage_karaka_follows_gender(self):
        male = compute_chart(make_birth(gender="male"), as_of=AS_OF)
        assert male["readings"]["marriage"]["karaka"]["body"] == "Venus"

    def test_finance_covers_the_dhana_houses(self, chart):
        finance = chart["readings"]["finance"]
        assert finance["second_house"]["house"] == 2
        assert finance["eleventh_house"]["house"] == 11
        assert finance["dhana_karaka"]["body"] == "Jupiter"

    def test_life_names_the_running_period(self, chart):
        period = chart["readings"]["life"]["current_period"]
        assert period["mahadasha"] is not None
        assert isinstance(period["rules_houses"], list)

    def test_every_yoga_cites_its_evidence(self, chart):
        for yoga in chart["analysis"]["yogas"]:
            assert yoga["detail"]
            assert yoga["category"]

    def test_readings_are_deterministic(self):
        birth = make_birth()
        assert compute_chart(birth, as_of=AS_OF) == compute_chart(birth, as_of=AS_OF)
