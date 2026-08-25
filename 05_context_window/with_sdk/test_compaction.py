"""
Compaction's proof layer. No API key, no network, milliseconds.

A compactor makes model calls, so testing it looks like it should cost money.
It does not: the model call lives in ONE method, and everything worth asserting
is the logic around it -- when to fold, how far to cut back, and what to leave
alone. Replace `_fold` with a counter and the whole policy becomes free to test.

    uv run pytest 05_context_window -q

That is the general move, and it is worth more than this file: push the
expensive dependency to a single seam, then test everything on the cheap side
of it. Chapter 6 will call this dependency injection and act like it invented it.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from compaction import Compactor, render
from context_filter import tokens

TRANSCRIPT = Path(__file__).resolve().parents[1] / "spike" / "transcript.json"


def load() -> list[Any]:
    return json.loads(TRANSCRIPT.read_text(encoding="utf-8"))


class FakeData:
    """The two fields `call_model_input_filter` actually reads."""

    def __init__(self, items: list[Any], instructions: str = "SYSTEM") -> None:
        self.model_data = _ModelData(items, instructions)


class _ModelData:
    def __init__(self, items: list[Any], instructions: str) -> None:
        self.input = items
        self.instructions = instructions


def offline(budget: int, **kwargs: Any) -> Compactor:
    """A Compactor whose summariser never touches the network."""
    compactor = Compactor(budget, **kwargs)

    async def _fold(new_items: list[Any]) -> None:
        compactor.summarisations += 1
        compactor.summary = f"<notes covering {len(new_items)} more items>"

    compactor._fold = _fold  # type: ignore[method-assign]
    return compactor


def run(compactor: Compactor, items: list[Any]) -> Any:
    return asyncio.run(compactor(FakeData(items)))  # type: ignore[arg-type]


# ------------------------------------------------- under budget: do not touch


def test_under_budget_returns_the_same_list_object() -> None:
    """
    Identity, not equality.

    A compactor that rebuilds a healthy transcript drops
    `provider_data.thought_signature` and earns a 400 that mentions neither
    summarising nor tokens. The cheapest way never to break an item is never to
    construct one.
    """
    items = load()
    compactor = offline(100_000)
    out = run(compactor, items)

    assert out.input is items
    assert compactor.summarisations == 0


def test_under_budget_leaves_the_instructions_alone() -> None:
    items = load()
    out = run(offline(100_000), items)
    assert out.instructions == "SYSTEM"


# ------------------------------------------------------ over budget: fold once


def test_over_budget_folds_and_shortens() -> None:
    items = load()
    compactor = offline(400)
    out = run(compactor, items)

    assert compactor.summarisations == 1
    assert len(out.input) < len(items)
    assert "<notes covering" in out.instructions


def test_the_summary_lands_in_instructions_not_in_the_transcript() -> None:
    """
    The design decision, asserted.

    Injecting the summary as a `user` or `assistant` item would invent a turn
    nobody took -- and the model will quote invented turns back at you.
    """
    items = load()
    out = run(offline(400), items)

    assert "<notes covering" in out.instructions
    assert "<notes covering" not in json.dumps(out.input)


def test_the_tail_still_opens_on_a_user_message() -> None:
    """Compaction does not get to skip section 3's rule."""
    for budget in (200, 300, 400, 600, 800):
        out = run(offline(budget), load())
        if out.input:
            assert out.input[0].get("role") == "user", f"budget={budget} opened illegally"


# ---------------------------------------------------------------- hysteresis


def test_a_second_call_at_the_same_length_does_not_fold_again() -> None:
    """The cache. Two model calls in one turn must not summarise twice."""
    items = load()
    compactor = offline(400)
    run(compactor, items)
    run(compactor, items)
    assert compactor.summarisations == 1


def test_growth_between_the_trigger_and_the_target_does_not_refold() -> None:
    """
    THE DEFECT THIS TEST EXISTS FOR.

    The first version recomputed the split every call and folded whenever it had
    moved -- which was nearly always. A nine-turn conversation spent THIRTEEN
    model calls summarising. The fix is that the trigger (tail > budget) and the
    target (tail cut back to budget * keep) are different numbers.

    Here: fold once, then grow the transcript a little. A compactor with
    hysteresis rides it out; one without folds again immediately.
    """
    items = load()
    compactor = offline(400)
    run(compactor, items)
    assert compactor.summarisations == 1

    grown = [*items, {"role": "user", "content": "one more short turn"}]
    run(compactor, grown)
    assert compactor.summarisations == 1, "refolded after a single small turn"


def test_enough_growth_eventually_folds_again() -> None:
    """Hysteresis must delay the fold, not prevent it."""
    items = load()
    compactor = offline(400)
    run(compactor, items)

    grown = [*items]
    for index in range(40):
        grown.append({"role": "user", "content": f"turn {index} " + "padding " * 40})
    run(compactor, grown)

    assert compactor.summarisations == 2


# --------------------------------------------------------------- the renderer


def test_render_includes_tool_calls_and_results() -> None:
    """A summary built only from prose would drop everything the tools wrote."""
    text = render(load())
    assert "[tool call]" in text
    assert "[tool result]" in text
    assert "t-shirt" in text


def test_render_is_much_smaller_than_the_json() -> None:
    items = load()
    assert len(render(items)) < len(json.dumps(items))
    assert tokens(items) > 0
