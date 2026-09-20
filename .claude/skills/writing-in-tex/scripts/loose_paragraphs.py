#!/usr/bin/env python3
"""List free-standing paragraphs that introduce no symbol, hypothesis or consequence.

A paragraph that carries no maths, no cross-reference, no citation and no defined term is
usually there to comment on the paragraph beside it, which house rule 9 forbids.  The output
is a list to justify, not a list to forbid: lead-ins to a display land here too.
"""

import re
import sys
from pathlib import Path

ENVIRONMENT = re.compile(r"\\(begin|end)\{")
SUBSTANTIVE = re.compile(r"\$|\\ref|\\eqref|\\cite|\\emph")


def loose_paragraphs(path: Path, low: int = 4, high: int = 45):
    depth, start, buffer = 0, 0, []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        for token in ENVIRONMENT.finditer(line):
            depth += 1 if token.group(1) == "begin" else -1
        if stripped.startswith("%") or ENVIRONMENT.search(line) or stripped.startswith("\\"):
            stripped = ""
        if stripped and depth <= 0:
            if not buffer:
                start = number
            buffer.append(stripped)
            continue
        if buffer:
            text = " ".join(buffer)
            if low <= len(text.split()) <= high and not SUBSTANTIVE.search(text):
                yield start, text
            buffer = []


def main(roots: list[str]) -> int:
    hits = 0
    for root in roots:
        for path in sorted(Path(root).rglob("*.tex")):
            for number, text in loose_paragraphs(path):
                print(f"{path}:{number}: {text}")
                hits += 1
    print(f"--- {hits} paragraphs to justify ---", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["."]))
