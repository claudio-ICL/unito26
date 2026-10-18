"""The sample questions and the notebooks that answer them are one statement.

A question of ``documentation/tex/questions/sections`` writes exactly one of its choices
``\\correctchoice``, and its section names, by ``\\notebook``, a notebook of
``notebooks/sample-questions``.  That notebook runs the code of the question and closes it
with one call ``verify("question.<label>", "<letter>", [...])``, which evaluates every choice
and asserts that the one lettered there holds and that no other does.

Running the notebooks is what makes the letters true.  These tests read the two without
running either, and keep them in step:

- a listing whose caption names an object of the package is a quote of it, held to the
  source as the quotes of the lecture notes are;
- every other listing of a question occurs, line for line, in a code cell of its notebook,
  so that the code verified is the code printed;
- the letter the notebook verifies is the letter of the key, for every question, and no
  notebook verifies a question that does not exist.

A snippet of a question is never run here: an alternative offered as a choice is often
wrong on purpose.
"""

import inspect
import json
import pathlib
import re

import pytest

from tests.test_notes_quote_the_package import QUOTED, occurs, resolve, runs

ROOT = pathlib.Path(__file__).parents[1]
SECTIONS = ROOT / "documentation" / "tex" / "questions" / "sections"
NOTEBOOKS = ROOT / "notebooks" / "sample-questions"
LETTERS = "ABCDE"
WIDTH = 75

QUESTION = re.compile(r"\\begin\{question\}(?P<body>.*?)\\end\{question\}", re.S)
LISTING = re.compile(
    r"\\begin\{lstlisting\}\[(?P<options>[^\n]*)\]\n(?P<body>.*?)\\end\{lstlisting\}", re.S
)
ANY_LISTING = re.compile(r"\\begin\{lstlisting\}")
LABEL = re.compile(r"\\label\{(question\.\w+)\}")
CHOICE = re.compile(r"\\(correctchoice|choice)(?![a-z])")
NOTEBOOK = re.compile(r"\\notebook\{([\w-]+)\}")
COMMENT = re.compile(r"(?<!\\)%.*")
VERIFY = re.compile(r'verify\(\s*"(question\.\w+)",\s*"([A-E])"')


def prose(body: str) -> str:
    """A question without its listings and its comments."""
    return COMMENT.sub("", LISTING.sub("", body))


def questions() -> list[dict]:
    found = []
    for path in sorted(SECTIONS.glob("*.tex")):
        text = path.read_text()
        notebook = NOTEBOOK.search(text)
        for match in QUESTION.finditer(text):
            body = match["body"]
            label = LABEL.search(prose(body))
            kinds = CHOICE.findall(prose(body))
            found.append({
                "file": path.name,
                "label": label[1] if label else f"{path.name}:{match.start()}",
                "notebook": notebook[1] if notebook else None,
                "key": [LETTERS[i] for i, kind in enumerate(kinds) if kind == "correctchoice"],
                "choices": len(kinds),
                "listings": [(m["options"], m["body"]) for m in LISTING.finditer(body)],
                "unparsed": len(ANY_LISTING.findall(body)) - len(LISTING.findall(body)),
            })
    return found


def code_cells(notebook: str) -> list[list[str]]:
    path = NOTEBOOKS / f"{notebook}.ipynb"
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    return [
        [line.rstrip() for line in "".join(cell["source"]).split("\n")]
        for cell in cells
        if cell["cell_type"] == "code"
    ]


def verifications() -> list[tuple[str, str, str]]:
    """``(notebook, label, letter)`` for every call of ``verify`` in every notebook."""
    found = []
    for path in sorted(NOTEBOOKS.glob("*.ipynb")):
        for cell in code_cells(path.stem):
            for label, letter in VERIFY.findall("\n".join(cell)):
                found.append((path.stem, label, letter))
    return found


QUESTIONS = questions()
SNIPPETS = [
    pytest.param(question, options, body, id=f"{question['label']}:{k}")
    for question in QUESTIONS
    for k, (options, body) in enumerate(question["listings"])
]


def test_the_collection_is_not_empty():
    assert QUESTIONS


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda question: question["label"])
def test_a_question_has_a_label_one_correct_choice_and_a_notebook(question):
    assert question["label"].startswith("question."), "a question carries \\label{question.…}"
    assert len(question["key"]) == 1, f"{question['label']}: correct choices {question['key']}"
    assert 2 <= question["choices"] <= len(LETTERS)
    assert question["notebook"], f"{question['file']} names no \\notebook"
    assert question["unparsed"] == 0, "a listing carries its options on its first line"


@pytest.mark.parametrize("question, options, body", SNIPPETS)
def test_a_snippet_fits_the_page(question, options, body):
    if QUOTED.search(options):
        return
    wide = [line for line in body.split("\n") if len(line) > WIDTH]
    assert not wide, f"wider than {WIDTH} columns:\n" + "\n".join(wide)


@pytest.mark.parametrize("question, options, body", SNIPPETS)
def test_a_listing_quotes_the_package_or_is_run_by_the_notebook(question, options, body):
    quoted = QUOTED.search(options)
    if quoted is not None:
        target = resolve(quoted[1].replace("\\_", "_").replace("\\", ""))
        source = [line.rstrip() for line in inspect.getsource(target).split("\n")]
        position = 0
        for run in runs(body):
            found = occurs(run, source, position)
            assert found is not None, f"not in {quoted[1]}, in this order:\n" + "\n".join(run)
            position = found
        return
    snippet = [line.rstrip() for line in body.rstrip("\n").split("\n")]
    cells = code_cells(question["notebook"])
    assert any(occurs(snippet, cell, 0) is not None for cell in cells), (
        f"{question['label']}: not in any code cell of {question['notebook']}:\n" + body
    )


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda question: question["label"])
def test_the_notebook_verifies_the_key(question):
    letters = [
        letter
        for notebook, label, letter in verifications()
        if notebook == question["notebook"] and label == question["label"]
    ]
    assert letters == question["key"], (
        f"{question['label']}: the key is {question['key']}, "
        f"{question['notebook']} verifies {letters}"
    )


def test_every_verification_names_a_question():
    labels = {question["label"] for question in QUESTIONS}
    orphans = [(notebook, label) for notebook, label, _ in verifications() if label not in labels]
    assert not orphans, f"verified, and not a question: {orphans}"
