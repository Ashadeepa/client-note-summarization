# Clinical Note Summarisation — System Design

---

## 1. Requirement framing — problem definition

**Business problem.** Clinicians lose hours per discharge to manual summarisation of long, messy encounter notes (vitals, nursing notes, physician notes, labs, orders, free-text). Leadership wants an AI-generated draft to cut that time — but this is a patient-safety-adjacent system, not a productivity toy: a wrong claim in a discharge summary can cause a missed diagnosis, a wrong medication reconciliation, or a dropped follow-up.

**Framing the problem correctly is the first architectural decision.** This is not "build a summarisation model." It's two coupled problems with different risk profiles:

| Sub-problem | Risk if wrong | Owner |
|---|---|---|
| Draft generation (what should the summary say) | Time saved, but bounded — clinician reads everything anyway | AI |
| Claim verification (is what it says actually true) | Unbounded — a hallucinated claim that survives review is a safety event | AI + deterministic checks + human sign-off |

**Explicit non-goals** (say these out loud in any design review — they define the blast radius):
- Not autonomous. No summary is ever sent, filed, or acted on without clinician sign-off.
- Not diagnostic. The system never infers a diagnosis the notes don't state; it summarises documented facts.
- Not a source-of-truth system. It never overwrites or supersedes the original chart.

**Functional requirements**
- Structured discharge-summary draft (standard sections: HPI, hospital course, discharge diagnosis, discharge meds, pending results, follow-up, code status)
- Every generated sentence traceable to specific source lines
- Explicit "insufficient source" flag on any required field with no supporting evidence, instead of a plausible-sounding guess
- Stretch: detect open loops — an ordered test/referral with no documented result or follow-up plan

