# Chapter 5 — Runs

Evidence, not claims. Model, date, and the output the code actually printed.

| | |
|---|---|
| **Model** | `gemini-3.5-flash-lite` (Chat Completions via Gemini's OpenAI-compatible endpoint) |
| **Date** | 2026-08-26 |
| **Offline tests** | **24 in Ch5**, 110 repo-wide — no API key, ~1 second |
| **Gate** | `ruff format` clean · `ruff check` clean · `pyright` **0 errors, 0 warnings** · `pytest` **110 passed** |

---

## The offline layer carries most of the proof

This is the chapter's central practical decision, and it is why the live dataset is four
cases rather than fifteen. A trimmer is a pure function over a list, so its properties cost
nothing to check:

```powershell
uv run pytest 05_context_window -q      # 24 tests, ~1 second, no key
```

| File | Tests | Asserts |
|---|---|---|
| `with_sdk/test_trim.py` | 14 | never orphans · fits the budget or floors · always opens on a user message · **byte-identical when healthy** · `provider_data` survives |
| `with_sdk/test_compaction.py` | 10 | no-op under budget · summary lands in `instructions` · hysteresis holds and eventually releases |

A dataset of fifteen twelve-turn cases would be 150+ requests — half a day of free-tier
quota per run, on the chapter least able to afford it. Pushing the assertions down to the
cheap layer is not a shortcut here; it is what makes the suite runnable more than once a day.

---

## Chapter 5's dataset — `check_compaction.py`

```powershell
uv run python 05_context_window/solutions/check_compaction.py
```

**All four cases pass. C1 and C2 are the experiment; C3 and C4 are the guards.**

### C1 — a fact from turn 1 survives a fold ✅ 3/3

Turn 1 states a reason that lives nowhere else: not in the `User` context, not returned by
any tool, never repeated.

```
    turn 1: I am reconciling this month for a visa application...
      folds=0  Which category does this expense belong to?
    turn 2: Groceries.
      folds=0  I have logged PKR 500 at Metro under Groceries for today.
    turn 3: How much of my food budget is left?
      folds=1  You have PKR 17500.0 left of your PKR 25000.0 Food & Dining budget
    turn 4: What is my transport budget?
      folds=2  Your Transportation budget is PKR 12000.0, you have spent PKR 900.
    turn 5: And utilities?
      folds=3  For Bills & Utilities, your budget is 18000.0 PKR, you have spent
    turn 6: Remind me why I am reconciling this month.
      folds=3  You are reconciling this month for your upcoming visa application.
      PASS  a fold actually fired (otherwise this case tests nothing)
      PASS  recovered 'visa' from turn 1
      PASS  did not claim to have lost it
```

The first check is not padding. A case that asserts "the fact survived compaction" while no
compaction happened has proved that a short conversation works.

### C2 — THE CONTROL: a tail window loses it ✅ 2/2

The same six turns, the same budget, the same agent. **Only the strategy differs.**

```
    turn 6: Remind me why I am reconciling this month.
      folds=0  You did not mention a reason for reconciling this month.
      PASS  no summarisation happened (tail window does not summarise)
      PASS  did NOT recover 'visa' from turn 1
```

Put the two answers side by side and the chapter is in two lines:

```
COMPACTION    "You are reconciling this month for your upcoming visa application."
TAIL WINDOW   "You did not mention a reason for reconciling this month."
```

**And note how the control failed.** It did not invent a reason; it said it had not been
given one. That is the finding that rewrote README §7 — the spec predicted compaction's
danger was an agent that forgets without knowing. The opposite is true: *deletion* leaves a
gap the agent can feel and report, and it is *summarisation* that fills the gap with
something plausible.

### C3 — a long conversation completes at all ✅ 3/3

Seven turns, six folds, no 400 and no `MaxTurnsExceeded`.

```
      folds=0  Which category does this expense belong to?
      folds=1  I have logged PKR 1,200 at Careem under Transportation for today.
      folds=1  Which category does this expense belong to? (e.g., Groceries, Shop
      folds=3  I have recorded PKR 300.00 at Imtiaz under Groceries.
      folds=4  Your total for Food & Dining this month is PKR 9,000.0, out of a b
      folds=5  You have spent PKR 2,100.0 on Transportation this month, leaving P
      folds=6  Your remaining budget for Food & Dining is PKR 16,000.0 and for Tr
      PASS  the run produced a reply at all
      PASS  no 400 / output error
      PASS  did not burn max_turns
```

Six folds in seven turns is a lot, and it is the 700-token fixture budget doing it, not a
defect — the shipping default is 3000. It is a useful thing to see once: **a budget set too
low turns compaction from a saving into a tax**, and the folds column is where that shows up
before the invoice does.

### C4 — under budget, nothing is touched ✅ 4/4

```
    turn 1: Log 500 at Metro.
      folds=0  Which category does this expense belong to?
    turn 2: Groceries.
      folds=0  I have logged PKR 500 at Metro under Groceries.
      PASS  the conversation really is under budget
      PASS  no fold fired
      PASS  branch is logged
      PASS  the expense was written
```

Most of what a context filter does is nothing. A filter that mangles short conversations
while fixing long ones has made things worse for the overwhelming majority of real traffic,
and C1–C3 would never have noticed.

---

## Four defects, all found by running the code

### 1. The window that was orphan-free and still illegal

Found in `filter_demo.py` PART 3, before the dataset existed.

```
400 INVALID_ARGUMENT
"Please ensure that function call turn comes immediately after a user turn
 or after a function response turn."
```

`drop_orphans` had kept every call/result pair intact. The window still opened on an
assistant message followed by a `function_call`. **Pairing is necessary and not sufficient:**
a conversation is a sequence with legal start positions, not a bag of items that reference
each other. Fixed by `align_to_turn_start`; taught as README §3, where the spike's table
shows five of six orphan-free windows printing `legal? NO`.

### 2. The cost bug in the cache I had already warned about

`compaction.py`'s own docstring said a summariser without a cache would run three times per
turn. It *had* a cache, and still spent **13 model calls on 9 turns** — more than the
conversation itself.

The trigger (`tail > budget * keep`) and the target (cut back to `budget * keep`) were the
same number, so the next model call crossed it again immediately.

```
before hysteresis:   9 turns -> 13 folds
after  hysteresis:   9 turns ->  4 folds     identical answers
```

> **A cache whose invalidation condition is also its reset condition is not a cache.**

### 3. The empty window — found by the dataset, on its first run

C1 turn 2 killed the run:

```
400 INVALID_ARGUMENT
"* GenerateContentRequest.contents: contents is not specified"
```

`align_to_turn_start` scans *forward* for a user message. A fold had advanced past the last
one, so the window contained none, and the filter handed the SDK an empty list. **An empty
request is not a small request; it is an invalid one**, and the error names neither trimming
nor budgets.

Two fixes, because there were two causes:

- `Compactor._split_at` now snaps **backwards to a user-message index**, so a fold can never
  land inside a turn. This was Challenge 2 in `PROJECT.md` before it turned out to be
  load-bearing — *a boundary you have to repair afterwards is a boundary you should have
  chosen in the first place.*
- `trim_to_budget` gained a floor: if aligning would empty the window, send the current turn
  regardless of size. **When the budget and validity conflict, validity wins.**

### 4. Two checks that were wrong about their subject, not their threshold

Both are more instructive than the code fixes.

**`test_the_window_fits_the_budget`** asserted `tokens(window) <= budget` and failed at
`201 <= 200` the moment the floor was added — because the newest turn is 201 tokens and the
floor sends it anyway. Dropping `200` from the list would have produced a green check that
no longer tested the interesting case. The real claim is *"fits the budget, unless fitting
would have meant sending nothing"*, so that is what it asserts now.

**C4 passed, then failed an hour later, unchanged.** Same two turns, same agent, one fold.
The conversation sits within a few tokens of the 700 fixture budget, so whether it crossed
depended on how verbose the model felt. The check claimed *"under budget, the filter is a
no-op"* and never established that the conversation was under budget — what it actually
measured was word count.

Fixed by making the premise true by construction (C4 runs at the **shipping** budget of
3000) and asserting the premise as its own check.

> **A flaky check is usually a check whose premise you forgot to assert.**

---

## Two operational findings

**Never run two golden-dataset harnesses concurrently.** They look independent and are not:
every one calls `expense_store.reset(seeded=True)` against the *same* ledger file. Started
in parallel here by mistake, caught before either produced output, and now recorded in
`CHAPTER_PLAYBOOK.md` §5 — the failures it produces read exactly like agent defects and
cannot be reproduced afterwards.

**A dataset run outlives a 10-minute tool timeout.** The first full `check_compaction.py`
run was killed at minute nine with three cases complete and unrecorded. Redirect to a log
and run in the background.

---

## Regression — `check_regression.py`

```powershell
uv run python 05_context_window/solutions/check_regression.py
```

Chapter 4 ran Chapter 3's nine cases against v4. This runs **Chapter 3's nine and Chapter
4's five** against v5 — and does it with the compactor **attached** at the shipping budget,
because passing with `compactor=None` would reproduce v4 exactly and prove nothing.

Chapter 5 changes what the model sees on *every* request. Of all the chapters so far, it is
the one most likely to break an earlier one.

### Two full runs. **93/94 both times — and a DIFFERENT case each time.**

| Run | Score | Failure | Verdict |
|---|---|---|---|
| 1 | 93/94 | `ch3/6` — date logged as `2026-05-08` | **model drift.** Fixed in the prompt |
| 2 | 93/94 | `ch4/M5` — Ayesha remaining `8500` not `1500` | **pre-existing flake.** Not Chapter 5's |

**A different case failing on each run is the signature of non-determinism, not of a
systematic break.** Both were diagnosed by probe before anything was changed, and neither
was caused by this chapter.

All five of Chapter 4's multi-turn cases passed in run 1. All nine of Chapter 3's passed in
run 2.

### Failure 1 — `ch3/6`, and it was not Chapter 5

The suspicion was reasonable: Chapter 5 rewrites what the model sees on every request. The
probe settled it in four calls:

```
filter=ON  folds=0 branch=logged date=2026-05-08
filter=OFF folds=0 branch=logged date=2026-05-08
filter=ON  folds=0 branch=logged date=2026-05-08
filter=OFF folds=0 branch=logged date=2026-05-08
```

Identical with the compactor and without it, and `folds=0` means the filter never fired —
the model saw byte-identical input to Chapter 4's. **Upstream model drift against an agent
nobody had touched.** The case had passed in Chapter 3 and again in Chapter 4.

The prompt had always carried the example — `"05/08/2026 (the 5th of August)"` — and told
the agent to *convert it to YYYY-MM-DD*. It obeyed perfectly, using its own MM/DD default,
discarding the parenthetical that existed precisely to settle the question.

> **A rule that names the right example can still leave the decision open.** The model does
> not fill that gap with nothing; it fills it with a default you never chose and cannot see.

Fixed in `expense_agent_v3.py` and `expense_agent_v4.py` identically, with the narrative
recorded above the prompt in both. Verified **twice on case 6 and twice on case 7** —
narrowing a date rule is exactly the change that breaks the refusal case next door:

```
case 6  branch=logged   rows=1  2026-08-05
case 7  branch=refused  rows=0  (nothing written)
case 6  branch=logged   rows=1  2026-08-05
case 7  branch=refused  rows=0  (nothing written)
```

Run 2 then scored case 6 at 7/7, recovering in 2 turns instead of 4.

### Failure 2 — `ch4/M5`, intermittent and older than this chapter

```
    turn 1 (Faraz)   PASS  remaining == 17500   turns=4
    turn 2 (Ayesha)  FAIL  remaining == 1500 (got 8500.0)   turns=2
```

`8500 = 9000 − 500`, where the seeded food total is 7500. The agent did the arithmetic
against a number it already had instead of calling `month_total` — and did it in **two**
model turns where every healthy run takes three.

That is Chapter 4 §8's own documented failure mode: *a session stops context being lost, and
cannot stop the model reciting a fact instead of re-reading it.* Eight probe runs, four with
the compactor and four without:

```
  filter=ON  Faraz   folds=0 turns=3 got=17500.0 OK
  filter=ON  Ayesha  folds=0 turns=3 got=1500.0  OK
  filter=OFF Faraz   folds=0 turns=3 got=17500.0 OK
  filter=OFF Ayesha  folds=0 turns=3 got=1500.0  OK
  ... x2
```

**Eight for eight, `folds=0` throughout.** A two-turn conversation is nowhere near the 3000
budget, so the compactor never runs and cannot be the cause. Roughly one failure in ten,
pre-existing, and left unfixed deliberately: Chapter 4's M2 defect was *caused* by a prompt
rule added to make another case pass, and adding more instruction pressure to a case that
succeeds 90% of the time is how that happens again.

> **Recorded rather than patched.** A known flake with a diagnosis and a reproduction is an
> honest state. A green suite bought with a rule nobody tested is not.

### The harness gap this exposed

`run_ch3` printed `folds=` on every case; `run_ch4` did not. So the single most useful
question — *did the compactor touch this run?* — needed a separate probe to answer. Now both
print it, including when it is zero.

> A harness that omits the number you will reach for is a harness you will edit under
> pressure, at the moment you least want to be editing it.
