"""HTTP API over the pipeline, for the local review-UI frontend.

Thin wrapper only — no new logic. Serializes DraftSummary into JSON the
React app can render as a clinician-review-style view (docs/design.md,
Section 5, step 8): every sentence next to its source line, flags surfaced,
nothing exportable or sendable — this API has no such endpoint either.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from clinical_summarization.pipeline import run_pipeline

app = FastAPI(title="Clinical Note Summarization API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

_VALID_BACKENDS = {"stub", "claude", "gemini"}


class SummarizeRequest(BaseModel):
    note: str
    backend: str = "stub"


@app.post("/api/summarize")
def summarize(request: SummarizeRequest) -> dict:
    if request.backend not in _VALID_BACKENDS:
        raise HTTPException(400, f"backend must be one of {sorted(_VALID_BACKENDS)}")

    import os

    prior = os.environ.get("CLINICAL_SUMMARIZATION_BACKEND")
    os.environ["CLINICAL_SUMMARIZATION_BACKEND"] = request.backend
    try:
        draft = run_pipeline(request.note)
    except Exception as exc:  # noqa: BLE001 — surface the real cause to the UI
        raise HTTPException(502, f"pipeline error: {exc}") from exc
    finally:
        if prior is None:
            os.environ.pop("CLINICAL_SUMMARIZATION_BACKEND", None)
        else:
            os.environ["CLINICAL_SUMMARIZATION_BACKEND"] = prior

    return {
        "sections": {
            section: [
                {
                    "text": v.sentence.text,
                    "source_lines": list(v.sentence.source_lines),
                    "entailed": v.entailed,
                    "reason": v.reason,
                }
                for v in verdicts
            ]
            for section, verdicts in draft.sections.items()
        },
        "coverage": [
            {"field": c.field, "satisfied": c.satisfied, "flag": c.flag} for c in draft.coverage
        ],
        "open_loops": [
            {"order_line": o.order_line, "description": o.description} for o in draft.open_loops
        ],
    }
