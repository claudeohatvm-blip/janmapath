"""Assembles a Report from a computed chart."""

from __future__ import annotations

from datetime import date

from . import narrator_ai, narrator_rules
from .schema import Report, Section


def build(chart: dict, *, use_ai: bool = False, language: str = "en") -> Report:
    """Turn engine output into a finished report.

    Narration is always written from rules first. AI rewriting, when enabled and
    configured, is applied on top and may only change wording - never a score, a
    band, or a conclusion.
    """
    readings = chart.get("readings") or {}
    sections: list[Section] = []

    if readings:
        sections.append(narrator_rules.life_section(readings["life"], chart))
        sections.append(narrator_rules.marriage_section(readings["marriage"]))
        sections.append(narrator_rules.finance_section(readings["finance"]))
        sections.append(narrator_rules.career_section(readings["career"]))
    else:
        sections.append(
            Section(
                key="life",
                title="Your Life Reading",
                summary="A full reading needs your birth time.",
                band="mixed",
                paragraphs=[
                    "Your birth time was recorded as unknown, so your ascendant "
                    "and house placements cannot be determined. Marriage, "
                    "financial and career readings are all read from houses, and "
                    "producing them without a reliable time would mean inventing "
                    "the foundation they rest on.",
                    "What can be read without a birth time is below: your Moon "
                    "sign and nakshatra, your Vimshottari dasha sequence, and the "
                    "dosha rules that are judged from the Moon rather than the "
                    "ascendant.",
                ],
                key_points=["Birth time unknown - house-based readings withheld"],
                is_free=True,
            )
        )

    sections.append(narrator_rules.dosha_section(chart["analysis"]["doshas"]))

    report = Report(
        name=chart["input"]["name"] or "Your",
        generated_on=date.today().isoformat(),
        narrator=narrator_rules.NARRATOR_ID,
        sections=sections,
    )

    if use_ai:
        report = narrator_ai.narrate(report, _findings_for_ai(chart), language)

    return report


def _findings_for_ai(chart: dict) -> dict:
    """The subset of engine output the narrator is allowed to see.

    Deliberately narrow: the model receives conclusions and the placements
    behind them, never raw degrees it might be tempted to recompute from.
    """
    return {
        "ascendant": chart.get("ascendant"),
        "planets": [
            {
                k: p[k]
                for k in ("body", "sign", "house", "nakshatra", "dignity", "retrograde")
            }
            for p in chart["planets"]
        ],
        "doshas": chart["analysis"]["doshas"],
        "yogas": chart["analysis"]["yogas"],
        "current_dasha": chart["dashas"]["vimshottari"]["current"],
        "readings": chart.get("readings", {}),
        "suppressed": chart["analysis"]["suppressed"],
    }
