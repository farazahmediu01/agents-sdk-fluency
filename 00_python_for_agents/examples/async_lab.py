"""
The async lab - ten experiments, each one killing a specific misconception.

    uv run python 00_python_for_agents/examples/async_lab.py          # all ten
    uv run python 00_python_for_agents/examples/async_lab.py 3        # just experiment 3

Experiments 1-6 are the concepts. Experiments 7-10 are the four things production
async needs that the concepts alone do not give you: releasing a resource that
must be released, receiving values as they arrive, refusing to start more work
than the far end will accept, and deciding what happens to the siblings when one
job fails. Every one of them shows up in the SDK before Chapter 3.

No API key. No network. Everything here is simulated with sleeps, which is not a
cheat -- `asyncio.sleep` is a genuinely accurate stand-in for "waiting on
something outside this program", and that is all a network call ever is.

HOW TO USE THIS FILE
--------------------
Run each experiment. **Predict the timing before you look.** Every experiment
prints how long it took, and the timings are the whole lesson -- async is one of
the few topics where the concept is directly measurable in seconds.

THE MENTAL MODEL: ONE PERSON, SEVERAL MACHINES
----------------------------------------------
You are doing laundry. You have one pair of hands.

    You load the washing machine and press start.   <- this takes you 5 seconds
    The machine now runs for 30 minutes.            <- this takes you NOTHING

The question that decides everything: **what do you do during those 30 minutes?**

    Synchronous you  : sits in front of the machine and watches it.
    Asynchronous you : goes and loads the dishwasher, then answers an email.

Both versions of you have exactly one pair of hands. You never do two things at
literally the same instant. The async version is not faster at any single task
-- it is faster overall because it stopped treating *waiting* as *working*.

Map it to the code and every keyword lands:

    async def wash():   this job has waiting in it
    await machine       "the machine is running now; I am free -- someone else go"
    asyncio.run(...)    the person. Somebody has to actually do the walking around
    asyncio.gather(...) start the washer AND the dishwasher before waiting on either

And the one that catches everyone:

    folding clothes     no waiting involved, only hands. Nothing to hand off.
                        This is CPU work, and async does nothing for it.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

# -----------------------------------------------------------------------------
# A stand-in for "something outside this program that takes time".
# -----------------------------------------------------------------------------


async def check_domain(name: str) -> str:
    """Pretend to ask a DNS server whether a domain is free. Takes ~0.4s."""
    await asyncio.sleep(0.4)
    return f"{name}.com is available"


async def check_username(name: str) -> str:
    """Pretend to ask a social API whether a handle is free. Takes ~0.6s."""
    await asyncio.sleep(0.6)
    return f"@{name} is taken"


async def check_trademark(name: str) -> str:
    """Pretend to search a trademark registry. Takes ~0.5s."""
    await asyncio.sleep(0.5)
    return f"no trademark conflict for {name}"


# -----------------------------------------------------------------------------
# 1. Calling an async function does not run it.
#
# THE MISCONCEPTION: "I called it, so it ran."
# -----------------------------------------------------------------------------


def experiment_1() -> None:
    print("1. What does calling an async function actually give you?\n")

    result = check_domain("spendly")  # note: no await
    print(f"   check_domain('spendly')  ->  {result!r}")
    print(f"   type                     ->  {type(result).__name__}")

    # Without this, Python warns 'coroutine was never awaited' - a real warning
    # you will see for real, and now you know what it means.
    result.close()

    print()
    print("   You did not get a string. You got a COROUTINE OBJECT: a job that has")
    print("   been described and not started. Think of it as a written note saying")
    print("   'wash the towels' -- writing the note is not doing the laundry.")
    print()
    print("   `await` is what hands the note to someone who will actually do it.")


# -----------------------------------------------------------------------------
# 2. `await` in a row is still a queue.
#
# THE MISCONCEPTION - and this is the big one - "I made it async, so it's fast."
# -----------------------------------------------------------------------------


async def experiment_2() -> None:
    print("2. Three awaits, one after another\n")

    start = time.perf_counter()
    a = await check_domain("spendly")
    b = await check_username("spendly")
    c = await check_trademark("spendly")
    elapsed = time.perf_counter() - start

    for line in (a, b, c):
        print(f"   {line}")
    print(f"\n   elapsed: {elapsed:.2f}s   (0.4 + 0.6 + 0.5 = 1.5)")
    print()
    print("   Every function here is `async`. Every call is `await`ed. And it took")
    print("   exactly as long as doing them one at a time, because that is what we")
    print("   asked for: `await` means 'I need this answer before my next line'.")
    print()
    print("   **This is the single most common async mistake.** Marking things")
    print("   `async` buys you nothing on its own. You have loaded the washing")
    print("   machine and then stood there watching it, three times.")


# -----------------------------------------------------------------------------
# 3. gather() is where the win actually is.
# -----------------------------------------------------------------------------


async def experiment_3() -> None:
    print("3. The same three, started together\n")

    start = time.perf_counter()
    a, b, c = await asyncio.gather(
        check_domain("spendly"),
        check_username("spendly"),
        check_trademark("spendly"),
    )
    elapsed = time.perf_counter() - start

    for line in (a, b, c):
        print(f"   {line}")
    print(f"\n   elapsed: {elapsed:.2f}s   (the SLOWEST one, 0.6 - not the sum)")
    print()
    print("   Total time is now the longest single wait instead of the sum of all")
    print("   of them. You started all three machines, then waited once.")
    print()
    print("   Notice the results came back in the order you ASKED for them, not the")
    print("   order they finished in. gather() preserves your ordering, which is why")
    print("   unpacking `a, b, c` is safe.")


# -----------------------------------------------------------------------------
# 4. One blocking call freezes everything.
#
# This is the experiment that makes the event loop visible.
# -----------------------------------------------------------------------------


async def polite_waiter(label: str, seconds: float) -> str:
    """Waits the async way: hands control back while it waits."""
    await asyncio.sleep(seconds)
    return f"{label} done"


async def rude_waiter(label: str, seconds: float) -> str:
    """
    Waits the WRONG way inside async code.

    `time.sleep` does not hand control back. It sits on the one pair of hands and
    refuses to let go, so nothing else in the entire program can make progress.
    """
    time.sleep(seconds)
    return f"{label} done"


async def experiment_4() -> None:
    print("4. asyncio.sleep vs time.sleep, inside async code\n")

    start = time.perf_counter()
    await asyncio.gather(
        polite_waiter("polite-1", 0.5),
        polite_waiter("polite-2", 0.5),
        polite_waiter("polite-3", 0.5),
    )
    polite = time.perf_counter() - start

    start = time.perf_counter()
    await asyncio.gather(
        rude_waiter("rude-1", 0.5),
        rude_waiter("rude-2", 0.5),
        rude_waiter("rude-3", 0.5),
    )
    rude = time.perf_counter() - start

    print(f"   three polite_waiter (asyncio.sleep) : {polite:.2f}s")
    print(f"   three rude_waiter   (time.sleep)    : {rude:.2f}s")
    print()
    print("   Identical code. Identical gather(). Identical durations. One is 3x")
    print("   slower, and nothing about the shape of the program says why.")
    print()
    print("   `asyncio.sleep` says 'I'm waiting -- somebody else go'.")
    print("   `time.sleep`    says nothing and holds the hands.")
    print()
    print("   THE RULE: inside `async def`, every waiting call must be an async one.")
    print("   One ordinary blocking call anywhere -- `requests.get`, `time.sleep`, a")
    print("   heavy file read -- silently converts your concurrent program back into")
    print("   a sequential one. Nothing crashes. It just gets slow, and the reason")
    print("   is invisible unless you know to look for it.")


# -----------------------------------------------------------------------------
# 5. Async is not threads, and does not help CPU work.
# -----------------------------------------------------------------------------


async def count_to(n: int) -> int:
    """Pure CPU work. There is no waiting here to hand off."""
    total = 0
    for i in range(n):
        total += i * i
    return total


async def experiment_5() -> None:
    print("5. What async does NOT do\n")

    size = 3_000_000

    start = time.perf_counter()
    await count_to(size)
    await count_to(size)
    one_at_a_time = time.perf_counter() - start

    start = time.perf_counter()
    await asyncio.gather(count_to(size), count_to(size))
    gathered = time.perf_counter() - start

    print(f"   two counts, awaited in sequence : {one_at_a_time:.2f}s")
    print(f"   two counts, gathered            : {gathered:.2f}s")
    print()
    print("   Barely any difference -- and gather() may even be slightly slower.")
    print()
    print("   This is folding clothes. There is no machine running in the")
    print("   background; the work needs your hands the entire time. gather() can")
    print("   only interleave at `await` points, and pure computation has none.")
    print()
    print("   async is for WAITING, not for computing. If you need real parallel")
    print("   CPU work you want processes (`multiprocessing`), which is a different")
    print("   tool for a different problem.")


# -----------------------------------------------------------------------------
# 6. Why async 'spreads'.
# -----------------------------------------------------------------------------


def a_normal_function() -> str:
    """
    An ordinary function cannot `await`. Uncomment the line to see it fail.

    That is not a rule Python invented to annoy you: `await` means "pause me and
    let the loop run someone else", and an ordinary function has no way to be
    paused and resumed.
    """
    # return await check_domain("spendly")   # SyntaxError: 'await' outside async function
    return "ordinary functions cannot await"


async def experiment_6() -> None:
    print("6. Why async spreads through a codebase\n")

    print(f"   {a_normal_function()}")
    print()
    print("   To `await` something you must be inside `async def`. So the moment one")
    print("   function deep in your stack becomes async, every caller must become")
    print("   async too, all the way up -- until someone calls `asyncio.run()`.")
    print()
    print("   People call this 'function colouring', and it is the real cost of")
    print("   async. It is worth knowing BEFORE you meet it, because the fix is")
    print("   architectural, not local.")
    print()
    print("   Where you will meet this in Chapter 1:")
    print()
    print("       result = await Runner.run(agent, message)      # the SDK is async")
    print("       result = Runner.run_sync(agent, message)       # the escape hatch")
    print()
    print("   `run_sync` starts a loop, runs the coroutine, and hands you the result")
    print("   -- so ordinary code can call it. Use it while you are learning. Reach")
    print("   for the async version when you want two agents running at once.")


# -----------------------------------------------------------------------------
# 7. `async with` - the cleanup that survives an exception.
#
# THE MISCONCEPTION: "I close it on the last line, so it gets closed."
# -----------------------------------------------------------------------------
#
# Back to the laundry: the machine door has to be closed and the machine handed
# back to the next person, and that is true whether the load washed cleanly or
# the drum jammed halfway. Where you put the "hand it back" line decides whether
# it happens on the bad day.

OPEN_CONNECTIONS = 0


class PooledConnection:
    """
    A stand-in for a database connection - something you must give BACK.

    `async with` needs exactly two methods, `__aenter__` and `__aexit__`. There
    is no base class to inherit and no library involved: the two methods ARE the
    protocol, the same way `__len__` is all `len()` ever wanted.
    """

    def __init__(self, label: str) -> None:
        self.label = label

    async def __aenter__(self) -> PooledConnection:
        global OPEN_CONNECTIONS
        await asyncio.sleep(0.05)  # handshakes take time - hence ASYNC with
        OPEN_CONNECTIONS += 1
        print(f"   [open  {self.label}]   pool holds {OPEN_CONNECTIONS}")
        return self  # <- this is what `as conn` binds to

    async def __aexit__(self, *exc_info: object) -> None:
        # Called on the way out. ALWAYS -- normal exit, `return`, or exception.
        global OPEN_CONNECTIONS
        await asyncio.sleep(0.05)
        OPEN_CONNECTIONS -= 1
        print(f"   [close {self.label}]   pool holds {OPEN_CONNECTIONS}")

    async def query(self, sql: str) -> str:
        await asyncio.sleep(0.1)
        if "boom" in sql:
            raise ValueError("syntax error near 'boom'")
        return f"{sql!r} -> 1 row"


@asynccontextmanager
async def borrowed(label: str) -> AsyncIterator[PooledConnection]:
    """
    The same thing, written as a function instead of a class.

    Everything before `yield` is `__aenter__`. Everything after is `__aexit__`.
    The `try/finally` is what makes the teardown survive an exception in the
    body -- without it this decorator gives you nothing the manual version did
    not already fail to give you.
    """
    conn = PooledConnection(label)
    await conn.__aenter__()
    try:
        yield conn
    finally:
        await conn.__aexit__()


async def experiment_7() -> None:
    print("7. `async with` and the connection you forgot to give back\n")

    print("   (a) closing it on the last line, the way it looks fine:\n")
    conn = PooledConnection("manual")
    await conn.__aenter__()
    try:
        print(f"   {await conn.query('select boom')}")
        await conn.__aexit__()  # never reached - query() raised above it
    except ValueError as exc:
        print(f"   ValueError: {exc}")
    leaked = OPEN_CONNECTIONS
    print(f"\n   pool holds {leaked} after the block ended   <- leaked one\n")

    print("   (b) the same failing query, inside `async with`:\n")
    before = OPEN_CONNECTIONS
    try:
        async with PooledConnection("guarded") as guarded:
            print(f"   {await guarded.query('select boom')}")
    except ValueError as exc:
        print(f"   ValueError: {exc}")
    print(f"\n   pool holds {OPEN_CONNECTIONS}, same as the {before} it started with")
    print("   -- this block leaked nothing. The 1 still sitting there is (a)'s,")
    print("   and it is not coming back on its own.\n")

    print("   (c) `@asynccontextmanager` - the same guarantee, as a function:\n")
    async with borrowed("factory") as conn2:
        print(f"   {await conn2.query('select 1')}")

    print()
    print("   The leak in (a) is not a typo -- it is the shape. Any `return`, any")
    print("   `raise`, any early exit between open and close skips the close, and")
    print("   the failure is invisible until the pool runs dry in production.")
    print()
    print("   Where you will meet this:")
    print()
    print("       async with AsyncSession(engine) as session:    # Phase 2, SQLModel")
    print("       async with MCPServerStdio(params) as server:   # Phase 1, L8")
    print("       @asynccontextmanager")
    print("       async def lifespan(app): ...                   # Phase 2, FastAPI")
    print()
    print("   All three are this. A resource with a far end that has to be told.")


# -----------------------------------------------------------------------------
# 8. `async for` - values as they arrive, not all at the end.
#
# THE MISCONCEPTION: "await gets me the answer, so await is all I need."
# -----------------------------------------------------------------------------


async def answer_at_once(prompt: str) -> str:
    """The ordinary shape: one value, handed over when everything is done."""
    tokens = prompt.split()
    for _ in tokens:
        await asyncio.sleep(0.12)
    return " ".join(tokens)


async def answer_streaming(prompt: str) -> AsyncIterator[str]:
    """
    An ASYNC GENERATOR: `yield` inside `async def`.

    It is not a coroutine and you cannot `await` it -- awaiting gives you the
    generator object, not its values. It is consumed with `async for`, which
    resumes the function each time round the loop.
    """
    for token in prompt.split():
        await asyncio.sleep(0.12)
        yield token


async def experiment_8() -> None:
    print("8. Waiting for the whole answer vs watching it arrive\n")

    prompt = "your rent is due on the fifth"

    start = time.perf_counter()
    whole = await answer_at_once(prompt)
    at_once_total = time.perf_counter() - start
    print(f"   awaited     : nothing... then {whole!r}")
    print(f"   first output after {at_once_total:.2f}s, total {at_once_total:.2f}s\n")

    start = time.perf_counter()
    first_at = 0.0
    print("   streamed    : ", end="", flush=True)
    async for token in answer_streaming(prompt):
        if first_at == 0.0:
            first_at = time.perf_counter() - start
        print(f"{token} ", end="", flush=True)
    streamed_total = time.perf_counter() - start
    print(f"\n   first output after {first_at:.2f}s, total {streamed_total:.2f}s")

    print()
    print("   Same work. Same total. The difference is entirely in WHEN the first")
    print("   thing reaches whoever is waiting, and for a person watching a screen")
    print("   that is most of what 'fast' means.")
    print()
    print("   Note what you cannot do: `await answer_streaming(...)` does not give")
    print("   you the tokens. An async generator is consumed by `async for` or it")
    print("   is not consumed at all.")
    print()
    print("   Where you will meet this:")
    print()
    print("       async for event in result.stream_events():     # Phase 1, L7")
    print("       async def chunks(): yield ...                  # Phase 2, SSE")
    print()
    print("   And in Phase 2 again, for a reason that has nothing to do with speed:")
    print("   chunking a document for embeddings is a generator, because you do not")
    print("   want the whole corpus in memory to produce the first chunk.")


# -----------------------------------------------------------------------------
# 9. Semaphore and wait_for - starting less work on purpose.
#
# THE MISCONCEPTION: "gather() is the fast one, so gather() everything."
# -----------------------------------------------------------------------------


class RateLimitError(RuntimeError):
    """What the far end says when you started more than it agreed to."""


IN_FLIGHT = 0
CONCURRENCY_CEILING = 3


async def metered_call(n: int) -> str:
    """A stand-in for an LLM endpoint that allows 3 concurrent requests."""
    global IN_FLIGHT
    IN_FLIGHT += 1
    try:
        if IN_FLIGHT > CONCURRENCY_CEILING:
            raise RateLimitError(f"429 rate_limit_exceeded (call {n})")
        await asyncio.sleep(0.3)
        return f"call {n} ok"
    finally:
        IN_FLIGHT -= 1


async def guarded_call(n: int, gate: asyncio.Semaphore) -> str:
    """The same call, but it waits for a slot before it starts."""
    async with gate:  # <- experiment 7's `async with`, doing real work
        return await metered_call(n)


async def never_answers() -> str:
    """The far end accepted the connection and then went quiet. It happens."""
    await asyncio.sleep(30)
    return "eventually"


async def experiment_9() -> None:
    print("9. Bounded concurrency, and the call that never comes back\n")

    print("   (a) nine calls, all started at once:\n")
    start = time.perf_counter()
    results = await asyncio.gather(*(metered_call(n) for n in range(1, 10)), return_exceptions=True)
    unbounded = time.perf_counter() - start
    failed = [r for r in results if isinstance(r, BaseException)]
    print(f"   {len(results) - len(failed)} succeeded, {len(failed)} rejected in {unbounded:.2f}s")
    print(f"   first rejection: {failed[0]}")

    print("\n   (b) the same nine, through a Semaphore(3):\n")
    gate = asyncio.Semaphore(CONCURRENCY_CEILING)
    start = time.perf_counter()
    ok = await asyncio.gather(*(guarded_call(n, gate) for n in range(1, 10)))
    bounded = time.perf_counter() - start
    print(f"   {len(ok)} succeeded, 0 rejected in {bounded:.2f}s")

    print("\n   (c) a call that hangs, with a deadline on it:\n")
    start = time.perf_counter()
    try:
        await asyncio.wait_for(never_answers(), timeout=0.5)
    except TimeoutError:
        print(
            f"   TimeoutError after {time.perf_counter() - start:.2f}s (the 30s call was cancelled)"
        )

    print()
    print("   (a) is what unbounded gather() does to a metered API: it is not")
    print("   faster, it is *rejected*, and every rejection is a retry you now have")
    print("   to write. (b) is slower on paper and finishes all nine.")
    print()
    print("   A Semaphore is a bag of N tickets. `async with gate` takes one and")
    print("   gives it back on the way out, so at most N coroutines are ever past")
    print("   that line. It does not slow anything down -- it stops you starting")
    print("   work the far end was never going to do.")
    print()
    print("   And (c): without `wait_for` there is no upper bound on how long an")
    print("   `await` can sit there. A hung call is not an error, it is a silence,")
    print("   and silence has no timeout unless you supply one.")


# -----------------------------------------------------------------------------
# 10. gather vs TaskGroup - what happens to the siblings when one fails.
#
# THE MISCONCEPTION: "the exception propagated, so everything stopped."
# -----------------------------------------------------------------------------


async def fails_fast() -> str:
    await asyncio.sleep(0.2)
    raise RuntimeError("extraction failed")


async def keeps_going(label: str) -> str:
    """A long sibling that announces itself when it finishes."""
    await asyncio.sleep(0.8)
    print(f"   >>> {label} finished, and nobody is waiting for it")
    return label


async def experiment_10() -> None:
    print("10. When one job fails, what happens to the others?\n")

    print("   (a) gather():\n")
    start = time.perf_counter()
    try:
        await asyncio.gather(fails_fast(), keeps_going("gather-sibling"))
    except RuntimeError as exc:
        print(f"   caught {exc!r} after {time.perf_counter() - start:.2f}s")
        print("   ...gather() has returned. Watch what the sibling does next:\n")

    await asyncio.sleep(0.8)  # give the orphan time to surface

    print("\n   (b) TaskGroup:\n")
    start = time.perf_counter()
    try:
        async with asyncio.TaskGroup() as group:
            group.create_task(fails_fast())
            group.create_task(keeps_going("taskgroup-sibling"))
    except* RuntimeError as group_exc:
        print(f"   caught {group_exc.exceptions} after {time.perf_counter() - start:.2f}s")

    await asyncio.sleep(0.8)  # same wait - and this time nothing appears
    print("   ...0.8s later, and the sibling never printed. It was cancelled.")

    print()
    print("   gather() propagates the first exception to YOU and leaves the other")
    print("   tasks running, unwatched, with nobody holding their results. They")
    print("   still consume tokens, still write to your database, and still log")
    print("   errors into a request that already returned 500.")
    print()
    print("   TaskGroup treats the group as one unit: a failure cancels the")
    print("   siblings and raises an ExceptionGroup, which is why the handler is")
    print("   `except*` -- more than one of them may have failed.")
    print()
    print("   THE RULE: `gather()` when the tasks are genuinely independent and you")
    print("   want every result (pass `return_exceptions=True` and inspect them).")
    print("   `TaskGroup` when they are parts of one job and a partial answer is")
    print("   worse than no answer -- which, for one user's agent run, it is.")


# -----------------------------------------------------------------------------


async def main() -> None:
    experiments = {
        1: experiment_1,
        2: experiment_2,
        3: experiment_3,
        4: experiment_4,
        5: experiment_5,
        6: experiment_6,
        7: experiment_7,
        8: experiment_8,
        9: experiment_9,
        10: experiment_10,
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
    # THE ENTRY POINT. Somebody has to start the loop, and `asyncio.run` is that
    # somebody. It creates the loop, runs your coroutine until it finishes, and
    # closes the loop again. Exactly one of these per program, at the very edge.
    asyncio.run(main())
