"""The lecture notes quote the package, and the quotes cannot drift from it.

A listing of the notes whose caption names an object of the package, a dotted path under
``unito26`` inside ``\\codehl``, is a quote of that object's source.  It may leave lines out,
marking each cut with a line reading ``# ...``, and every run of lines between two cuts must
occur in the source verbatim and in order, shifted as a block by at most one indentation.
Every other listing is a program, and it is run, so the assertions the notes make of it
hold.

A listing in the notes and the code it shows are two statements of one fact; this test is
what keeps them one.
"""

import importlib
import inspect
import pathlib
import re

import pytest

NOTES = pathlib.Path(__file__).parents[1] / "documentation" / "tex" / "notes"
LISTING = re.compile(
    r"\\begin\{lstlisting\}\[(?P<options>[^\n]*)\]\n(?P<body>.*?)\\end\{lstlisting\}", re.S
)
QUOTED = re.compile(r"\\codehl\{(unito26(?:\.[\w\\]+)+)\}")
LABEL = re.compile(r"label=([\w.]+)")
CUT = "# ..."


def listings() -> list:
    found = []
    for path in sorted(NOTES.rglob("*.tex")):
        for match in LISTING.finditer(path.read_text()):
            label = LABEL.search(match["options"])
            name = label[1] if label else f"{path.name}:{match.start()}"
            found.append(pytest.param(match["options"], match["body"], id=name))
    return found


def resolve(dotted: str):
    """The object a dotted path names: the longest importable prefix, then attributes."""
    parts = dotted.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            found = importlib.import_module(".".join(parts[:cut]))
        except ModuleNotFoundError:
            continue
        for name in parts[cut:]:
            found = getattr(found, name)
        return found
    raise LookupError(f"nothing importable in {dotted}")


def runs(body: str) -> list[list[str]]:
    """The lines of a quote between its cuts."""
    pieces, piece = [], []
    for line in body.rstrip("\n").split("\n"):
        if line.strip() == CUT:
            pieces.append(piece)
            piece = []
        else:
            piece.append(line.rstrip())
    pieces.append(piece)
    return [piece for piece in pieces if piece]


def indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def occurs(run: list[str], source: list[str], start: int) -> int | None:
    """Where ``run`` ends in ``source``, searching from ``start``, or None.

    The run matches a block of the source line for line, up to one indentation shared by
    every line that is not blank: a quote may lift a method out of its class.
    """
    for at in range(start, len(source) - len(run) + 1):
        block = source[at:at + len(run)]
        shifts = set()
        for quoted, original in zip(run, block):
            if quoted.strip() != original.strip():
                break
            if quoted.strip():
                shifts.add(indent(original) - indent(quoted))
        else:
            if len(shifts) <= 1:
                return at + len(run)
    return None


@pytest.mark.parametrize("options, body", listings())
def test_a_listing_quotes_the_package_or_runs(options, body):
    quoted = QUOTED.search(options)
    if quoted is None:
        exec(compile(body, "<listing>", "exec"), {"__name__": "__listing__"})
        return
    target = resolve(quoted[1].replace("\\_", "_").replace("\\", ""))
    source = [line.rstrip() for line in inspect.getsource(target).split("\n")]
    position = 0
    for run in runs(body):
        found = occurs(run, source, position)
        assert found is not None, (
            f"not in {quoted[1]}, in this order:\n" + "\n".join(run)
        )
        position = found


def test_the_notes_carry_both_kinds():
    kinds = [QUOTED.search(param.values[0]) is not None for param in listings()]
    assert any(kinds) and not all(kinds)
