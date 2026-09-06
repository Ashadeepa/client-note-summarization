"""Required-field schema — control-plane policy, owned by clinical informatics
in practice (docs/design.md, Section 3), hardcoded here for the vertical slice.
"""

from __future__ import annotations

# section name -> which ingest tags route a line into it
SECTION_ROUTING: dict[str, tuple[str, ...]] = {
    "discharge_medications": ("medication",),
    "hospital_course": ("functional_status",),
}

# every field a discharge summary must either cite or explicitly flag
REQUIRED_FIELDS: tuple[str, ...] = (
    "discharge_medications",
    "hospital_course",
    "follow_up_plan",
)

INSUFFICIENT_SOURCE_FLAG = "INSUFFICIENT SOURCE — clinician input required"
