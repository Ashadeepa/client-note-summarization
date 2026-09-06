from clinical_summarization.pipeline import run_pipeline

NOTE = """
line 42 — Metformin 500mg BID, continued on discharge.
line 58 — CT chest ordered 3/2 for persistent cough.
line 61 — Pt tolerating oral intake well, ambulating independently.
"""


def test_generates_citation_bound_sentence_for_medication():
    draft = run_pipeline(NOTE)
    med_verdicts = draft.sections["discharge_medications"]
    assert len(med_verdicts) == 1
    assert med_verdicts[0].sentence.source_lines == (42,)
    assert med_verdicts[0].entailed


def test_hospital_course_cites_functional_status_line():
    draft = run_pipeline(NOTE)
    course_verdicts = draft.sections["hospital_course"]
    assert len(course_verdicts) == 1
    assert course_verdicts[0].sentence.source_lines == (61,)
    assert course_verdicts[0].entailed


def test_coverage_flags_follow_up_plan_as_insufficient_source():
    draft = run_pipeline(NOTE)
    follow_up = next(c for c in draft.coverage if c.field == "follow_up_plan")
    assert not follow_up.satisfied
    assert "INSUFFICIENT SOURCE" in follow_up.flag


def test_coverage_passes_fields_with_verified_citations():
    draft = run_pipeline(NOTE)
    meds = next(c for c in draft.coverage if c.field == "discharge_medications")
    course = next(c for c in draft.coverage if c.field == "hospital_course")
    assert meds.satisfied
    assert course.satisfied


def test_open_loop_detects_ct_chest_with_no_result():
    draft = run_pipeline(NOTE)
    assert len(draft.open_loops) == 1
    assert draft.open_loops[0].order_line == 58


def test_verifier_rejects_unsupported_claim():
    from clinical_summarization.generator import GeneratedSentence
    from clinical_summarization.ingest import parse_note
    from clinical_summarization.verifier import verify

    lines = parse_note(NOTE)
    line_42 = next(l for l in lines if l.line_no == 42)
    fabricated = GeneratedSentence(
        text="Patient was diagnosed with type 2 diabetes mellitus.",
        source_lines=(42,),
        section="discharge_medications",
    )
    verdict = verify(fabricated, [line_42])
    assert not verdict.entailed
