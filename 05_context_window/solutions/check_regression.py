"""
The regression rule, two chapters deep.

    uv run python 05_context_window/solutions/check_regression.py
    uv run python 05_context_window/solutions/check_regression.py --part ch3
    uv run python 05_context_window/solutions/check_regression.py --part ch4

Chapter 4 imported Chapter 3's nine cases and ran them against v4. This imports
BOTH -- Chapter 3's nine single-turn cases and Chapter 4's five multi-turn
cases -- and runs them against v5.

    from check_expenses import CASES as CH3_CASES        <- Ch3's dataset
    from check_multiturn import CASES as CH4_CASES       <- Ch4's dataset
    from expense_agent_v5 import run_expense_agent       <- this chapter's agent

Nothing is copied, edited or re-typed. If a case is wrong, it is wrong in one
place.

THE COMPACTOR IS ATTACHED, AND THAT IS THE POINT
------------------------------------------------
The lazy version of this file would pass `compactor=None` and reproduce v4
exactly. It would pass trivially and prove nothing, because Chapter 5's whole
risk is that it changes what the model SEES on every single request.

So every case here runs with a real `Compactor` at the shipping budget. All of
these conversations are far below it, which makes this run a live test of the
property `check_compaction.py` calls C4:

    under budget, the filter must be a no-op

If the compactor mangles short conversations while fixing long ones, it has made
things worse for the overwhelming majority of real traffic -- and these fourteen
cases are what would catch it.

`--no-filter` runs without the compactor, for when you need to know whether a
failure is Chapter 5's fault or was already there.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys

from agents.memory.session import Session

import _bootstrap_spine5  # noqa: F401  -- must precede every spine import
import expense_store
from check_expenses import CASES as CH3_CASES
from check_expenses import PAUSE_BETWEEN_CASES
from check_multiturn import CASES as CH4_CASES
from check_multiturn import PAUSE_BETWEEN_TURNS
from compaction import Compactor
from expense_agent_v5 import DEFAULT_BUDGET, make_session, run_expense_agent
from spendly_context import default_user


async def run_ch3(use_filter: bool) -> tuple[int, int, list[str]]:
    """Chapter 3's nine cases. Single turn, no session -- their original conditions."""
    total = passed = 0
    failed: list[str] = []

    print(f"\n{'=' * 72}\nCHAPTER 3's dataset against v5 ({len(CH3_CASES)} cases)\n{'=' * 72}")
    for index, case in enumerate(CH3_CASES):
        expense_store.reset(seeded=True)
        print(f"\nCASE {case.number}: {case.prompt}")
        print(f"  expect: {case.expectation}")

        # A fresh Compactor per case. It caches ONE conversation's summary, and
        # sharing it across cases would be the exact leak the spine's docstring
        # warns about -- with a golden dataset as the victim.
        compactor = Compactor(DEFAULT_BUDGET) if use_filter else None
        run = await run_expense_agent(
            case.prompt, user=default_user(), session=None, compactor=compactor
        )

        case_ok = True
        for label, ok in case.verify(run):
            total += 1
            passed += ok
            case_ok &= ok
            print(f"    {'PASS' if ok else 'FAIL'}  {label}")

        folds = compactor.summarisations if compactor else 0
        print(f"  branch={run.branch}  turns={run.iterations}  folds={folds}")
        if folds:
            print("  NOTE: a fold fired on a single-turn case. The budget is too low,")
            print("        or _split_at is cutting where it should not.")
        if not case_ok:
            failed.append(f"ch3/{case.number}")
        if index < len(CH3_CASES) - 1:
            await asyncio.sleep(PAUSE_BETWEEN_CASES)

    return total, passed, failed


