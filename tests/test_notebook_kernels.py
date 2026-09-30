"""Every notebook names the kernel `python3`, the one ipykernel installs in each environment.

`python3` resolves to the Python of the environment the Jupyter server was started from,
which is the setup the course prescribes. A kernel registered under another name exists
only on the machine that registered it, and serves a server started elsewhere, whose
figures plotly leaves blank.
"""

import json
import pathlib

import pytest

NOTEBOOKS = sorted(
    path
    for path in (pathlib.Path(__file__).parents[1] / "notebooks").rglob("*.ipynb")
    if ".ipynb_checkpoints" not in path.parts
)


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=lambda path: path.name)
def test_notebook_names_the_python3_kernel(notebook):
    kernelspec = json.loads(notebook.read_text(encoding="utf-8"))["metadata"].get("kernelspec", {})
    assert kernelspec.get("name") == "python3", (
        f"{notebook.name} names the kernel {kernelspec.get('name')!r}; "
        "choose 'Python 3 (ipykernel)' and save it again"
    )
