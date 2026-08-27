"""
Inheritance - five experiments, ending in the one class shape the SDK asks you
to write by hand.

    uv run python 00_python_for_agents/examples/class_inheritance_lab.py        # all five
    uv run python 00_python_for_agents/examples/class_inheritance_lab.py 4      # just experiment 4

No API key. No SDK import. Experiment 4 rebuilds `RunHooks` from scratch in about
thirty lines, because the point is to see that there is nothing in it you could
not have written -- and then to recognise it when the real one arrives in Phase 1.

WHY THIS FILE EXISTS
--------------------
Chapters 0-5 of this curriculum contain fourteen classes and **not one `super()`
call.** That is not an accident: dataclasses, Pydantic models, Protocols and
TypedDicts are all classes you *fill in*, never classes you *extend*. They carried
you to Chapter 5 without ever needing inheritance.

Phase 1 ends that. `RunHooks` is subclass-and-override, `SQLModel` is subclass-
and-declare, and a custom eval metric in Phase 3 is subclass-and-implement. Three
different libraries, one Python feature, and you have not used it yet.

THE MENTAL MODEL: A JOB DESCRIPTION AND THE PEOPLE DOING THE JOB
---------------------------------------------------------------
A base class is a job description. It lists what the role responds to, and it
supplies a default for each one -- often the default "do nothing".

    class RunHooks:              the job description
        async def on_tool_start(...): pass

A subclass is somebody hired into that role. They answer to the same list, they
do most of it the standard way, and they do the parts they care about their own
way.

    class CostHooks(RunHooks):   an employee who only cares about the invoice
        async def on_tool_start(...): self.calls += 1

And `super()` is "...and also do whatever the job description said." Whether you
need that line depends entirely on whether the description said anything.
"""

from __future__ import annotations

import asyncio
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# -----------------------------------------------------------------------------
# Stand-ins for the objects the real hooks receive. Deliberately tiny: this file
# is about the class relationships, not about the SDK.
# -----------------------------------------------------------------------------


@dataclass
class Agent:
    """What the SDK will hand your hook as `agent`."""

    name: str


@dataclass
class Tool:
    """What the SDK will hand your hook as `tool`."""

    name: str
    cost_cents: float = 0.0


# -----------------------------------------------------------------------------
# 1. Inheritance is deduplication, and nothing grander.
#
# THE MISCONCEPTION: "inheritance is for modelling real-world is-a relationships."
# -----------------------------------------------------------------------------
#
# It is occasionally that. Day to day it is this: two classes that were 90% the
# same, with the 90% written once.


class Notifier:
    """The shared 90%: everything a notifier does that is not the sending."""

    def __init__(self, recipient: str) -> None:
        self.recipient = recipient
        self.sent: list[str] = []

    def format(self, body: str) -> str:
        """Shared. Neither subclass overrides this, and that is the point."""
        return f"To {self.recipient}: {body}"

    def send(self, body: str) -> str:
        message = self.format(body)
        self.sent.append(message)
        return f"[base] {message}"


class SlackNotifier(Notifier):
    """The 10% that differs."""

    def send(self, body: str) -> str:
        message = self.format(body)  # inherited, not rewritten
        self.sent.append(message)
        return f"[slack] {message}  :rocket:"


class SmsNotifier(Notifier):
    def send(self, body: str) -> str:
        message = self.format(body)[:32]  # SMS is short
        self.sent.append(message)
        return f"[sms] {message}"


def experiment_1() -> None:
    print("1. What a subclass actually gets for free\n")

    for notifier in (
        Notifier("faraz"),
        SlackNotifier("faraz"),
        SmsNotifier("faraz"),
    ):
        print(f"   {type(notifier).__name__:<15} {notifier.send('your rent is due')}")

    slack = SlackNotifier("faraz")
    print()
    print(f"   slack.format is Notifier's?  {SlackNotifier.format is Notifier.format}")
    print(f"   isinstance(slack, Notifier)  {isinstance(slack, Notifier)}")
    print(f"   slack.sent exists            {slack.sent == []}")
    print()
    print("   `SlackNotifier` defines ONE method. It has `format`, `__init__`,")
    print("   `recipient` and `sent` anyway, because Python looks a name up on the")
    print("   class first and then walks up to the parent when it does not find it.")
    print()
    print("   That walk is the whole feature. Everything else is consequences.")


