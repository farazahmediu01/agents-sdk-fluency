"""
Compaction, end to end, on a conversation long enough to need it.

    uv run python 05_context_window/with_sdk/compaction_demo.py
    uv run python 05_context_window/with_sdk/compaction_demo.py --trim

    ~20 requests. Run it once and read the table; do not loop it.

THE EXPERIMENT
--------------
Turn 1 states two facts that live NOWHERE ELSE: a destination and a day. They
are not in the `Traveller` context, no tool returns them, and nothing later
repeats them. Then eight turns of packing push them out of any sane budget.

The last turn asks for them back.

    --trim   run the same conversation with section 3's tail window instead,
             which throws the head away. This is the control, and without it
             "compaction worked" is not a claim you have tested.

Chapter 4's PART 1 shipped a control that was contaminated by a shared context
object, and it was convincing. So: the fact under test is deliberately one that
only the transcript can carry.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, cast

from agents import RunConfig, Runner, SQLiteSession
from agents.run_config import CallModelData, ModelInputData

import _bootstrap_sdk5  # noqa: F401  -- must precede the packing_agent import
from compaction import Compactor
from context_filter import tokens, trim_to_budget
from packing_agent import Traveller, packing_agent

DB = Path(__file__).with_name("data") / "compaction_demo.db"
PACE_SECONDS = 8.0
BUDGET = 600

# Turn 1 carries the two facts under test. Nothing else in the run mentions them.
TURNS = [
    "I fly to Skardu on Friday. Start me off with two t-shirts, 0.2 kg each.",
    "Add a pair of jeans, 0.8 kg.",
    "Add a fleece, 0.5 kg.",
    "Add hiking boots, 1.5 kg.",
    "Add a down jacket, 1.1 kg.",
    "Add a sleeping bag, 1.8 kg.",
    "Add a water filter, 0.3 kg.",
    "How much room do I have left?",
    "Remind me: which city am I flying to, and on which day?",
]


class TailWindow:
    """The control: section 3's trimmer, wired to the same seam."""

    def __init__(self, budget: int) -> None:
        self.budget = budget
        self.summarisations = 0

    def __call__(self, data: CallModelData[Any]) -> ModelInputData:
        items = cast(list[dict[str, Any]], data.model_data.input)
        if tokens(items) <= self.budget:
            return data.model_data
        return ModelInputData(
            input=cast(Any, trim_to_budget(items, self.budget)),
            instructions=data.model_data.instructions,
        )


async def main() -> None:
    control = "--trim" in sys.argv
    strategy: Any = TailWindow(BUDGET) if control else Compactor(BUDGET)
    label = "TAIL WINDOW (control)" if control else "COMPACTION"

    print(f"\n  {label} at a {BUDGET}-token budget\n")
    DB.parent.mkdir(parents=True, exist_ok=True)
    session = SQLiteSession(f"compaction_{'trim' if control else 'summary'}", DB)
    await session.clear_session()

    config = RunConfig(call_model_input_filter=strategy)
    traveller = Traveller(name="Faraz", bag_limit_kg=20.0)

    print(f"  {'turn':>5}{'stored':>8}{'est tok':>9}{'summaries':>11}   answer")
    print("  " + "-" * 74)

    for number, prompt in enumerate(TURNS, start=1):
        result = await Runner.run(
            packing_agent, prompt, context=traveller, session=session, run_config=config
        )
        items = cast(list[dict[str, Any]], await session.get_items())
        answer = str(result.final_output).replace("\n", " ")
        print(
            f"  {number:>5}{len(items):>8}{tokens(items):>9}"
            f"{strategy.summarisations:>11}   {answer[:44]}"
        )
        await asyncio.sleep(PACE_SECONDS)

    print("\n  THE QUESTION THAT MATTERS is the last one. Skardu and Friday were")
    print("  said once, in turn 1, and nothing since repeated them.")
    if not control:
        print(f"\n  the summary the model was given:\n    {strategy.summary[:400]}")
        print("\n  Now run again with --trim and compare that last answer.")


if __name__ == "__main__":
    asyncio.run(main())
