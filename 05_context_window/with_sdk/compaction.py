"""
Compaction: summarise the head, keep the tail verbatim.

Section 3's trimmer works and throws away the wrong end. The oldest turn is
usually where the user said what they WANT; a tail window deletes precisely
that. Run `spike/orphan_400.py` and read case B's answer -- the trim succeeded
and the agent replied "you have packed a pair of hiking boots", because the
t-shirts, the jeans and the jacket were in the part that got cut.

Compaction is the standard answer: replace the head with a short description of
itself instead of deleting it. What that buys, and what it costs, is section 7.

TWO DESIGN DECISIONS WORTH ARGUING WITH
---------------------------------------
**The summary goes in `instructions`, not into the item list.** `ModelInputData`
has two fields and almost everyone only looks at `input`. Putting the summary
there would mean inventing a turn nobody took -- a `user` message the user never
sent, or an `assistant` message it never said. Both are lies to the model that
will be quoted back at you. `instructions` is the field that already means
"things that are true but were not said in the conversation".

**The summary is cached.** The filter fires once per MODEL CALL, not once per
turn (`filter_demo.py` PART 2 measured three firings in a single turn). A
summariser without a cache would make three extra model calls per turn, and the
bill for staying under budget would exceed the bill for going over it.
"""

from __future__ import annotations

from typing import Any

from agents import Agent, Runner
from agents.run_config import CallModelData, ModelInputData

from context_filter import Item, align_to_turn_start, drop_orphans, tokens
from shared.models import make_model

SUMMARISER = Agent(
    name="Conversation summariser",
    instructions=(
        "You compress the earlier part of a conversation so it can be dropped "
        "from the transcript without losing what matters.\n"
        "Write at most 120 words, as terse notes, in the third person.\n"
        "KEEP: what the user asked for, decisions made, values they supplied, "
        "constraints they stated, and anything a tool wrote down.\n"
        "DROP: pleasantries, the assistant's phrasing, and anything the tail of "
        "the conversation already makes obvious.\n"
        "Never invent a detail that is not in the text. If a fact is uncertain, "
        "leave it out rather than guessing."
    ),
    model=make_model(),
)


def render(items: list[Item]) -> str:
    """A plain-text view of items for the summariser to read."""
    lines: list[str] = []
    for item in items:
        kind = item.get("type")
        if kind == "function_call":
            lines.append(f"[tool call] {item.get('name')}({item.get('arguments')})")
        elif kind == "function_call_output":
            lines.append(f"[tool result] {item.get('output')}")
        elif item.get("role") == "user":
            lines.append(f"user: {item.get('content')}")
        elif item.get("role") == "assistant":
            content = item.get("content")
            if isinstance(content, str):
                lines.append(f"assistant: {content}")
            else:
                text = "".join(p.get("text", "") for p in content or [])
                lines.append(f"assistant: {text}")
    return "\n".join(lines)


class Compactor:
    """
    A `call_model_input_filter` that summarises the head once it must.

    Under budget it is a no-op and returns the SAME list object it was given --
    see `test_compaction.py`. A filter that rewrites healthy history is a bug,
    and on Gemini 3.x a rebuilt item loses the `thought_signature` the model
    requires back.
    """

    def __init__(self, budget: int, *, keep: float = 0.5) -> None:
        self.budget = budget
        self.keep = keep  # fraction of the budget left as verbatim tail after a fold
        self.summary: str = ""
        self.covered: int = 0  # how many leading items the summary describes
        self.summarisations: int = 0  # model calls spent on summarising

    def _split_at(self, items: list[Item]) -> int:
        """
        Index of the first item to keep verbatim after a fold.

        THE RESULT IS ALWAYS A USER-MESSAGE INDEX, and that is not cosmetic.

        The first version returned wherever the token count happened to run out.
        A golden-dataset run then died on turn 2 of case C1:

            400 INVALID_ARGUMENT
            "* GenerateContentRequest.contents: contents is not specified"

        The split had landed past the last user message, so the verbatim tail
        contained only assistant and tool items, `align_to_turn_start` found no
        user message to open on, and the filter handed the SDK an empty list.

        Snapping the split BACK to a turn boundary fixes three things at once:
        the tail can never be empty, it always opens legally, and a summary
        never describes half an exchange -- which was Challenge 2 in this
        chapter's `PROJECT.md` before it turned out to be load-bearing.

        > A boundary you have to repair afterwards is a boundary you should have
        > chosen in the first place.
        """
        tail_budget = int(self.budget * self.keep)
        raw = 0
        for kept, index in enumerate(range(len(items) - 1, -1, -1)):
            if kept and tokens(items[index:]) > tail_budget:
                raw = index + 1
                break

        # Snap backwards to the nearest user message: never cut inside a turn.
        for index in range(min(raw, len(items) - 1), -1, -1):
            if items[index].get("role") == "user":
                return index
        return 0

    async def _fold(self, new_items: list[Item]) -> None:
        """Extend the summary to cover `new_items` as well."""
        previous = f"NOTES SO FAR:\n{self.summary}\n\nNEW MATERIAL:\n" if self.summary else ""
        result = await Runner.run(SUMMARISER, previous + render(new_items))
        self.summary = str(result.final_output).strip()
        self.summarisations += 1

    async def __call__(self, data: CallModelData[Any]) -> ModelInputData:
        items: list[Item] = data.model_data.input  # type: ignore[assignment]
        base = data.model_data.instructions

        if self.covered == 0 and tokens(items) <= self.budget:
            # Untouched. Note the SAME list object goes back out.
            return data.model_data

        # THE HYSTERESIS, AND THE BUG IT FIXES.
        #
        # The first version recomputed the split on every call and folded
        # whenever it had moved. It had moved on nearly every call, so a
        # nine-turn conversation spent THIRTEEN model calls on summarising --
        # more than the conversation itself. Staying under budget cost more than
        # going over it would have.
        #
        # The cause is section 5's measurement: the filter fires per MODEL CALL,
        # and a fold leaves the tail at `budget * keep`, which the next call
        # immediately exceeds. Any threshold equal to the one you reset to will
        # trigger every time.
        #
        # So the trigger and the target are deliberately different numbers: fold
        # only when the verbatim tail passes the FULL budget, and when folding,
        # cut back to HALF of it. That gap is the hysteresis, and it is the
        # difference between compaction as an optimisation and compaction as an
        # expense.
        if tokens(items[self.covered :]) > self.budget:
            split = self._split_at(items)
            if split > self.covered:
                await self._fold(items[self.covered : split])
                self.covered = split

        tail = align_to_turn_start(drop_orphans(items[self.covered :]))
        instructions = (
            f"{base}\n\nEARLIER IN THIS CONVERSATION (compacted notes, not spoken "
            f"text -- do not quote it back):\n{self.summary}"
            if self.summary
            else base
        )
        return ModelInputData(input=tail, instructions=instructions)  # type: ignore[arg-type]
