"""
Spendly Lite v5 -- v4, plus a context budget it cannot exceed.

    uv run python 05_context_window/solutions/expense_agent_v5.py

WHAT CHANGED, AND HOW LITTLE
----------------------------
v4 imported unchanged: the agent, the tools, the storage, the reply types, the
system prompt, the backoff. This file adds one argument to one call:

    Runner.run(agent, prompt, ..., run_config=RunConfig(call_model_input_filter=...))

That is the entire delta, and it is the same shape as Chapter 4's: memory did
not require rewriting the tools, and neither does managing it. **If adding a
context budget had meant touching `expense_tools.py`, the budget was in the
wrong place.**

THE ONE DESIGN DECISION WORTH ARGUING WITH
------------------------------------------
`Compactor` is passed IN, one per conversation. It is not a module-level object
and not an attribute of the agent, because it holds a cached summary of ONE
conversation. An agent is shared by every user; a summary is not.

Chapter 4 spent a golden-dataset case (M3) proving one `session_id` must not see
another's transcript. A shared compactor would reintroduce exactly that leak
through a different door, and it would be harder to see: the transcripts stay
separate and only the SUMMARY crosses over, so the agent recites a fact from
somebody else's conversation with no trace of where it came from.

    A cache belongs wherever the thing it caches belongs. The summary
    describes a session, so it lives and dies with the session.

`make_run_state()` exists to make that hard to get wrong: it hands back a
session and a compactor together, because they have the same lifetime.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents import RunConfig, Runner
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.memory.session import Session

import _bootstrap_spine5  # noqa: F401  -- must precede every spine import
from compaction import Compactor
from expense_agent_v4 import (
    REJECTED_PREFIX,
    SdkRun,
    _flatten,
    agent,
    make_session,
)
from spendly_context import User, default_user

# Big enough that ordinary two-turn work never triggers a fold, small enough
# that a long conversation does. Section 2 is about why this number is a policy
# choice and not a fact -- the model's real limit is orders of magnitude larger,
# and you pick a budget from cost and latency, not from what fits.
DEFAULT_BUDGET = 3000

SESSION_DB = Path(__file__).parent / "data" / "sessions.db"


@dataclass
class RunState:
    """A session and the compactor that caches ITS summary. Same lifetime."""

    session: Session
    compactor: Compactor


def make_run_state(session_id: str, *, budget: int = DEFAULT_BUDGET) -> RunState:
    """Build both halves of one conversation's state together."""
    return RunState(session=make_session(session_id), compactor=Compactor(budget))


async def run_expense_agent(
    prompt: str,
    *,
    user: User | None = None,
    session: Session | None = None,
    compactor: Compactor | None = None,
    max_turns: int = 15,
) -> SdkRun:
    """
    One turn.

    Every argument still defaults to the older behaviour. `compactor=None` runs
    with no filter at all, which is exactly v4 -- and that is what lets
    `check_regression.py` push Chapter 3's nine cases and Chapter 4's five
    through this function and get the earlier chapters' answers back.

    A new capability that cannot be turned off is not a capability, it is a
    rewrite.
    """
    who = user or default_user()
    config = RunConfig(call_model_input_filter=compactor) if compactor else None

    try:
        result = await _run_with_backoff(prompt, max_turns, who, session, config)
    except Exception as exc:
        name = type(exc).__name__
        if name == "MaxTurnsExceeded":
            return SdkRun(
                reply=None,
                final_answer=f"[max turns exceeded: {exc}]",
                hit_max_iterations=True,
            )
        if name in {"ModelBehaviorError", "UserError"}:
            return SdkRun(reply=None, final_answer="", output_error=f"{name}: {exc}")
        raise

    calls = [item for item in result.new_items if isinstance(item, ToolCallItem)]
    outputs = [item for item in result.new_items if isinstance(item, ToolCallOutputItem)]
    names = [str(getattr(c.raw_item, "name", "?")) for c in calls]
    rejected = [str(o.output).startswith(REJECTED_PREFIX) for o in outputs]
    reply = result.final_output
    stored = await session.get_items() if session is not None else []

    return SdkRun(
        reply=reply,
        final_answer=_flatten(reply),
        iterations=len(result.raw_responses),
        tool_names=names,
        executed_names=[
            name for name, was_rejected in zip(names, rejected, strict=False) if not was_rejected
        ],
        input_tokens=result.context_wrapper.usage.input_tokens,
        session_items=len(stored),
        session_text=str(stored),
    )


async def _run_with_backoff(
    prompt: str,
    max_turns: int,
    user: User,
    session: Session | None,
    config: RunConfig | None,
    attempts: int = 4,
) -> Any:
    """
    v4's backoff, carried forward with one extra argument.

    Its docstring explains why `MaxTurnsExceeded` is in the transient set: under
    sustained 429s the SDK burns turns internally and raises a runaway-agent
    error for what is actually a quota problem.
    """
    delay = 20.0
    for attempt in range(1, attempts + 1):
        try:
            return await Runner.run(
                agent,
                prompt,
                max_turns=max_turns,
                context=user,
                session=session,
                run_config=config,
            )
        except Exception as exc:
            name = type(exc).__name__
            transient = {
                "RateLimitError",
                "MaxTurnsExceeded",
                "APITimeoutError",
                "APIConnectionError",
                "InternalServerError",
            }
            if not (name in transient or "429" in str(exc)) or attempt == attempts:
                raise
            print(f"  [{name} - waiting {delay:.0f}s, attempt {attempt}]")
            await asyncio.sleep(delay)
            delay *= 1.8
    raise RuntimeError("unreachable")


async def main() -> None:
    """A short conversation, with the budget low enough to make compaction fire."""
    import expense_store

    expense_store.reset(seeded=True)
    state = make_run_state("demo_v5", budget=900)
    await state.session.clear_session()

    turns = [
        "I am tracking this month for a visa application, so keep it accurate. Log 500 at Metro.",
        "Groceries.",
        "How much of my food budget is left?",
        "Why was I tracking this month again?",
    ]
    for number, prompt in enumerate(turns, start=1):
        run = await run_expense_agent(prompt, session=state.session, compactor=state.compactor)
        print(f"\n  turn {number}: {prompt}")
        print(f"    branch={run.branch} folds={state.compactor.summarisations}")
        print(f"    {run.final_answer[:100]}")
        await asyncio.sleep(8)


if __name__ == "__main__":
    asyncio.run(main())
