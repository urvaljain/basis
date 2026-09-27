"""Evaluation metrics — only things that are actually measured.

## The rule this module exists to enforce

Every number Basis displays must trace to a measurement performed here. A metric that was
not computed is reported as ``NOT_MEASURED``, never as a plausible figure, and the interface
renders that state distinctly rather than hiding the row.

This is not fastidiousness. The product's entire argument is that an AI system should be
checkable, and a fabricated quality metric would be the single most damaging thing it could
ship — it would be dishonesty *about its honesty*.

## What can be measured without a language model

More than is usually assumed, and these happen to be the metrics that matter most:

* **Citation accuracy** — does the retrieved span actually contain the governing clause?
  Ground truth is a page and a phrase from the real document, so this is exact string
  checking, not judgement.
* **Blind-spot recall and precision** — for questions whose answer lives on unreadable
  pages, is the gap reported? For questions where it does not, does the system stay quiet?
* **Caveat propagation** — does a citation drawn from repaired text or a damaged table
  carry its warning all the way to the output?
* **Repair correctness** — known corrupted strings against their known readings.
* **Latency**.

## What requires a model, and is therefore honestly unreported

* **Unsupported-claim rate** — needs generated prose to check claims against.
* **Calibration** — needs stated confidence on generated answers.
* **Cost** — no calls, no cost.

Those are marked ``NOT_MEASURED`` with the reason attached, and the harness prints why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MetricStatus(str, Enum):
    MEASURED = "measured"
    NOT_MEASURED = "not_measured"
    """Requires a capability this run did not have. Never rendered as a number."""

    NOT_APPLICABLE = "not_applicable"


@dataclass
class Metric:
    """One evaluation dimension and its result."""

    name: str
    description: str
    status: MetricStatus
    value: float | None = None
    unit: str = "%"
    numerator: int | None = None
    denominator: int | None = None
    reason_not_measured: str | None = None
    failures: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def measured(
        cls,
        name: str,
        description: str,
        numerator: int,
        denominator: int,
        *,
        unit: str = "%",
        failures: list[dict[str, Any]] | None = None,
    ) -> Metric:
        value = round(100 * numerator / denominator, 1) if denominator else 0.0
        return cls(
            name=name,
            description=description,
            status=MetricStatus.MEASURED,
            value=value,
            unit=unit,
            numerator=numerator,
            denominator=denominator,
            failures=failures or [],
        )

    @classmethod
    def unmeasured(cls, name: str, description: str, reason: str) -> Metric:
        return cls(
            name=name,
            description=description,
            status=MetricStatus.NOT_MEASURED,
            reason_not_measured=reason,
        )

    @classmethod
    def scalar(
        cls, name: str, description: str, value: float, unit: str
    ) -> Metric:
        return cls(
            name=name,
            description=description,
            status=MetricStatus.MEASURED,
            value=round(value, 1),
            unit=unit,
        )

    @property
    def display(self) -> str:
        if self.status is not MetricStatus.MEASURED or self.value is None:
            return "not measured"
        base = f"{self.value}{self.unit}"
        if self.denominator:
            base += f" ({self.numerator}/{self.denominator})"
        return base

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "display": self.display,
            "reason_not_measured": self.reason_not_measured,
            "failure_count": len(self.failures),
            "failures": self.failures[:10],
        }


@dataclass
class EvalReport:
    """The result of one evaluation run."""

    run_at: str
    mode: str
    corpus_title: str
    corpus_sha256: str
    case_count: int
    metrics: list[Metric] = field(default_factory=list)
    case_results: list[dict[str, Any]] = field(default_factory=list)

    @property
    def measured(self) -> list[Metric]:
        return [m for m in self.metrics if m.status is MetricStatus.MEASURED]

    @property
    def unmeasured(self) -> list[Metric]:
        return [m for m in self.metrics if m.status is MetricStatus.NOT_MEASURED]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_at": self.run_at,
            "mode": self.mode,
            "corpus": {"title": self.corpus_title, "sha256": self.corpus_sha256},
            "case_count": self.case_count,
            "metrics": [m.to_dict() for m in self.metrics],
            "cases": self.case_results,
        }

    def render(self) -> str:
        lines = [
            "=" * 78,
            f"BASIS EVALUATION — {self.run_at}",
            f"mode: {self.mode} | corpus: {self.corpus_title[:48]}",
            f"sha256: {self.corpus_sha256[:16]}… | cases: {self.case_count}",
            "=" * 78,
            "",
            "MEASURED",
        ]
        for m in self.measured:
            lines.append(f"  {m.name:<36s} {m.display:>18s}")
            lines.append(f"      {m.description}")
            if m.failures:
                for f in m.failures[:3]:
                    lines.append(f"      ✗ {str(f)[:96]}")
        if self.unmeasured:
            lines += ["", "NOT MEASURED — reported as such rather than estimated"]
            for m in self.unmeasured:
                lines.append(f"  {m.name:<36s} {'not measured':>18s}")
                lines.append(f"      {m.reason_not_measured}")
        lines.append("=" * 78)
        return "\n".join(lines)
