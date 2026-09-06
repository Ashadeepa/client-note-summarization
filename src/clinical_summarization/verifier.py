"""Verification pass — architecturally independent of the generator.

Sees only the source lines a sentence cites — never the rest of the note, and
never the generator's reasoning — so it can't rationalize a claim using
context the citation didn't actually invoke (docs/design.md, Section 2). In
production this is a separate model/model family from the generator, so a
shared blind spot in one doesn't silently validate itself in the other; the
live verifier here defaults to a different model than `LLMGenerator`.

`stub_verify` approximates entailment with token overlap — a deterministic,
offline stand-in with the same signature as `LLMVerifier.verify`, used in
tests and as the default backend.
"""

from __future__ import annotations

from pydantic import BaseModel

from clinical_summarization.models import GeneratedSentence, SourceLine, VerifierVerdict

DEFAULT_VERIFIER_MODEL = "claude-sonnet-5"

_CITATION_MISMATCH_REASON = "citation mismatch: verifier was not given exactly the cited lines"

_SYSTEM_PROMPT = (
    "You check whether a claim is fully entailed by ONLY the source lines given "
    "below. You have no access to the rest of the clinical note. If the claim "
    "adds, changes, generalizes, or infers anything the lines don't literally "
    "state, mark it not entailed."
)

_OVERLAP_THRESHOLD = 0.5


class _EntailmentVerdict(BaseModel):
    entailed: bool
    reason: str


def _tokens(text: str) -> set[str]:
    return {tok.strip(".,").lower() for tok in text.split() if tok.strip(".,")}


def _check_citation(sentence: GeneratedSentence, cited_lines: list[SourceLine]) -> bool:
    """cited_lines must be exactly the lines named in sentence.source_lines —
    the verifier is never handed the full note."""
    return {line.line_no for line in cited_lines} == set(sentence.source_lines)


def stub_verify(sentence: GeneratedSentence, cited_lines: list[SourceLine]) -> VerifierVerdict:
    if not _check_citation(sentence, cited_lines):
        return VerifierVerdict(sentence=sentence, entailed=False, reason=_CITATION_MISMATCH_REASON)

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


class LLMVerifier:
    """Real verifier backend (Anthropic Claude). Defaults to a different
    model than `LLMGenerator` by design. Requires `pip install anthropic`
    and an ANTHROPIC_API_KEY (or another credential source the SDK
    resolves)."""

    def __init__(self, client=None, model: str = DEFAULT_VERIFIER_MODEL):
        import anthropic

        self.client = client or anthropic.Anthropic()
        self.model = model

    def verify(self, sentence: GeneratedSentence, cited_lines: list[SourceLine]) -> VerifierVerdict:
        if not _check_citation(sentence, cited_lines):
            return VerifierVerdict(sentence=sentence, entailed=False, reason=_CITATION_MISMATCH_REASON)

        source_block = "\n".join(f"line {line.line_no}: {line.text}" for line in cited_lines)
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Source lines:\n{source_block}\n\nClaim: {sentence.text}",
                }
            ],
            output_format=_EntailmentVerdict,
        )
        result = response.parsed_output
        return VerifierVerdict(sentence=sentence, entailed=result.entailed, reason=result.reason)


DEFAULT_GEMINI_VERIFIER_MODEL = "gemini-2.5-flash"


class GeminiVerifier:
    """Alternative verifier backend (Google Gemini), same interface as
    `LLMVerifier`. Requires `pip install google-genai` and a
    GEMINI_API_KEY/GOOGLE_API_KEY (or another credential source the SDK
    resolves)."""

    def __init__(self, client=None, model: str = DEFAULT_GEMINI_VERIFIER_MODEL):
        from google import genai

        self.client = client or genai.Client()
        self.model = model

    def verify(self, sentence: GeneratedSentence, cited_lines: list[SourceLine]) -> VerifierVerdict:
        if not _check_citation(sentence, cited_lines):
            return VerifierVerdict(sentence=sentence, entailed=False, reason=_CITATION_MISMATCH_REASON)

        from google.genai import types

        source_block = "\n".join(f"line {line.line_no}: {line.text}" for line in cited_lines)
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"Source lines:\n{source_block}\n\nClaim: {sentence.text}",
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_EntailmentVerdict,
            ),
        )
        result: _EntailmentVerdict = response.parsed
        return VerifierVerdict(sentence=sentence, entailed=result.entailed, reason=result.reason)
