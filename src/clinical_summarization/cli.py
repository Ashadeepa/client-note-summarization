"""Run the pipeline against a note file and print a human-readable draft.

Nothing here writes, sends, or files anything — printing to stdout is the
only output path, consistent with the "no send capability exists" guardrail
in docs/design.md, Section 3.
"""

from __future__ import annotations

import sys

from clinical_summarization.pipeline import run_pipeline


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m clinical_summarization.cli <note_file>", file=sys.stderr)
        raise SystemExit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        raw_note = f.read()

    draft = run_pipeline(raw_note)

    print("=== Draft Summary ===\n")
    for section, verdicts in draft.sections.items():
        print(f"[{section}]")
        for verdict in verdicts:
            status = "OK" if verdict.entailed else "REJECTED"
            print(f"  ({status}) {verdict.sentence.text}  <- lines {verdict.sentence.source_lines}")
        print()

    print("[coverage]")
    for result in draft.coverage:
        if result.satisfied:
            print(f"  {result.field}: OK")
        else:
            print(f"  {result.field}: {result.flag}")
    print()

    print("[open loops]")
    if not draft.open_loops:
        print("  none detected")
    for loop in draft.open_loops:
        print(f"  line {loop.order_line}: {loop.description}")


if __name__ == "__main__":
    main()
