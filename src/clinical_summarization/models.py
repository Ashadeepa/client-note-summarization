"""Shared data types for the pipeline.

Generator output is structured {text, source_lines} from the moment it's produced —
never prose that gets citations attached after the fact (see docs/design.md, Section 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceLine:
    line_no: int
    text: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneratedSentence:
    text: str
    source_lines: tuple[int, ...]
    section: str


@dataclass(frozen=True)
class VerifierVerdict:
    sentence: GeneratedSentence
    entailed: bool
    reason: str


@dataclass(frozen=True)
class CoverageResult:
    field: str
    satisfied: bool
    verdicts: tuple[VerifierVerdict, ...] = ()
    flag: str | None = None


@dataclass(frozen=True)
class OpenLoop:
    description: str
    order_line: int


@dataclass
class DraftSummary:
    sections: dict[str, list[VerifierVerdict]] = field(default_factory=dict)
    coverage: list[CoverageResult] = field(default_factory=list)
    open_loops: list[OpenLoop] = field(default_factory=list)

    def flags(self) -> list[str]:
        return [c.flag for c in self.coverage if c.flag]
