"""
Chapter 5's golden dataset. Four cases, one control, one no-op check.

    uv run python 05_context_window/solutions/check_compaction.py
    uv run python 05_context_window/solutions/check_compaction.py --only 1,2

Roughly 12 minutes. Small on purpose: this chapter's subject is LONG
conversations, and a dataset of five twelve-turn cases would be 150+ requests --
half a day of free-tier quota for one run, on the chapter least able to afford
it.

The bulk of the proof is offline instead (`with_sdk/test_trim.py`,
`with_sdk/test_compaction.py`, 23 tests, ~1 second, no API key). What is left
here is only what genuinely needs a model:

    C1  a fact from turn 1 survives a fold
    C2  THE CONTROL -- the same turns with a tail window, which must NOT
    C3  a long conversation completes at all
    C4  under budget, the transcript is passed through untouched

C2 IS THE LOAD-BEARING CASE. Without it, C1 is a claim about one run of a
non-deterministic system. Chapter 4 shipped a control contaminated by a shared
context object and it was convincing for a whole afternoon, so the fact under
test here is deliberately one that ONLY the transcript can carry -- it is not in
the `User` context, no tool returns it, and nothing after turn 1 repeats it.

C4 IS THE QUIET ONE. Most of what a context filter does is nothing. A filter that
mangles short conversations while fixing long ones has made things worse for the
overwhelming majority of real traffic, and no amount of C1 passing would show it.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
from dataclasses import dataclass, field
from typing import Any

from agents import RunConfig, Runner
from agents.run_config import CallModelData, ModelInputData

import _bootstrap_spine5  # noqa: F401  -- must precede every spine import
import expense_store
from compaction import Compactor
from context_filter import tokens, trim_to_budget
from expense_agent_v4 import _flatten
from expense_agent_v5 import DEFAULT_BUDGET, agent, make_session
from spendly_context import default_user

Checks = list[tuple[str, bool]]

PAUSE_BETWEEN_TURNS = 20.0
PAUSE_BETWEEN_CASES = 45.0

# Small enough that a handful of turns crosses it. The shipping default is 3000;
# this is a test fixture, not a recommendation.
TEST_BUDGET = 700

# The fact under test. Stated once, in turn 1, and nowhere else in the run.
SECRET_TURN = (
    "I am reconciling this month for a visa application, so accuracy matters. Log 500 at Metro."
)


class TailWindow:
    """The control strategy: drop the head instead of summarising it."""

    def __init__(self, budget: int) -> None:
        self.budget = budget
        self.summarisations = 0

    def __call__(self, data: CallModelData[Any]) -> ModelInputData:
        items = data.model_data.input
        if tokens(items) <= self.budget:  # type: ignore[arg-type]
            return data.model_data
        return ModelInputData(
            input=trim_to_budget(items, self.budget),  # type: ignore[arg-type]
            instructions=data.model_data.instructions,
        )


@dataclass
class Turn:
    prompt: str
    verify: Any = None


@dataclass
class Case:
    number: int
    name: str
    expectation: str
    turns: list[Turn] = field(default_factory=list)
    strategy: str = "compaction"  # or "tail"
    budget: int = TEST_BUDGET


# --------------------------------------------------------------------- checks


def survived_the_fold(run: Any, folds: int) -> Checks:
    answer = run.final_answer.lower()
    return [
        ("a fold actually fired (otherwise this case tests nothing)", folds >= 1),
        ("recovered 'visa' from turn 1", "visa" in answer),
        ("did not claim to have lost it", "don't have" not in answer and "not have" not in answer),
    ]


def did_not_survive(run: Any, folds: int) -> Checks:
    """
    The control. It must FAIL to recover the fact.

    A control that passes the same assertion as the treatment is not a control;
    it is a second copy of the treatment. This asserts the opposite outcome, and
    if it ever starts recovering 'visa' the right response is to make the
    conversation longer, never to delete the case.
    """
    answer = run.final_answer.lower()
    return [
        ("no summarisation happened (tail window does not summarise)", folds == 0),
        ("did NOT recover 'visa' from turn 1", "visa" not in answer),
    ]


def completed_without_error(run: Any, _folds: int) -> Checks:
    return [
        ("the run produced a reply at all", run.reply is not None),
        ("no 400 / output error", not run.output_error),
        ("did not burn max_turns", not run.hit_max_iterations),
    ]


def logged_normally(run: Any, folds: int) -> Checks:
    """
    C4: under budget the filter must not have touched anything.

    THIS CHECK WAS WRONG ABOUT ITS SUBJECT ON ITS FIRST OUTING, and the way it
    failed is the reason it is worth reading.

    It ran at the 700-token fixture budget and asserted `folds == 0`. It passed.
    Re-run an hour later, unchanged, it FAILED -- the same two turns, the same
    agent, one fold. The conversation sits within a few tokens of 700, so whether
    it crosses depends on how verbose the model felt that minute.

    The claim is "under budget, the filter is a no-op". The check never
    established that the conversation WAS under budget, so what it actually
    measured was the model's word count.

    The fix is not a bigger tolerance. It is to make the premise true by
    construction: run this case at the SHIPPING budget, where a two-turn expense
    conversation is nowhere near the limit, and assert the premise as its own
    check so that if it ever stops holding the case says so instead of quietly
    testing nothing.

    > A flaky check is usually a check whose premise you forgot to assert.
    """
    return [
        ("the conversation really is under budget", tokens(run.session_items) <= DEFAULT_BUDGET),
        ("no fold fired", folds == 0),
        ("branch is logged", run.branch == "logged"),
        ("the expense was written", "log_expense" in run.executed_names),
    ]


CASES: list[Case] = [
    Case(
        1,
        "a fact from turn 1 survives a fold",
        "compaction keeps the reason stated before the first fold",
        [
            Turn(SECRET_TURN),
            Turn("Groceries."),
            Turn("How much of my food budget is left?"),
            Turn("What is my transport budget?"),
            Turn("And utilities?"),
            Turn("Remind me why I am reconciling this month."),
        ],
    ),
    Case(
        2,
        "THE CONTROL - a tail window loses it",
        "the same six turns, dropping the head instead of summarising it",
        [
            Turn(SECRET_TURN),
            Turn("Groceries."),
            Turn("How much of my food budget is left?"),
            Turn("What is my transport budget?"),
            Turn("And utilities?"),
            Turn("Remind me why I am reconciling this month."),
        ],
        strategy="tail",
    ),
    Case(
        3,
        "a long conversation completes at all",
        "no 400, no MaxTurnsExceeded, across enough turns to fold twice",
        [
            Turn("Log 1200 at Careem."),
            Turn("Transport."),
            Turn("Log 300 at Imtiaz."),
            Turn("Groceries."),
            Turn("What is my food total this month?"),
            Turn("What is my transport total?"),
            Turn("Give me both remaining budgets."),
        ],
    ),
    Case(
        4,
        "under budget, nothing is touched",
        "a two-turn conversation must not trigger the filter at all",
        [
            Turn("Log 500 at Metro."),
            Turn("Groceries."),
        ],
        # The SHIPPING budget, not the fixture budget. See `logged_normally`.
        budget=DEFAULT_BUDGET,
    ),
]

# Only the last turn of each case is graded. The turns before it exist to grow
# the transcript, and asserting on them would be asserting on Chapter 4.
CASES[0].turns[-1].verify = survived_the_fold
CASES[1].turns[-1].verify = did_not_survive
CASES[2].turns[-1].verify = completed_without_error
CASES[3].turns[-1].verify = logged_normally


async def run_case(case: Case) -> tuple[int, int, bool]:
    expense_store.reset(seeded=True)
    strategy: Any = TailWindow(case.budget) if case.strategy == "tail" else Compactor(case.budget)
    session = make_session(f"ch5_case_{case.number}_{case.strategy}")
    await session.clear_session()
    config = RunConfig(call_model_input_filter=strategy)
    user = default_user()

    total = passed = 0
    ok = True

    for number, turn in enumerate(case.turns, start=1):
        result = await Runner.run(
            agent, turn.prompt, context=user, session=session, run_config=config, max_turns=15
        )
        run = _adapt(result, await session.get_items())
        folds = strategy.summarisations
        print(f"    turn {number}: {turn.prompt[:56]}")
        print(f"      folds={folds}  {run.final_answer[:66]}")

        if turn.verify is not None:
            for label, check in turn.verify(run, folds):
                total += 1
                passed += check
                ok &= check
                print(f"      {'PASS' if check else 'FAIL'}  {label}")

        if number < len(case.turns):
            await asyncio.sleep(PAUSE_BETWEEN_TURNS)

    return total, passed, ok


class _Adapted:
    __slots__ = (
        "branch",
        "executed_names",
        "final_answer",
        "hit_max_iterations",
        "output_error",
        "reply",
        "session_items",
    )


def _adapt(result: Any, items: Any) -> Any:
    """Minimal view of a run. The full `SdkRun` lives in `expense_agent_v5`."""
    from agents.items import ToolCallItem

    run = _Adapted()
    run.session_items = items
    reply = result.final_output
    run.reply = reply
    run.output_error = ""
    run.hit_max_iterations = False
    run.executed_names = [
        str(getattr(i.raw_item, "name", "?"))
        for i in result.new_items
        if isinstance(i, ToolCallItem)
    ]
    branch = "?"
    for name in ("logged", "reported", "need_more_info", "refused"):
        if getattr(reply, name, None) is not None:
            branch = name
            break
    run.branch = branch

    # Reuse the spine's flattener rather than re-deriving which field each branch
    # keeps its prose in. The first version of this file guessed `.message` for
    # every branch; the real names are `reply`, `question` and so on, so every
    # answer fell through to `str(reply)` -- a repr that happens to CONTAIN the
    # text, which means the substring assertions would have passed while testing
    # the wrong string. A check that is accidentally right is a check you cannot
    # trust the next time it matters.
    run.final_answer = _flatten(reply)
    return run


async def main(wanted: set[int] | None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)

    cases = [c for c in CASES if wanted is None or c.number in wanted]
    print(f"Chapter 5's dataset - {len(cases)} cases")
    print("Roughly 12 minutes. The offline tests carry the rest of the proof.\n")

    total = passed = 0
    failed: list[int] = []
    for index, case in enumerate(cases):
        print(f"CASE C{case.number}: {case.name}")
        print(f"  expect: {case.expectation}")
        a, b, ok = await run_case(case)
        total, passed = total + a, passed + b
        if not ok:
            failed.append(case.number)
        print()
        if index < len(cases) - 1:
            await asyncio.sleep(PAUSE_BETWEEN_CASES)

    print("=" * 72)
    print(f"{passed}/{total} checks passed")
    if failed:
        print(f"FAILED CASES: {failed}")
        if 2 in failed:
            print()
            print("C2 is the control. If it failed because the tail window DID recover")
            print("the fact, the conversation is too short to distinguish the strategies.")
            print("Lengthen it. Do not delete the case, and do not weaken the assertion.")
    else:
        print("All cases passed.")
    return 0 if not failed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    picked = {int(n) for n in args.only.split(",") if n.strip()} or None
    raise SystemExit(asyncio.run(main(picked)))
