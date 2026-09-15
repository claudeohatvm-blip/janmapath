"""Report structure.

A report is a list of sections. Each section carries prose, a set of key points,
and the evidence rows that produced it - so every claim in the narrative can be
traced back to a placement in the chart.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Evidence:
    """One verifiable fact from the chart, shown alongside the prose."""

    label: str
    value: str


@dataclass
class Section:
    key: str
    title: str
    summary: str                                   # one-line verdict
    band: str = ""                                 # supported | mixed | challenged
    score: int | None = None
    paragraphs: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    is_free: bool = False                          # drives the paywall boundary

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    name: str
    generated_on: str
    narrator: str                                  # "rules" or a model id
    sections: list[Section] = field(default_factory=list)
    disclaimer: str = (
        "This reading is offered for guidance and reflection. It is not advice "
        "on medical, legal, or financial matters."
    )

    def section(self, key: str) -> Section | None:
        return next((s for s in self.sections if s.key == key), None)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "generated_on": self.generated_on,
            "narrator": self.narrator,
            "disclaimer": self.disclaimer,
            "sections": [s.as_dict() for s in self.sections],
        }