# -----------------------------------------------------------------------------
# 2. Overriding, and what `super()` is for.
#
# THE MISCONCEPTION: "I overrode the method, so my version runs" -- true, and
# usually not the question you needed answered.
# -----------------------------------------------------------------------------


class AuditedNotifier(Notifier):
    """
    Adds an audit line to every send.

    Two ways to write it. One of them silently drops the parent's bookkeeping.
    """

    def __init__(self, recipient: str) -> None:
        super().__init__(recipient)
        self.audit: list[str] = []

    def send(self, body: str) -> str:
        self.audit.append(f"AUDIT send -> {self.recipient}")
        return super().send(body)  # <- and also do what the parent did


class ForgetfulAuditedNotifier(Notifier):
    """The same class with `super().send(...)` replaced by a reimplementation."""

    def __init__(self, recipient: str) -> None:
        super().__init__(recipient)
        self.audit: list[str] = []

    def send(self, body: str) -> str:
        self.audit.append(f"AUDIT send -> {self.recipient}")
        # Looks equivalent. It is not: `self.sent.append(...)` is missing, and
        # nothing anywhere will tell you.
        return f"[base] {self.format(body)}"


def experiment_2() -> None:
    print("2. Overriding with and without super()\n")

    good = AuditedNotifier("faraz")
    bad = ForgetfulAuditedNotifier("faraz")

    for notifier in (good, bad):
        notifier.send("your rent is due")
        notifier.send("electricity bill posted")

    print(f"   AuditedNotifier          audit={len(good.audit)}  sent={len(good.sent)}")
    print(f"   ForgetfulAuditedNotifier audit={len(bad.audit)}  sent={len(bad.sent)}   <- lost")
    print()
    print("   Both classes 'work'. Both return the right string. One of them has")
    print("   quietly stopped recording what it sent, because the author reproduced")
    print("   the parent's behaviour by hand instead of calling it.")
    print()
    print("   `super().send(body)` means: run the parent's version of this method,")
    print("   then carry on. It is not a keyword you sprinkle for safety -- it is a")
    print("   decision. Ask one question every single time you override:")
    print()
    print("       does the parent's version do work I still need?")
    print()
    print("   Yes -> call super(). No -> deliberately do not, and say so in a")
    print("   comment, because the next reader will wonder.")


# -----------------------------------------------------------------------------
# 3. `__init__` is the override people forget.
#
# THE MISCONCEPTION: "the parent sets that up, so it will be there."
# -----------------------------------------------------------------------------


class BrokenAuditedNotifier(Notifier):
    """Adds state, and never lets the parent add its own."""

    def __init__(self, recipient: str) -> None:
        # super().__init__(recipient)   <- the missing line
        self.audit: list[str] = []


def experiment_3() -> None:
    print("3. The AttributeError you will actually hit\n")

    broken = BrokenAuditedNotifier("faraz")
    print(f"   constructed fine: {broken}")
    print("   ...no error yet. The object exists. It is simply half-built.\n")

    try:
        broken.send("your rent is due")
    except AttributeError as exc:
        print(f"   AttributeError: {exc}")

    print()
    print("   `__init__` is a method like any other, so defining one in the subclass")
    print("   OVERRIDES the parent's -- and the parent's was where `self.recipient`")
    print("   and `self.sent` came from. They were never assigned.")
    print()
    print("   Note where it failed: not at construction, at first use. The object")
    print("   was happily created and passed around before anything complained.")
    print()
    print("   THE RULE: if your subclass defines `__init__`, its first line is")
    print("   `super().__init__(...)` unless you can say out loud why not.")


# -----------------------------------------------------------------------------
# 4. The template-method base class - this IS RunHooks.
#
# THE MISCONCEPTION: "hooks are framework magic."
# -----------------------------------------------------------------------------


