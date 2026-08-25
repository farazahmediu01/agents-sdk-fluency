"""
The trimmer. Pure functions over a list of session items.

WHY THIS IS ITS OWN FILE, AND NOT PART OF `filter_demo.py`
---------------------------------------------------------
Two reasons, and the second one was a bug.

**It is testable for free.** Nothing here imports an agent, a model, or a key.
`test_trim.py` exercises every property in milliseconds, which is what lets a
chapter about long conversations avoid paying for one on every run.

**A shared module name is a shared module.** The first version put these
functions in `filter_demo.py`, which imports `_bootstrap` to reach Chapter 4's
packing agent. `uv run pytest 05_context_window` passed. `uv run pytest` did
not:

    ModuleNotFoundError: No module named 'packing_agent'

There are now three files called `_bootstrap.py` in this repo -- Ch3, Ch4 and
Ch5 -- and `sys.modules` keys on the module NAME, not the path. Whichever one is
imported first wins, and every later `import _bootstrap` is a cache hit that
silently does nothing. Chapter 3's ran first and added Chapter 2's paths;
Chapter 5's never executed.

    >>> import _bootstrap  # 03_structured_outputs/solutions
    >>> import _bootstrap as second  # intended: 05_context_window/with_sdk
    >>> _bootstrap is second
    True

Chapters 3 and 4 never noticed because their bootstrap path lists overlap and
their test files import no spine code. Chapter 5 needed a path neither of them
adds, so it is the first to break -- which is how latent coupling usually
announces itself: not when it is introduced, but two chapters later.

The fix here is not a cleverer bootstrap. It is having nothing to bootstrap:
the code worth testing has no cross-chapter dependency, so it does not import
one.
"""

from __future__ import annotations

import json
from typing import Any

Item = dict[str, Any]

# Four characters per token is wrong and good enough. It never needs a download,
# it is within ~15% for English JSON, and you spend it on a budget you enforce
# with a margin of your own choosing. See README section 2b for the measurement.
CHARS_PER_TOKEN = 4

_PAIR_TYPES = frozenset({"function_call", "function_call_output"})


def tokens(items: list[Item]) -> int:
    """Estimated tokens for a list of session items."""
    return len(json.dumps(items)) // CHARS_PER_TOKEN


def drop_orphans(items: list[Item]) -> list[Item]:
    """
    Remove tool calls missing their result, and results missing their call.

    A window sliced by count can begin on a `function_call_output` whose
    `function_call` fell outside it -- the model is handed an answer to a
    question it cannot see having asked. Chapter 4's `limit=` table produced
    exactly that at `limit=2` and `limit=6`.

    Items are TypedDicts. Use `.get()`, never attribute access.
    """
    calls = {i.get("call_id") for i in items if i.get("type") == "function_call"}
    outputs = {i.get("call_id") for i in items if i.get("type") == "function_call_output"}
    paired = calls & outputs
    return [i for i in items if i.get("type") not in _PAIR_TYPES or i.get("call_id") in paired]


def align_to_turn_start(items: list[Item]) -> list[Item]:
    """
    Advance the window to begin on a user message.

    THE DEFECT THIS EXISTS FOR, found by running `filter_demo.py` PART 3 rather
    than by reasoning about it. A window can be perfectly orphan-free and still
    be rejected:

        400 INVALID_ARGUMENT
        "Please ensure that function call turn comes immediately after a user
         turn or after a function response turn."

    `drop_orphans` had kept a matched call/result pair. The window still opened
    on an assistant message with a `function_call` after it. Every pair intact,
    structure illegal.

    > **Pairing is necessary and not sufficient.** A conversation is not a bag of
    > items that reference each other; it is a sequence with legal start
    > positions. Guarding one invariant does not make a request valid -- it makes
    > one specific failure impossible, which is a much smaller claim.

    `drop_orphans` stays anyway: it is cheaper, it catches a *trailing* call whose
    result never arrived, and section 3 needs you to meet it before you meet its
    hole.
    """
    for index, item in enumerate(items):
        if item.get("role") == "user":
            return items[index:]
    return []


def trim_to_budget(items: list[Item], budget: int) -> list[Item]:
    """
    Keep the newest items that fit `budget`, repair the pairs, align to a turn.

    NOTE WHAT THIS DOES NOT DO: it never constructs an item. Every element of the
    result is an object that came in. A trimmer that rebuilds items drops
    `provider_data` -- which on Gemini 3.x carries the `thought_signature` the
    model requires back on replay -- and the resulting 400 mentions neither
    trimming nor tokens. `test_trim.py` asserts identity, not equality, for
    exactly this reason.
    """
    kept: list[Item] = []
    for item in reversed(items):
        if kept and tokens([*kept, item]) > budget:
            break
        kept.insert(0, item)
    return align_to_turn_start(drop_orphans(kept))
