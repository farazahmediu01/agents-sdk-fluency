"""
Put Chapter 4's spine and Chapter 5's filter on the import path.

Read `03_structured_outputs/solutions/_bootstrap.py` for the full argument.
Short version: chapter folders start with digits, so they cannot be packages, so
a script only ever gets its OWN directory on `sys.path`, and `extraPaths` in
`pyproject.toml` tells pyright where to look without affecting runtime.

WHY THE NAME IS NOT `_bootstrap`
--------------------------------
Because `sys.modules` keys on the module NAME, not the path, and this repo now
has several of these. The first one imported wins; every later `import
_bootstrap` is a cache hit that silently does nothing. Chapter 5 found this the
expensive way -- `uv run pytest 05_context_window` passed and `uv run pytest`
died with `ModuleNotFoundError: No module named 'packing_agent'`.

It matters more here than in `with_sdk/`, because `check_regression.py`
deliberately imports Chapter 4's harness AND this chapter's agent into one
process. Two files called `_bootstrap` in that process is not a hazard, it is a
guaranteed failure -- and a confusing one, since the module that "did not run"
raises nothing at all.

> **Rule: a bootstrap module needs a name unique across the whole repository.**

Import it FIRST, before any spine import:

    import _bootstrap_spine5  # noqa: F401
    import expense_store
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The spine, oldest first, plus Chapter 5's own `with_sdk` for the compactor.
# The list grows by one entry per chapter -- the running cost of "one app that
# grows", paid here rather than by copying code forward.
_PATHS = [
    _REPO_ROOT / "02_typed_tools" / "from_scratch",
    _REPO_ROOT / "02_typed_tools" / "solutions",
    _REPO_ROOT / "03_structured_outputs" / "solutions",
    _REPO_ROOT / "04_sessions_state" / "solutions",
    _REPO_ROOT / "05_context_window" / "with_sdk",
]

for _path in _PATHS:
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)
