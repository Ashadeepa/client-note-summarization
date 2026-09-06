"""Run the pipeline against a note file and print a human-readable draft.

Nothing here writes, sends, or files anything — printing to stdout is the
only output path, consistent with the "no send capability exists" guardrail
in docs/design.md, Section 3.
"""

from __future__ import annotations

import argparse

from clinical_summarization.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the clinical note summarization pipeline.")
    parser.add_argument("note_file")
    parser.add_argument(
        "--backend",
        choices=["stub", "claude", "gemini"],
        default="stub",
        help="Which generator/verifier implementation to use. 'stub' (default) is "
        "offline and free. 'claude' requires ANTHROPIC_API_KEY. 'gemini' requires "
        "GEMINI_API_KEY/GOOGLE_API_KEY.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Deprecated alias for --backend claude.",
    )
    args = parser.parse_args()

    backend = "claude" if args.live else args.backend
    if backend != "stub":
        import os

        os.environ["CLINICAL_SUMMARIZATION_BACKEND"] = backend

    with open(args.note_file, encoding="utf-8") as f:
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
