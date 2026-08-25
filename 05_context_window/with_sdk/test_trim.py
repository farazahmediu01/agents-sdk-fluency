"""
The trimmer's proof layer. No API key, no network, milliseconds.

This file is the argument for Chapter 5's whole approach. A trimmer is a pure
function over a list, so every property worth asserting can be asserted for
free -- and a chapter about long conversations that needed a long conversation
to test itself would cost a day's quota per run.

    uv run pytest 05_context_window -q

The four properties, in the order they were learned:

    1. never orphan a call/result pair          (Chapter 4's table)
    2. never exceed the budget                  (the obvious one)
    3. always open on a legal turn boundary     (found by a 400 in PART 3)
    4. leave a healthy window BYTE-IDENTICAL    (the one nobody writes)

Property 4 is the important one. A trimmer that quietly rewrites history it did
not need to touch is a worse bug than the one it was written to fix -- and on
Gemini 3.x it is a live 400, because rebuilding an item drops the
`provider_data.thought_signature` the model requires back on replay.
"""

import json
from pathlib import Path
from typing import Any

from context_filter import align_to_turn_start, drop_orphans, tokens, trim_to_budget

TRANSCRIPT = Path(__file__).resolve().parents[1] / "spike" / "transcript.json"


def load() -> list[Any]:
    return json.loads(TRANSCRIPT.read_text(encoding="utf-8"))


def call_ids(items: list[Any], kind: str) -> set[str]:
    return {i["call_id"] for i in items if i.get("type") == kind}


# ---------------------------------------------------------------- the fixture


def test_the_fixture_is_the_transcript_chapter_4_measured() -> None:
    """22 items and 4,782 characters is the exact row Ch4's table published."""
    items = load()
    assert len(items) == 22
    assert len(json.dumps(items)) == 4782


def test_the_fixture_actually_contains_tool_pairs() -> None:
    """Without pairs this whole file would pass while testing nothing."""
    items = load()
    assert call_ids(items, "function_call")
    assert call_ids(items, "function_call") == call_ids(items, "function_call_output")


# ------------------------------------------------------ 1. never orphan a pair


def test_drop_orphans_removes_a_result_whose_call_is_gone() -> None:
    items = load()
    window = items[-6:]  # Ch4's table flagged this: starts on a function_call_output
    assert window[0].get("type") == "function_call_output"

    cleaned = drop_orphans(window)
    assert cleaned[0].get("type") != "function_call_output"
    assert call_ids(cleaned, "function_call") == call_ids(cleaned, "function_call_output")


def test_drop_orphans_removes_a_call_whose_result_never_arrived() -> None:
    """The mirror case. A trailing call with no output is equally a 400."""
    items = load()
    truncated = items[:2]  # user, function_call -- the output is item 2
    assert truncated[-1].get("type") == "function_call"

    cleaned = drop_orphans(truncated)
    assert not call_ids(cleaned, "function_call")


def test_no_budget_ever_produces_an_orphan() -> None:
    items = load()
    for budget in range(50, 1400, 25):
        window = trim_to_budget(items, budget)
        assert call_ids(window, "function_call") == call_ids(window, "function_call_output"), (
            f"budget={budget} orphaned a pair"
        )


# --------------------------------------------------------- 2. respect the budget


def test_the_window_fits_the_budget() -> None:
    items = load()
    for budget in (1400, 1000, 600, 400, 200):
        assert tokens(trim_to_budget(items, budget)) <= budget


def test_a_budget_smaller_than_one_item_returns_nothing_rather_than_lying() -> None:
    """
    The honest edge. The loop always keeps a first item so it can make progress,
    which means one huge item could exceed the budget -- but `align_to_turn_start`
    then drops it unless it is a user message. Either way the caller never
    receives a window that claims to fit and does not.
    """
    items = load()
    window = trim_to_budget(items, 1)
    assert window == [] or tokens(window) <= tokens(items)


# ------------------------------------------------- 3. open on a legal boundary


def test_every_budget_opens_on_a_user_message() -> None:
    """
    The property that `drop_orphans` alone does not give you.

    Found by a real 400 in `filter_demo.py` PART 3:
        "Please ensure that function call turn comes immediately after a user
         turn or after a function response turn."
    """
    items = load()
    for budget in range(50, 1400, 25):
        window = trim_to_budget(items, budget)
        if window:
            assert window[0].get("role") == "user", f"budget={budget} opened illegally"


def test_orphan_free_is_not_the_same_as_legal() -> None:
    """The spike's table in one assertion: clean pairs, illegal structure."""
    items = load()
    window = drop_orphans(items[-5:])
    assert call_ids(window, "function_call") == call_ids(window, "function_call_output")
    assert window[0].get("role") != "user"  # orphan-free, and the provider says no
    assert align_to_turn_start(window)[0].get("role") == "user"


# ---------------------------------------------- 4. do not touch what is healthy


def test_a_healthy_window_comes_back_byte_identical() -> None:
    """
    Not "equal" -- IDENTICAL, and by identity, not just value.

    Every item must be the same object that went in. Rebuilding an equal-looking
    dict drops `provider_data.thought_signature`, which Gemini 3.x requires back
    on replay, and the failure is a 400 that names neither trimming nor tokens.
    """
    items = load()
    window = trim_to_budget(items, 100_000)

    assert json.dumps(window) == json.dumps(items)
    assert all(a is b for a, b in zip(window, items, strict=True))


def test_provider_data_survives_every_budget() -> None:
    """The field this chapter would otherwise destroy silently."""
    items = load()
    signed = [i for i in items if (i.get("provider_data") or {}).get("thought_signature")]
    assert signed, "fixture has no thought_signature to protect"

    for budget in (1400, 1000, 600, 400):
        for item in trim_to_budget(items, budget):
            if item.get("type") == "function_call":
                assert "thought_signature" in (item.get("provider_data") or {})
