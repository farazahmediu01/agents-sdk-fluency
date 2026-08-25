"""
Put Chapter 4's `with_sdk` folder on the import path.

Same reason and same shape as `03_structured_outputs/solutions/_bootstrap.py` --
read that file's docstring for the full argument. The short version: chapter
folders start with digits, so they cannot be packages, so a script only ever
gets its OWN directory on `sys.path`. `extraPaths` in `pyproject.toml` tells
pyright where to look and has no effect at runtime.

WHY THE UGLY NAME
-----------------
This file was called `_bootstrap.py` for about an hour, which is how long it
took to discover that `sys.modules` keys on the module NAME and not the path.
Chapters 3, 4 and 5 each had one; the first to be imported won, and every later
`import _bootstrap` was a cache hit that silently did nothing:

    ModuleNotFoundError: No module named 'packing_agent'

`uv run pytest 05_context_window` passed. `uv run pytest` did not.

> **Rule for the next chapter: a bootstrap module needs a name unique across the
> whole repository.** Chapters 3 and 4 got away with `_bootstrap` because their
> path lists overlap; the moment one needs a path the others do not add, the
> chapter that loses the race breaks -- and it breaks two chapters after the
> collision was introduced.

Chapter 5 reuses Chapter 4's packing agent deliberately. Context management is
not a property of expenses, and re-teaching it on a fresh agent would hide the
one thing worth seeing: this is the SAME agent, the SAME session, and the SAME
conversation whose growth Chapter 4 measured. Only the filter is new.

Import it FIRST:

    import _bootstrap_sdk5  # noqa: F401
    from packing_agent import packing_agent
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

_PATHS = [_REPO_ROOT / "04_sessions_state" / "with_sdk"]

for _path in _PATHS:
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)
