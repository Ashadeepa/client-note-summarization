"""Coverage checker — deterministic, not a model call.

Walks REQUIRED_FIELDS and confirms each one either has at least one verified
citation or is explicitly flagged. This is the hard gate that turns "usually
cites things" into "never ships an unsupported claim" (docs/design.md,
Section 2) — it must stay a plain code check, never delegated to a model.
"""

from __future__ import annotations

from clinical_summarization.models import CoverageResult, VerifierVerdict
from clinical_summarization.schema import INSUFFICIENT_SOURCE_FLAG, REQUIRED_FIELDS


def check_coverage(
    verdicts_by_section: dict[str, list[VerifierVerdict]],
) -> list[CoverageResult]:
    results: list[CoverageResult] = []
    for field in REQUIRED_FIELDS:
        section_verdicts = verdicts_by_section.get(field, [])
        entailed = tuple(v for v in section_verdicts if v.entailed)
        if entailed:
            results.append(CoverageResult(field=field, satisfied=True, verdicts=entailed))
        else:
            results.append(
                CoverageResult(
                    field=field,
                    satisfied=False,
                    verdicts=tuple(section_verdicts),
                    flag=f"{field}: {INSUFFICIENT_SOURCE_FLAG}",
                )
            )
    return results
