# Docs

- [`design.md`](./design.md) — full system design: requirement framing, architecture and AI leverage, the control plane, dev-to-deployment and data migration, a worked end-to-end use case, and business handoff.
- [`architecture-pipeline.svg`](./architecture-pipeline.svg) — the citation-bound generation → verification → coverage-check → clinician-review pipeline, all inside the no-egress boundary.
- [`architecture-control-data-plane.svg`](./architecture-control-data-plane.svg) — the data plane / control plane split: what processes notes vs. what governs the process.
- [`architecture-dev-to-prod.svg`](./architecture-dev-to-prod.svg) — dev → staging → production, with the eval corpus as the staging release gate.

The prototype itself (`clinical-summary-demo.jsx`, ported into the app under `src/`) implements the pipeline diagram end to end against two synthetic sample notes, using live model calls for generation and an independent verification pass.