class RunHooks:
    """
    A hand-rolled copy of the SDK's class, minus the generics.

    Read the real one when you get there -- `agents/lifecycle.py`, class
    `RunHooksBase`, docstring "Subclass and override the methods you need." It
    has more methods than this (`on_llm_start`, `on_llm_end`, `on_handoff`) and
    they are typed against `RunContextWrapper[TContext]`, but the shape is
    exactly what is below: **every method is a no-op you are invited to replace.**
    """

    async def on_agent_start(self, agent: Agent) -> None:
        """Called when an agent begins. Does nothing on purpose."""

    async def on_tool_start(self, agent: Agent, tool: Tool) -> None:
        """Called before a tool runs. Does nothing on purpose."""

    async def on_tool_end(self, agent: Agent, tool: Tool, result: str) -> None:
        """Called after a tool returns. Does nothing on purpose."""

    async def on_agent_end(self, agent: Agent, output: str) -> None:
        """Called when an agent finishes. Does nothing on purpose."""


async def fake_runner(agent: Agent, tools: list[Tool], hooks: RunHooks) -> str:
    """
    A 12-line stand-in for `Runner.run`, to show WHO calls your methods.

    You never call a hook yourself. You hand the object to the runner and the
    runner calls you back -- which is why the parameter list is not yours to
    choose.
    """
    await hooks.on_agent_start(agent)
    for tool in tools:
        await hooks.on_tool_start(agent, tool)
        await asyncio.sleep(0.05)
        result = f"{tool.name} ok"
        await hooks.on_tool_end(agent, tool, result)
    output = "done"
    await hooks.on_agent_end(agent, output)
    return output


class PrintHooks(RunHooks):
    """Overrides two of the four. The other two keep doing nothing."""

    async def on_agent_start(self, agent: Agent) -> None:
        print(f"      [start] {agent.name}")

    async def on_tool_start(self, agent: Agent, tool: Tool) -> None:
        print(f"      [tool ] {tool.name}")


@dataclass
class Budget:
    """Somewhere for the cost hook to put its numbers."""

    cents: float = 0.0
    tool_names: list[str] = field(default_factory=list)


class CostHooks(RunHooks):
    """
    Overrides ONE method, and carries state.

    Note the `__init__` with no `super().__init__()` -- and note that this is
    fine here, because `RunHooks` does not define `__init__` at all, so there is
    nothing of the parent's to lose. That is a fact you have to CHECK, not
    assume. Experiment 3 is what assuming costs.
    """

    def __init__(self, budget: Budget) -> None:
        self.budget = budget

    async def on_tool_end(self, agent: Agent, tool: Tool, result: str) -> None:
        self.budget.cents += tool.cost_cents
        self.budget.tool_names.append(tool.name)


class VerboseCostHooks(CostHooks):
    """
    Now subclass YOUR OWN hooks, and the super() question comes back with teeth.

    `CostHooks.on_tool_end` is not a no-op. Override it without calling super()
    and the budget silently stops counting.
    """

    async def on_tool_end(self, agent: Agent, tool: Tool, result: str) -> None:
        await super().on_tool_end(agent, tool, result)  # keep the counting
        print(f"      [cost ] {tool.name} +{tool.cost_cents:.1f}c")