**Non-functional requirements**
- Zero data egress — PHI never leaves the customer's environment, including logs and telemetry
- Draft-only — architecturally incapable of auto-sending (no send capability exists in the system's action space)
- Auditable — every field in every summary must be reconstructable to (source lines, model version, prompt version, verifier verdict) months later
- Low-latency enough to fit clinician workflow (drafting time reduction is the success metric — a slow draft that requires as much reading as writing from scratch doesn't move the metric)

**Success metric.** Reduce drafting time meaningfully **with zero unsupported clinical claims** — these are yoked together, not traded off. A system that's fast but occasionally confidently wrong isn't a partial success; it's a different, worse system. This is the generation/validation separation principle applied at the requirements level: throughput is what generation buys you, safety is what a separate validation layer buys you, and neither compensates for the other.

---

## 2. Architecture and AI leverage

**Where AI genuinely adds leverage:**
- Drafting prose from structured/semi-structured clinical text (its strength — fluent synthesis)
- Section classification (which lines belong in HPI vs hospital course)
- Free-text matching for open-loop detection where structured order/result joins fail

**Where AI is a liability if used unsupervised:**
- Deciding whether a claim is *true* — an LLM grading its own output is correlated with the same failure mode that produced the output
- Filling gaps — the single highest-risk behavior in this domain is a model producing a plausible sentence for a field with no source support

**Design consequence: generation and validation are architecturally separate systems, not separate prompts.**
- The **generator** produces sentence-level output *bound* to citations at generation time (structured `{text, source_lines}` output, not prose-then-cite), because retrofitted citation search is where hallucinated support gets laundered into looking sourced.
- The **verifier** is an independent pass — ideally a distinct, simpler model or a lightweight NLI-style entailment checker — that reads *only* the cited lines and checks entailment. It has no access to the rest of the note, so it can't rationalize a claim using context the citation didn't actually invoke.
- A **coverage checker** (deterministic, not a model call) walks the required-field schema and confirms every mandatory field either has a verified citation or is explicitly flagged. This is the layer that turns "usually cites things" into "never ships an unsupported claim" — it's a hard gate, not a heuristic.

This is why the system is markedly more expensive per summary than a single LLM call — that's a designed cost, not an inefficiency, and it's the number to flag to leadership early rather than let them discover in a budget review.

**Model choice is a control-plane decision, not a generation-quality decision.** The generator can be a strong general model; the verifier benefits from being a *different* model (or model family) than the generator, so a shared blind spot in one doesn't silently validate itself in the other.

---

## 3. The control plane

Separating **data plane** (notes flowing through ingest → extraction → generation → verification) from **control plane** (the policies governing what's allowed to happen) is what makes this system operable and auditable rather than a black box with a UI on top.

**What lives in the control plane:**

- **Policy engine** — the required-field schema per summary type, the insufficiency threshold, which fields are hard-blocking vs advisory
- **Model routing & versioning** — which generator/verifier model version served this request; pinned, not "latest," so a summary from March is reproducible in September
- **Guardrail enforcement** — the structural fact that no "send" action exists anywhere in the tool surface the AI can call; the only write path from the AI's output is to a draft store a human then acts on
- **Audit log** — immutable record per summary: input note hash, model versions, every citation, every verifier verdict, every insufficiency flag, and the clinician's final edits — kept inside the customer boundary
- **Circuit breakers / kill switch** — if the verifier's flag rate on a model version spikes (signal of a bad deploy or drifted note format), the pipeline should auto-halt generation for that version and fall back to "manual drafting, no AI assist" rather than silently degrading
- **Rate/cost governance** — since the two-pass design doubles inference cost, the control plane is also where you'd throttle or prioritize (e.g. complex multi-problem admissions get the verifier; routine short-stay notes might get a cheaper single-pass path with tighter coverage thresholds — a real trade-off worth surfacing, not hiding)
- **Access control** — who can view drafts, who can approve model version promotions, who can adjust the required-field schema (this should not be an engineering-only decision — clinical informatics should own the schema)

The control plane is deliberately **not** where clinical judgment lives — it enforces process, not medical correctness. Medical correctness is the verifier's and clinician's job. The control plane's job is making sure the process that produces a summary is always the same process, every time, and that any deviation is visible.

---

## 4. Target architecture and dev-to-deployment, including data migration

**Deployment topology** — everything below the line lives inside the customer's VPC/on-prem boundary; nothing crosses it:

- Model serving: self-hosted open-weight model or a vendor's dedicated-instance/on-prem offering — no public API calls
- Vector store + note index: in-boundary, encrypted at rest
- Application layer (ingestion, section extraction, orchestration, draft store, review UI): in-boundary
- Egress denied by default at the network layer (not just "the app doesn't call out") — a code bug should not be able to leak data; the boundary has to be enforced structurally

**Dev → staging → production**

1. **Dev**: synthetic and de-identified sample notes only; no real PHI touches a developer's environment ever, including local debugging
2. **Staging**: a mirrored, access-controlled copy of production infrastructure inside the same boundary, running the adversarial eval suite (Section 6 of the original design) as a **release gate** — a model/prompt change cannot promote to production unless the hallucination-rate and required-field-flagging metrics clear threshold, checked automatically on every change, not just at initial launch
3. **Production**: canary rollout by summary type or ward, starting with the lowest-acuity, most routine cases, before spreading to complex multi-problem admissions
4. **Rollback**: since model versions are pinned per the control plane's versioning policy, rollback is a routing change, not a redeploy — this matters because a hallucination spike needs a same-hour response, not a next-release fix

**Data migration** — this is the part most designs skip and it's where a real system trips:

- **Historical notes are not bulk-fed to the model.** The goal of migration isn't "backfill the AI's knowledge" — an LLM summarizer doesn't need historical notes to function on a new encounter. Migration exists to build the **eval corpus**: a representative, clinician-annotated gold set drawn from real historical encounters.
- That means the migration pipeline's real job is a **de-identification and annotation workflow**, not a data-loading job: pull a stratified sample of past encounters (routine + complex + edge cases), de-identify for the eval environment if graders work outside the strict production boundary, and have clinicians annotate gold summaries with sentence-level source citations.
- **Format normalization** is the other real migration task — hospital notes come from multiple EHR exports, dictation systems, and scanned/OCR'd documents; the ingestion pipeline's line-numbering scheme (the citation currency for the whole system) has to handle all of them consistently, or citations silently misalign and the verifier is checking the wrong lines. This is worth a dedicated format-inventory pass before writing a line of the generator.
- No live cutover moment exists for this system in the way there is for, say, a database migration — it launches alongside the existing manual workflow and clinicians opt into drafts per-note, so the "migration" risk is really an eval-corpus-quality risk, not a data-loss risk.

---

## 5. Sample use case, end to end

Walking one encounter through the full pipeline:

1. **Source note** (excerpt, line-numbered): line 42 — "Metformin 500mg BID, continued on discharge." Line 58 — "CT chest ordered 3/2 for persistent cough." Line 61 — "Pt tolerating oral intake well, ambulating independently." No later line documents a CT result.

2. **Ingest & normalize** tags line 42 as medication-relevant, line 58 as an order, line 61 as functional-status.

3. **Section extraction** routes line 42 toward "Discharge medications," line 61 toward "Hospital course."

4. **Draft generation** emits, e.g.: `{ text: "Metformin 500 mg twice daily, continued at discharge.", source_lines: [42] }` — never prose without an attached span.

5. **Verification pass** re-reads only line 42, confirms it entails the generated sentence, and passes it.

6. **Coverage check** walks the required-field schema: discharge medications ✓ (cited), hospital course ✓ (cited), **follow-up plan** — no supporting line found anywhere in the note → emits `[INSUFFICIENT SOURCE — clinician input required]` rather than inventing a plausible-sounding follow-up.

7. **Open-loop detector** (stretch capability) joins the orders table against the results table: CT chest ordered line 58, no matching result — surfaced separately as a checklist item, "CT chest ordered 3/2, no result in chart — confirm follow-up," so it can't get buried in narrative prose.

8. **Clinician review UI** presents the draft with every sentence hoverable to its source line, the two flags surfaced prominently, nothing exportable or sendable until the clinician has reviewed and signed. The clinician fills the follow-up field from their own knowledge, confirms or chases the CT result, and signs.

9. **Audit log** now holds: input note hash, model versions for generator and verifier, every citation and verdict, both flags, and the clinician's edits — reconstructable end to end.

This walkthrough is also the natural demo script for a stakeholder review: it makes the "refuse rather than guess" behavior concrete instead of abstract, which is usually the point skeptical clinicians need to see to trust the system at all.

---

## 6. Business handoff and knowledge management

A system like this outlives its build team, and the handoff quality determines whether it stays safe under new maintainers or quietly drifts.

- **Ownership model**: clinical informatics owns the required-field schema and insufficiency thresholds; engineering owns the pipeline, model serving, and control plane; a joint governance committee (informatics + engineering + a rotating clinician reviewer) owns model version promotion decisions — this shouldn't be an engineering-only call, since a "quality improvement" to the generator can shift what gets flagged in ways only a clinician would catch.
- **Runbooks**: incident response for a hallucination-rate spike (who's paged, what the rollback procedure is, how a bad model version gets pulled from routing), and a separate runbook for ingestion-format drift (a new EHR export version breaking the line-numbering scheme).
- **Living documentation**: an ADR trail for every model/architecture decision (why generate-with-citation over generate-then-cite, why a separate verifier model, why the coverage check is deterministic rather than model-based) — these are exactly the decisions a future maintainer will be tempted to "simplify" without understanding why they exist.
- **Eval suite as institutional memory**: the adversarial case set (contradiction traps, negation traps, temporal traps, distractor-dense notes) is itself a knowledge asset — every production near-miss should become a new adversarial case, so the eval suite grows more representative of real failure modes over time rather than staying frozen at launch quality.
- **Clinician training and feedback loop**: a lightweight in-UI mechanism for clinicians to flag a draft error beyond just editing it silently — silent edits lose the signal of *why* something was wrong; a flagged error should route back to the eval corpus.
- **Metrics dashboard for handoff**: hallucination rate per sentence, required-field flag rate, drafting-time-saved (the paired study metric), and open-loop catch rate, tracked over time and by model version — this is what lets a future team notice drift before a patient-safety event does.
- **Sunset/version-deprecation policy**: since model versions are pinned, define upfront how long an old version stays servable after a new one promotes (for reproducibility of past audits) before it's formally retired.

The through-line across all six sections is the same one from Section 2: generation buys speed, a structurally separate validation layer buys safety, and the control plane, deployment process, and handoff docs all exist to keep that separation intact as the system — and the team around it — changes over time.
