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

## Docs

- [`docs/design.md`](./docs/design.md) — full system design: requirement framing, architecture and AI leverage, the control plane, dev-to-deployment and data migration, a worked end-to-end use case, and business handoff.
- [`docs/architecture-pipeline.svg`](./docs/architecture-pipeline.svg) — the citation-bound generation → verification → coverage-check → clinician-review pipeline, all inside the no-egress boundary.
- [`docs/architecture-control-data-plane.svg`](./docs/architecture-control-data-plane.svg) — the data plane / control plane split: what processes notes vs. what governs the process.
- [`docs/architecture-dev-to-prod.svg`](./docs/architecture-dev-to-prod.svg) — dev → staging → production, with the eval corpus as the staging release gate.

The vertical-slice implementation under `src/clinical_summarization/` implements the pipeline diagram end to end against the sample note, with pluggable generator/verifier backends (offline stub, Claude, Gemini) behind the same interface — see `src/clinical_summarization/pipeline.py`.
