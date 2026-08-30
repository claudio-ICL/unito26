"""The document's worked examples are generated, so they cannot drift from the tests.

A fixture explained in prose and asserted in code is two statements of one fact, and
they diverge on the first edit that touches only one of them.  Here the prose *is* the
fixture, rendered, and this test is what makes that claim true rather than aspirational.
"""

import pathlib

from unito26.lob import worked_examples

DOCUMENTATION = pathlib.Path(__file__).parents[2] / "documentation"
DOCUMENT = DOCUMENTATION / "order-flow-to-order-book.md"
INDEXING = DOCUMENTATION / "grid-levels-and-lobster-levels.md"


def test_regenerating_the_catalogue_leaves_the_document_unchanged():
    before = DOCUMENT.read_text()
    changed = worked_examples.write_into(str(DOCUMENT))
    assert not changed, (
        "the generated worked-example section is out of date; regenerate it with\n"
        "    python -m unito26.lob.worked_examples documentation/order-flow-to-order-book.md"
    )
    assert DOCUMENT.read_text() == before


def test_regenerating_the_indexing_example_leaves_the_document_unchanged():
    before = INDEXING.read_text()
    changed = worked_examples.write_into(
        str(INDEXING),
        worked_examples.render_indexing_markdown,
        worked_examples.INDEXING_BEGIN_MARKER,
        worked_examples.INDEXING_END_MARKER,
    )
    assert not changed, (
        "the generated indexing example is out of date; regenerate it with\n"
        "    python -m unito26.lob.worked_examples documentation/grid-levels-and-lobster-levels.md"
    )
    assert INDEXING.read_text() == before
