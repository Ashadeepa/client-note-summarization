# Clinical Note Summarization

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,gemini]"
```

Run against the bundled sample note (offline, free, deterministic — no API key needed):

```bash
python -m clinical_summarization.cli examples/sample_note.txt
```

Run against a real model instead of the offline stub:

```bash
# Claude (claude-opus-5 generator / claude-sonnet-5 verifier)
ANTHROPIC_API_KEY=your-key python -m clinical_summarization.cli --backend claude examples/sample_note.txt

# Gemini (gemini-2.5-flash for both)
GEMINI_API_KEY=your-key python -m clinical_summarization.cli --backend gemini examples/sample_note.txt
```

Run the tests (always pinned to the offline stub backend, regardless of `--backend`):

```bash
pytest -q
```

To try your own note, write a text file using the same `line N — text` format as `examples/sample_note.txt` and pass its path instead.

### Writing a note that actually generates a draft

Section extraction (`src/clinical_summarization/ingest.py`) is deterministic
keyword tagging, not a model call — a line only reaches the generator if its
text matches one of these regexes:

| Section | Line must contain | Regex |
|---|---|---|
| `discharge_medications` | `mg`, `bid`, `tid`, `qd`, `dose`, or `continued on discharge` | `\b(mg\|bid\|tid\|qd\|dose\|continued on discharge)\b` |
| `hospital_course` | `tolerating`, `ambulating`, or `ambulatory` | `\b(tolerating\|ambulating\|ambulatory)\b` |
| `follow_up_plan` | `follow-up`, `follow up`, `f/u`, `return to clinic`, `recheck`, or `re-evaluate` | `\b(follow-up\|follow up\|f/u\|return to clinic\|recheck\|re-evaluate)\b` |

A line that matches none of these gets no tag and never reaches a section —
its content is simply invisible to the generator, not summarized and not
flagged as missing. Word boundaries matter too: `10mg` (no space) does not
match `\bmg\b`; `10 mg` does.

**Example that works** (mirrors `examples/sample_note.txt`):

```
line 42 — Metformin 500mg BID, continued on discharge.
line 58 — CT chest ordered 3/2 for persistent cough.
line 61 — Pt tolerating oral intake well, ambulating independently.
```

Produces:
- **Discharge Medications:** "Metformin 500mg BID was continued on discharge." — cited to line 42
- **Hospital Course:** "The patient is tolerating oral intake well and ambulating independently." — cited to line 61
- **Follow-up Plan:** `INSUFFICIENT SOURCE — clinician input required`
- **Open loop:** line 58 (CT ordered, no result in chart — nothing routes `ordered` lines to a section, so it surfaces here instead of being dropped)

**Example with two medication lines:**

```
line 15 — Atorvastatin 20mg qd, continued on discharge.
line 22 — Furosemide dose adjusted for renal function.
line 30 — CT abdomen ordered for suspected obstruction.
line 48 — Pt tolerating regular diet, ambulating with assistance.
```

**Example where most lines still don't route** (lines 12/27/33 match no tag —
`10mg` has no space before `mg`, so `\bmg\b` doesn't match, and chest
tightness/ECG findings aren't covered by any rule — so those three stay
invisible to the generator regardless of backend. Line 45 now routes to
`follow_up_plan`):

```
line 12 — Lisinopril 10mg daily, started for new hypertension diagnosis.
line 27 — Pt reports intermittent chest tightness, denies radiation to arm/jaw.
line 33 — ECG within normal limits, no ST changes noted.
line 45 — Follow-up with cardiology in 2 weeks recommended.
```

Produces:
- **Discharge Medications:** `INSUFFICIENT SOURCE — clinician input required`
- **Hospital Course:** `INSUFFICIENT SOURCE — clinician input required`
- **Follow-up Plan:** "Follow-up with cardiology in 2 weeks recommended." — cited to line 45

### Review UI (local)

A small React app for trying the pipeline interactively — paste/edit a note, pick a backend, see the draft with citations, coverage flags, and open loops rendered.

```bash
# terminal 1 — API server
source .venv/bin/activate
pip install -e ".[dev,gemini,server]"
uvicorn clinical_summarization.api:app --port 8010

# terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Live backends (Claude/Gemini) need the corresponding API key set in the terminal running `uvicorn` before you start it. The API has no send/export endpoint — draft-only, per docs/design.md Section 3.

## Documenation

- [`docs/design.md`](./docs/design.md) — full system design: requirement framing, architecture and AI leverage, the control plane, dev-to-deployment and data migration, a worked end-to-end use case, and business handoff.
- [`docs/architecture-pipeline.svg`](./docs/architecture-pipeline.svg) — the citation-bound generation → verification → coverage-check → clinician-review pipeline, all inside the no-egress boundary.
- [`docs/architecture-control-data-plane.svg`](./docs/architecture-control-data-plane.svg) — the data plane / control plane split: what processes notes vs. what governs the process.
- [`docs/architecture-dev-to-prod.svg`](./docs/architecture-dev-to-prod.svg) — dev → staging → production, with the eval corpus as the staging release gate.

The vertical-slice implementation under `src/clinical_summarization/` implements the pipeline diagram end to end against the sample note, with pluggable generator/verifier backends (offline stub, Claude, Gemini) behind the same interface — see `src/clinical_summarization/pipeline.py`.