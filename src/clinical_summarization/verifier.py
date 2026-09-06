"""Verification pass — stubbed, but architecturally independent of the generator.

Sees only the source lines a sentence cites — never the rest of the note, and
never the generator's reasoning — so it can't rationalize a claim using
context the citation didn't actually invoke (docs/design.md, Section 2). In
production this is a separate model/model family from the generator, ideally
an NLI-style entailment checker, precisely so a shared blind spot in one
doesn't silently validate itself in the other.

The stub below approximates entailment with token overlap. It is not a real
entailment check — it exists to prove the pipeline shape, not the accuracy.
"""

from __future__ import annotations

from clinical_summarization.models import GeneratedSentence, SourceLine, VerifierVerdict

_OVERLAP_THRESHOLD = 0.5


def _tokens(text: str) -> set[str]:
    return {tok.strip(".,").lower() for tok in text.split() if tok.strip(".,")}


def verify(sentence: GeneratedSentence, cited_lines: list[SourceLine]) -> VerifierVerdict:
    """cited_lines must be exactly the lines named in sentence.source_lines —
    the verifier is never handed the full note."""
    cited_ids = {line.line_no for line in cited_lines}
    if cited_ids != set(sentence.source_lines):
        return VerifierVerdict(
            sentence=sentence,
            entailed=False,
            reason="citation mismatch: verifier was not given exactly the cited lines",
        )

    source_tokens: set[str] = set()
    for line in cited_lines:
        source_tokens |= _tokens(line.text)
    claim_tokens = _tokens(sentence.text)

    if not claim_tokens:
        return VerifierVerdict(sentence=sentence, entailed=False, reason="empty claim")

    overlap = len(claim_tokens & source_tokens) / len(claim_tokens)
    entailed = overlap >= _OVERLAP_THRESHOLD
    reason = (
        f"token overlap {overlap:.2f} >= {_OVERLAP_THRESHOLD}"
        if entailed
        else f"token overlap {overlap:.2f} below threshold {_OVERLAP_THRESHOLD}"
    )
    return VerifierVerdict(sentence=sentence, entailed=entailed, reason=reason)
