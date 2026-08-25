"""
The seam: `RunConfig(call_model_input_filter=...)`.

    uv run python 05_context_window/with_sdk/filter_demo.py

    PART 1   the filter, called directly      -- FREE, no API calls
    PART 2   how often does it actually fire? -- ~3 requests
    PART 3   a real conversation, trimmed     -- ~8 requests

PART 1 is free because a filter is an ordinary function over an ordinary list.
That is the whole point of this chapter's proof strategy: the interesting
behaviour is testable without spending a token. Only "does the agent still
work" needs the model.

Chapter 4 gave you a session that grows forever and one knob -- `limit=N` --
that counts items instead of tokens and can cut a tool call away from its
result. This is where that gets fixed properly.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from agents import RunConfig, Runner, SQLiteSession
from agents.items import TResponseInputItem
from agents.run_config import CallModelData, ModelInputData

import _bootstrap_sdk5  # noqa: F401  -- must precede the packing_agent import
from context_filter import tokens, trim_to_budget
from packing_agent import Traveller, packing_agent

TRANSCRIPT = Path(__file__).resolve().parents[1] / "spike" / "transcript.json"
DB = Path(__file__).with_name("data") / "filter_demo.db"
PACE_SECONDS = 8.0  # the 15/min per-model free-tier limit


def make_filter(budget: int, log: list[tuple[int, int]]) -> Any:
    """
    Build a `call_model_input_filter` that trims to `budget` and records each call.

    THE TWO CASTS ARE THE POINT, not noise to skim past. `ModelInputData.input`
    is a `list[TResponseInputItem]` -- a union of TypedDicts -- and `list` is
    INVARIANT, so pyright rejects passing it where a `list[dict[str, Any]]` is
    wanted and rejects the return trip too:

        Argument of type "list[TResponseInputItem]" cannot be assigned to
        parameter "items" of type "list[Item]"

    That is not pedantry. It is the type system noticing that this function sits
    on a boundary between two views of the same bytes: the SDK's precise one and
    the trimmer's structural one. `context_filter` deliberately keeps the
    structural view -- it is a data function, it should not need the SDK to exist
    -- so the conversion belongs here, once, named, at the seam.

    A cast changes nothing at runtime. It records where you took responsibility.
    """

    def _filter(data: CallModelData[Any]) -> ModelInputData:
        original = cast(list[dict[str, Any]], data.model_data.input)
        kept = trim_to_budget(original, budget)
        log.append((len(original), len(kept)))
        return ModelInputData(
            input=cast(list[TResponseInputItem], kept),
            instructions=data.model_data.instructions,
        )

    return _filter


# --------------------------------------------------------------------------
# PART 1 -- free. A filter is just a function.
# --------------------------------------------------------------------------
def part1() -> None:
    print("\nPART 1 - the filter, called directly. No API calls.\n")
    items: list[Any] = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
    print(f"  the captured transcript: {len(items)} items, {tokens(items)} est. tokens\n")
    print(f"  {'budget':>8}{'in':>6}{'out':>6}{'tokens':>8}   first item kept")
    print("  " + "-" * 52)
    for budget in (2000, 800, 400, 200):
        out = trim_to_budget(items, budget)
        first = str(out[0].get("role") or out[0].get("type")) if out else "-"
        print(f"  {budget:>8}{len(items):>6}{len(out):>6}{tokens(out):>8}   {first}")
    print("\n  Every row starts on a user message, so every row is legal. Compare")
    print("  Chapter 4's limit= table, where limit=2 and limit=6 both opened on a")
    print("  tool result -- and note that being orphan-free was not enough either.")


# --------------------------------------------------------------------------
# PART 2 -- how often does the filter fire?
# --------------------------------------------------------------------------
async def part2() -> None:
    print("\n\nPART 2 - how often does the filter actually fire?\n")
    print("  Predict before reading: ONE user message that needs two tool calls.")
    print("  How many times does call_model_input_filter run?\n")

    log: list[tuple[int, int]] = []
    config = RunConfig(call_model_input_filter=make_filter(100_000, log))
    traveller = Traveller(name="Faraz", bag_limit_kg=20.0)

    result = await Runner.run(
        packing_agent,
        "Pack a raincoat at 0.6 kg and a book at 0.4 kg.",
        context=traveller,
        run_config=config,
    )
    print(f"  agent: {str(result.final_output)[:64]}")
    seen = [pair[0] for pair in log]
    print(f"\n  the filter fired {len(log)} times, seeing {seen} items")
    print("\n  Not once per TURN -- once per MODEL CALL. A turn that calls two")
    print("  tools is three model calls, so a summariser wired here would run")
    print("  three times and bill you three times. Section 6 is about when to fire.")


# --------------------------------------------------------------------------
# PART 3 -- a real conversation under a tight budget
# --------------------------------------------------------------------------
async def part3() -> None:
    print("\n\nPART 3 - a real conversation, trimmed hard.\n")
    DB.parent.mkdir(parents=True, exist_ok=True)
    session = SQLiteSession("filter_demo", DB)
    await session.clear_session()

    log: list[tuple[int, int]] = []
    config = RunConfig(call_model_input_filter=make_filter(400, log))
    traveller = Traveller(name="Faraz", bag_limit_kg=20.0)

    turns = [
        "Pack two t-shirts, 0.2 kg each.",
        "Add a pair of jeans, 0.8 kg.",
        "Add a jacket, 1.2 kg.",
        "In one sentence, everything I have packed so far?",
    ]
    for number, prompt in enumerate(turns, start=1):
        before = len(log)
        result = await Runner.run(
            packing_agent, prompt, context=traveller, session=session, run_config=config
        )
        stored = len(await session.get_items())
        moves = " ".join(f"{a}->{b}" for a, b in log[before:])
        print(f"  turn {number}  stored={stored:>3}  in->sent  {moves}")
        print(f"           {str(result.final_output)[:70]}")
        await asyncio.sleep(PACE_SECONDS)

    print("\n  `stored` climbs and never falls -- the session still keeps everything.")
    print("  The filter changes what is SENT, never what is STORED. That distinction")
    print("  is the one to hold on to: trimming is not deletion.")


async def main() -> None:
    part1()
    await part2()
    await asyncio.sleep(PACE_SECONDS)
    await part3()


if __name__ == "__main__":
    asyncio.run(main())