async def experiment_4() -> None:
    print("4. Rebuilding RunHooks, then using it three ways\n")

    agent = Agent(name="SpendlyExpenseAgent")
    tools = [Tool("extract_expense", 0.8), Tool("save_expense", 0.2)]

    print("   (a) the base class itself - four no-ops, so nothing is observed:\n")
    await fake_runner(agent, tools, RunHooks())
    print("      (silence, and the run still worked)\n")

    print("   (b) PrintHooks - two methods overridden:\n")
    await fake_runner(agent, tools, PrintHooks())

    print("\n   (c) VerboseCostHooks - subclass of a subclass, with super():\n")
    budget = Budget()
    await fake_runner(agent, tools, VerboseCostHooks(budget))
    print(f"\n      budget: {budget.cents:.1f}c across {budget.tool_names}")

    print()
    print("   Three objects, one call signature, and `fake_runner` did not change")
    print("   between them. It calls `hooks.on_tool_end(...)` and whichever class")
    print("   you handed it decides what that means.")
    print()
    print("   THE TRAP, and it is the reason this experiment exists: the SDK's own")
    print("   base methods are no-ops, so forgetting `super()` when you subclass")
    print("   `RunHooks` costs you nothing. Then you subclass your OWN hooks --")
    print("   which is what happens the moment you want dev logging on top of")
    print("   production metrics -- and the same forgotten line costs you the")
    print("   metrics. Same code, different parent, different consequence.")
    print()
    print("   Where you will meet this:")
    print()
    print("       class ObservabilityHooks(RunHooks):     # Phase 1, L7")
    print("       class Expense(SQLModel, table=True):    # Phase 2, SQLModel")
    print("       class ToolError(Exception):             # you already wrote this")


# -----------------------------------------------------------------------------
# 5. ABC - the base class that refuses to be used directly.
# -----------------------------------------------------------------------------


class Grader(ABC):
    """
    `RunHooks` says "override what you like". This says "you MUST override this".

    The difference is whether a default is meaningful. A no-op hook is a fine
    default. A no-op grader is a scoring system that silently passes everything.
    """

    name: str = "unnamed"

    @abstractmethod
    def score(self, answer: str, expected: str) -> float:
        """Return 0.0-1.0. There is no sensible default, so there is none."""

    def report(self, answer: str, expected: str) -> str:
        """Shared, concrete, and written once - the reason ABC beats a Protocol here."""
        return f"{self.name:<12} {self.score(answer, expected):.2f}"


class ExactMatch(Grader):
    name = "exact"

    def score(self, answer: str, expected: str) -> float:
        return 1.0 if answer.strip() == expected.strip() else 0.0


class Contains(Grader):
    name = "contains"

    def score(self, answer: str, expected: str) -> float:
        return 1.0 if expected.lower() in answer.lower() else 0.0


def experiment_5() -> None:
    print("5. When the base class should refuse to be instantiated\n")

    try:
        # The `ignore` is the lesson, not a workaround: pyright reports
        # `reportAbstractUsage` on this line WITHOUT running it, so an ABC is
        # caught by the type checker AND at construction. We silence it here only
        # because we want the runtime error to be visible below.
        Grader()  # pyright: ignore[reportAbstractUsage]
    except TypeError as exc:
        print(f"   TypeError: {exc}\n")

    answer, expected = "Your rent is 40000 PKR", "40000"
    for grader in (ExactMatch(), Contains()):
        print(f"   {grader.report(answer, expected)}")

    print()
    print("   `@abstractmethod` turns a forgotten override into an error at")
    print("   construction, which is the earliest anyone could have told you.")
    print()
    print("   Choosing between the three tools you now have:")
    print()
    print("     Protocol   - you do not own the classes; you just need the shape")
    print("                  (you already use this: `RunLike` in Chapter 1)")
    print("     plain base - shared behaviour, sensible defaults, override at will")
    print("                  (RunHooks)")
    print("     ABC        - shared behaviour PLUS holes the subclass must fill")
    print("                  (a DeepEval custom metric, Phase 3)")
    print()
    print("   And the one rule worth carrying: inherit from ONE class. Python")
    print("   allows more, resolves conflicts by a documented ordering called the")
    print("   MRO, and the moment you need to know what the MRO is, the design has")
    print("   already gone wrong. `SQLModel, table=True` is a keyword argument, not")
    print("   a second parent -- you will not need multiple inheritance in Phase 2.")


# -----------------------------------------------------------------------------


async def main() -> None:
    experiments = {
        1: experiment_1,
        2: experiment_2,
        3: experiment_3,
        4: experiment_4,
        5: experiment_5,
    }

    wanted = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(experiments)

    for number in wanted:
        run = experiments.get(number)
        if run is None:
            continue
        print("=" * 72)
        outcome = run()
        if asyncio.iscoroutine(outcome):
            await outcome
        print()


if __name__ == "__main__":
    asyncio.run(main())
