#!/usr/bin/env python3
"""Measure what each beamer frame is made of, and how many words sit beside it.

A deck is projection material: the frame carries an object -- a display, a diagram, a
statement, a table, an algorithm -- and the words under it are captions the lecturer
glances at.  Prose belongs in the lecture notes, and what is said aloud belongs in
``\\note``, which this counts separately and does not hold against the frame.

A caption is a gloss (``term: noun phrase``), a fragment of subject and predicate, or a
condition written as mathematics.  It is never a sentence, so its length is capped twice:
``--cap`` over the whole frame, and ``--sentence`` over each caption taken alone.

The body of a statement is an object and is not counted as caption, but it is prose all
the same, so its own words are capped by ``--statement``.

Reports the caption words of every frame, and flags the ones over ``--cap`` (``OVER``),
the ones whose captions read as sentences (``LONG``), the ones whose statement says more
than its head claim (``STMT``), and the ones carrying no object at all (``BARE``).
"""

import re
import sys
from pathlib import Path

FRAME = re.compile(r"\\begin\{frame\}(.*?)\\end\{frame\}", re.S)
TITLE = re.compile(r"\\frametitle\{(.*?)\}", re.S)

#: Environments whose contents are the object, not the caption around it.
OBJECTS = (
    ("diagram", r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}"),
    ("table", r"\\begin\{tabular\}.*?\\end\{tabular\}"),
    ("algorithm", r"\\begin\{algorithmic\}.*?\\end\{algorithmic\}"),
    ("statement", r"\\begin\{(?:defi|prop|thm|lemma|corol|remark|assumption)\}.*?"
                  r"\\end\{(?:defi|prop|thm|lemma|corol|remark|assumption)\}"),
    ("display", r"\\begin\{(?:equation|equation\*|align|align\*|gather)\}.*?"
                r"\\end\{(?:equation|equation\*|align|align\*|gather)\}"),
    ("display", r"\\\[.*?\\\]"),
    ("list", r"\\begin\{(?:itemize|enumerate)\}.*?\\end\{(?:itemize|enumerate)\}"),
)

NOTE = re.compile(r"\\note\{", re.S)
COMMENT = re.compile(r"(?<!\\)%.*$", re.M)
MACRO = re.compile(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?")
#: A symbol is not a word: inline mathematics is the object's language, not prose.
INLINE = re.compile(r"\$[^$]*\$", re.S)
BRACES = re.compile(r"[{}$&\\]")
#: What separates one caption from the next: a beat, a blank line, a break, a full stop.
BREAK = re.compile(r"\\pause|\\\\|\n\s*\n|(?<=[a-z])[.;](?:\s|$)")


def _balanced(text: str, start: int) -> tuple[str, int]:
    """The braced group beginning at ``start``, and where it ends.  Nesting-aware."""
    depth, index = 0, start
    while index < len(text):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
        index += 1
    return text[start:], len(text)


STATEMENT = re.compile(r"\\begin\{(?:defi|prop|thm|lemma|corol|remark|assumption)\}"
                       r"(.*?)\\end\{(?:defi|prop|thm|lemma|corol|remark|assumption)\}", re.S)


def dissect(body: str) -> tuple[list[str], list[int], int, int]:
    """Objects present, the length of each caption, the statement bodies, and the note."""
    body = COMMENT.sub("", body)
    body = TITLE.sub("", body)

    spoken = 0
    while (found := NOTE.search(body)) is not None:
        note, end = _balanced(body, found.end() - 1)
        spoken += len(_words(note))
        body = body[:found.start()] + body[end:]

    stated = sum(len(_words(said)) for said in STATEMENT.findall(body))

    kinds = []
    for name, pattern in OBJECTS:
        body, count = re.subn(pattern, "\n\n", body, flags=re.S)
        if count:
            kinds.extend([name] * count)
    captions = [len(_words(piece)) for piece in BREAK.split(body) if _words(piece)]
    return kinds, captions, stated, spoken


def _words(text: str) -> list[str]:
    return BRACES.sub(" ", MACRO.sub(" ", INLINE.sub(" ", text))).split()


def main(argv: list[str]) -> int:
    cap, sentence, statement = 40, 12, 25
    roots = []
    for argument in argv:
        if argument.startswith("--cap="):
            cap = int(argument.split("=", 1)[1])
        elif argument.startswith("--sentence="):
            sentence = int(argument.split("=", 1)[1])
        elif argument.startswith("--statement="):
            statement = int(argument.split("=", 1)[1])
        else:
            roots.append(argument)

    frames = over = long = said = bare = total = 0
    for root in roots or ["."]:
        base = Path(root)
        for path in [base] if base.is_file() else sorted(base.rglob("*.tex")):
            for body in FRAME.findall(path.read_text()):
                kinds, captions, stated, spoken = dissect(body)
                title = TITLE.search(body)
                title = title.group(1) if title else "(untitled)"
                caption = sum(captions)
                frames, total = frames + 1, total + caption
                flag = "     "
                if not kinds:
                    flag, bare = "BARE ", bare + 1
                if captions and max(captions) > sentence:
                    flag, long = "LONG ", long + 1
                if stated > statement:
                    flag, said = "STMT ", said + 1
                if caption > cap:
                    flag, over = "OVER ", over + 1
                if flag.strip():
                    print(f"{flag}{caption:>4}w caption ({max(captions or [0]):>3}w longest),"
                          f" {stated:>3}w stated, {spoken:>4}w spoken, "
                          f"{','.join(sorted(set(kinds))) or 'nothing':<24} {title[:44]}")
    if frames:
        print(f"--- {frames} frames, {total / frames:.0f} caption words each on average; "
              f"{over} over {cap}, {long} with a caption over {sentence}, "
              f"{said} with a statement over {statement}, "
              f"{bare} with no object ---", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