async def run_ch4(use_filter: bool) -> tuple[int, int, list[str]]:
    """
    Chapter 4's five multi-turn cases.

    Chapter 4's own `run_case` calls Chapter 4's agent directly, so it cannot be
    pointed at v5. The loop is reproduced here -- forty lines, and the same cost
    Chapter 4 paid to reuse Chapter 3's harness.

    > The lesson repeats because the mistake repeats: a harness that hard-codes
    > the thing it tests can be read by the next chapter but not RUN by it.
    > Chapter 6 should take an agent as an argument.
    """
    total = passed = 0
    failed: list[str] = []

    print(f"\n{'=' * 72}\nCHAPTER 4's dataset against v5 ({len(CH4_CASES)} cases)\n{'=' * 72}")
    for index, case in enumerate(CH4_CASES):
        expense_store.reset(seeded=True)
        print(f"\nCASE M{case.number}: {case.name}")
        print(f"  expect: {case.expectation}")

        sessions: dict[str, Session] = {}
        compactor = Compactor(DEFAULT_BUDGET) if use_filter else None
        case_ok = True

        for turn_number, turn in enumerate(case.turns, start=1):
            if turn.before is not None:
                turn.before()
                print("    [the world changed between turns]")

            session = None
            if case.use_session:
                # Reset per CASE, never per TURN -- Chapter 4's defect 4.
                name = turn.session_id or f"reg_case_{case.number}"
                if name not in sessions:
                    fresh = make_session(name)
                    await fresh.clear_session()
                    sessions[name] = fresh
                session = sessions[name]

            run = await run_expense_agent(
                turn.prompt, user=turn.user, session=session, compactor=compactor
            )
            print(f"    turn {turn_number}: {turn.prompt}")
            for label, ok in turn.verify(run):  # type: ignore[arg-type]
                total += 1
                passed += ok
                case_ok &= ok
                print(f"      {'PASS' if ok else 'FAIL'}  {label}")
            folds = compactor.summarisations if compactor else 0
            # Print folds even when zero. Diagnosing a Chapter 4 failure here
            # means answering "did the compactor touch this?" first, and the
            # first version of this harness printed folds for Chapter 3's cases
            # and not Chapter 4's -- so the one question worth asking needed a
            # separate probe to answer. A harness that omits the number you will
            # reach for is a harness you will edit under pressure.
            print(f"      branch={run.branch}  turns={run.iterations}  folds={folds}")
            await asyncio.sleep(PAUSE_BETWEEN_TURNS)

        if not case_ok:
            failed.append(f"ch4/M{case.number}")
        if index < len(CH4_CASES) - 1:
            await asyncio.sleep(PAUSE_BETWEEN_TURNS)

    return total, passed, failed


async def main(part: str, use_filter: bool) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)

    print("The regression rule, run against Spendly Lite v5.")
    print(f"compactor: {'ON at budget ' + str(DEFAULT_BUDGET) if use_filter else 'OFF'}")
    print("Expect roughly 25 minutes for both parts.")

    total = passed = 0
    failed: list[str] = []

    if part in {"both", "ch3"}:
        a, b, c = await run_ch3(use_filter)
        total, passed, failed = total + a, passed + b, failed + c
    if part in {"both", "ch4"}:
        a, b, c = await run_ch4(use_filter)
        total, passed, failed = total + a, passed + b, failed + c

    print(f"\n{'=' * 72}")
    print(f"{passed}/{total} checks passed")
    if failed:
        print(f"FAILED CASES: {failed}")
        print()
        print("A failure here means CHAPTER 5 BROKE AN EARLIER CHAPTER, which is")
        print("the one outcome the regression rule exists to catch. Diagnose the")
        print("shape first -- `branch=none turns=0` is quota, not a regression.")
        print("Then re-run with --no-filter. If it passes there, the compactor is")
        print("at fault; if it fails there too, the defect predates this chapter.")
    else:
        scope = {"both": "Chapters 3 and 4", "ch3": "Chapter 3", "ch4": "Chapter 4"}[part]
        print(f"All cases passed. {scope} survived Chapter 5.")
    return 0 if not failed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--part", choices=["both", "ch3", "ch4"], default="both")
    parser.add_argument("--no-filter", action="store_true", help="run without the compactor")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.part, not args.no_filter)))
