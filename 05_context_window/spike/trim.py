"""
SPIKE -- disposable. Not imported by the project, not covered by the golden
dataset, safe to delete the moment Chapter 5 validates.

It exists to answer one question: what does trimming a transcript actually
involve, once you stop counting items and start counting tokens?

Chapter 4 handed you `get_items(limit=N)` and showed it can slice a tool call
away from its result. This is the 50 lines underneath the fix. Chapter 5's
`with_sdk/` layer then throws it away and uses the SDK's own seam, forever
after.

    uv run python 05_context_window/spike/trim.py

Runs offline, costs nothing, replays a REAL 22-item transcript captured from
Chapter 4's `growth_demo` session -- the same one the Ch4 table measured at
4,782 characters.
"""

import json
from pathlib import Path
from typing import Any

Item = dict[str, Any]

TRANSCRIPT = Path(__file__).with_name("transcript.json")

# Four characters per token is wrong and good enough. It is within ~15% for
# English JSON, it never needs a download, and you are spending it on a budget
# you enforce with a margin. Section 2b measures the error against tiktoken.
CHARS_PER_TOKEN = 4


def tokens(items: list[Item]) -> int:
    """Estimated tokens for a list of items."""
    return len(json.dumps(items)) // CHARS_PER_TOKEN


def drop_orphans(items: list[Item]) -> list[Item]:
    """
    Remove tool calls missing their result, and results missing their call.

    A window sliced by count can begin on a `function_call_output` whose
    `function_call` fell outside it. The model is then handed an answer to a
    question it cannot see having asked, and the provider rejects the request.

    Items are TypedDicts. Use .get(), never attribute access.
    """
    calls = {i.get("call_id") for i in items if i.get("type") == "function_call"}
    outputs = {i.get("call_id") for i in items if i.get("type") == "function_call_output"}
    paired = calls & outputs
    pair_types = {"function_call", "function_call_output"}

    return [i for i in items if i.get("type") not in pair_types or i.get("call_id") in paired]


def trim(items: list[Item], budget: int) -> list[Item]:
    """Keep the newest items that fit `budget` tokens, then repair the seam."""
    kept: list[Item] = []
    for item in reversed(items):
        if tokens([*kept, item]) > budget and kept:
            break
        kept.insert(0, item)
    return drop_orphans(kept)


def main() -> None:
    items: list[Item] = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
    print(f"  loaded {len(items)} items, {tokens(items)} est. tokens\n")
    print(f"  {'budget':>8}{'kept':>6}{'tokens':>8}{'first item':>24}  orphans?  legal?")
    print("  " + "-" * 66)

    for budget in (2000, 1000, 600, 400, 200, 100):
        window = trim(items, budget)
        first = str(window[0].get("role") or window[0].get("type")) if window else "-"
        leaked = window != drop_orphans(window)
        # A window may be orphan-free and STILL be rejected. Providers require a
        # conversation to open at a turn boundary -- a `function_call` must follow
        # a user turn or a tool result, never an assistant message. This column is
        # the hole in `drop_orphans`, and finding it is Practice 3.
        legal = bool(window) and window[0].get("role") == "user"
        print(
            f"  {budget:>8}{len(window):>6}{tokens(window):>8}{first:>24}"
            f"  {'YES' if leaked else 'no':>8}  {'yes' if legal else 'NO':>6}"
        )

    print("\n  Compare the naive version -- a tail window that counts items:")
    for limit in (2, 6):
        naive = items[-limit:]
        first = str(naive[0].get("role") or naive[0].get("type"))
        orphaned = naive != drop_orphans(naive)
        print(f"    items[-{limit}:] -> first={first:22} orphaned={'YES' if orphaned else 'no'}")

    print("\n  Now read the `legal?` column again. Every row is orphan-free, and")
    print("  most of them are still NO -- they open on an assistant message.")
    print("  `drop_orphans` fixes the failure it was written for and no other.")


if __name__ == "__main__":
    main()
