# Chapter 5 — Project

Two tracks, both mandatory. **Core 120 min · Full 210 min** — the sum of the estimates
below, and the figure the README's budget table carries.

| Part | Tier | Min |
|---|---|-----|
| Track 2 — Spendly Lite v5 | `[core]` | 60 |
| Track 3 — your own agent's Ch5 increment | `[core]` | 60 |
| Challenges 1–3 | `[depth]` | 90 |

Dataset wall-clock is not counted — start the runs and read the README while they go.

| Track | What | Domain | Graded on |
|---|---|---|---|
| 2️⃣ **The Spine** | Spendly Lite v5 — bounded context | Expenses, always | The golden datasets, **plus every prior chapter's cases still passing** |
| 3️⃣ **Your Own Agent** | Chapter 5's capability in *your* agent | Whatever you chose in Ch1 | **Evidence, not functionality** |

---

# Track 2 — Spendly Lite v5 `[core]` · 60 min

## The requirement

Spendly can now hold a conversation that does not end when the context does.

```
TURN 1   "I am tracking this month for a visa application, so keep it accurate.
          Log 500 at Metro."
         -> need_more_info, missing=['category']

TURN 2   "Groceries."          -> logged

TURN 3   "How much of my food budget is left?"    -> reported   [1 fold]

TURN 4   "Why was I tracking this month again?"
         -> "You are tracking the current month for a visa application."
```

Turn 4's answer came from turn 1, through a compaction fold. Chapter 4 could remember turn 1
only while the whole transcript still fitted; nothing in Chapter 4 could survive it not
fitting.

## What you build

| File | What |
|---|---|
| `with_sdk/context_filter.py` | The pure trimmer — `tokens`, `drop_orphans`, `align_to_turn_start`, `trim_to_budget` |
| `with_sdk/compaction.py` | `Compactor` — fold, cache, hysteresis |
| `solutions/expense_agent_v5.py` | v4 + `run_config=` |
| `solutions/check_compaction.py` | The live cases |
| `solutions/check_regression.py` | **Chapter 3's nine cases and Chapter 4's five, against v5** |
| `with_sdk/test_*.py` | Offline tests — no API key, milliseconds |
| `solutions/RUNS.md` | Evidence: model, date, real output |

### The change that is smaller than you expect

```python
result = await Runner.run(agent, prompt, session=session, context=user,
                          run_config=RunConfig(call_model_input_filter=compactor))
```

Chapter 2's tools, Chapter 3's reply types and Chapter 4's session are imported unchanged.
**If adding a context budget had meant rewriting your tools, the budget was in the wrong
place.**

### The one decision that is not obvious

```python
def make_run_state(session_id: str, *, budget: int = DEFAULT_BUDGET) -> RunState:
    return RunState(session=make_session(session_id), compactor=Compactor(budget))
```

The `Compactor` is **per conversation**, handed in — not a module global, not an attribute of
the agent. It holds a cached summary of *one* conversation, and an agent is shared by every
user.

Chapter 4 spent a golden-dataset case (M3) proving one `session_id` must not see another's
transcript. A shared compactor reintroduces that leak through a quieter door: the transcripts
stay separate and only the **summary** crosses over, so the agent states a fact from somebody
else's conversation with nothing in the transcript to explain where it came from.

> A cache belongs wherever the thing it caches belongs. The summary describes a session, so
> it lives and dies with the session.

`make_run_state()` exists so that getting this wrong requires effort.

---

## The golden datasets

```powershell
uv run pytest 05_context_window -q                                # free, ~1s
uv run python 05_context_window/solutions/check_compaction.py     # the live cases
uv run python 05_context_window/solutions/check_regression.py     # Ch3 + Ch4, against v5
```

| Case | Asks |
|---|---|
| **C1** | Does a fact from turn 1 survive a fold? |
| **C2** | **The control** — same turns, tail window instead. Does it fail? |
| **C3** | Does a long conversation complete at all, without a 400? |
| **C4** | Under budget, is the transcript passed through **untouched**? |

**C4 is the quiet one.** Most of what a context filter does is *nothing*, and a filter that
mangles short conversations while fixing long ones has made things worse for the majority of
your traffic.

**C2 is not padding.** Chapter 4's M2 caught a defect introduced by the fix that made M1
pass. A control is how you tell "the strategy worked" from "the model guessed well".

---

## Acceptance checklist

- [ ] `uv run pytest 05_context_window -q` green, no API key needed
- [ ] `check_compaction.py` — all cases pass **in one run, on one model**
- [ ] `check_regression.py` — **Chapter 3's nine and Chapter 4's five still pass against v5**
- [ ] `uv run ruff format . && uv run ruff check . && uv run pyright` all clean
- [ ] `solutions/RUNS.md` records model, date and real pasted output
- [ ] You can state why the trimmer asserts identity rather than equality
- [ ] You can state which layer should own "the summary left something out" — and why it is
      not any of the three this curriculum has taught so far

> **The regression rule is not a formality.** Chapter 3 broke Chapter 2's case 6 and was only
> caught because Chapter 2's cases were still in the dataset. Chapter 5 changes what the model
> *sees* on every single request — of all the chapters so far, this is the one most likely to
> break an earlier one.

---

## Challenges `[depth]` · 90 min

**1. A budget that is not a constant.** `DEFAULT_BUDGET = 3000` is a number somebody made up.
Derive it instead: measure the fixed cost (system prompt + tool schemas) once at startup, then
set the budget as a fraction of the model's real context limit minus that fixed cost. Which
of those two numbers is hardest to obtain, and what do you do when the provider will not tell
you?

**2. Fold on a turn boundary, not an item boundary.** `_split_at` can cut between a user
message and the reply it earned, so a summary sometimes describes half an exchange. Make folds
land only on turn boundaries. Then answer: did the summaries get better, and how do you know
that is not just your impression?

**3. Persist the summary.** The `Compactor` lives in memory, so restarting the process re-folds
the whole conversation from scratch — expensive, and the new summary will not match the old
one. Store it. Where? It is not an expense, and it is not conversation history. Chapter 4's
session/context/store table has three boxes and this fits none of them cleanly, which is the
exercise.

---

# Track 3 — Your Own Agent `[core]` · 60 min

> **Same rubric, every chapter. Graded on evidence, never on features.**

```
Your Own Agent — Chapter 5 increment
  [ ] The chapter's capability is present and working in YOUR agent
  [ ] RUNS.md has 3 new runs, dated, with actual output pasted in
  [ ] One paragraph: what broke, and what you changed
  [ ] It is not an expense tracker
```

## What "the chapter's capability" means here

1. **A `call_model_input_filter`** that enforces a token budget you chose and can defend
2. **A conversation long enough to actually trigger it** — if your filter never fires, you
   have not tested it, you have configured it
3. **A control run.** The same conversation with a naive tail window, showing a difference in
   behaviour. If both strategies produce the same answers, your conversation is too short
4. **One structural property asserted offline** — no orphans, or opens-on-user, or
   byte-identical-when-healthy. Any one. For free.

## The paragraph

Answer these three, honestly:

- What did your agent get **wrong** the first time your filter fired? (If nothing: was the
  budget high enough to fire at all?)
- Which fact did compaction lose that you did not expect it to lose?
- Did you ever weaken a check to make a run pass? What was the check actually claiming, and
  was it wrong about its subject or its threshold?

> A student whose agent broke and who documented why has met the bar. A student with a
> working agent and no runs has not.

---

## 🔁 Spendly Transfer

In the real Spendly (`C:\Users\Faraz\Desktop\Spendly\`):

1. **Measure before you choose.** Chapter 4 asked you to log
   `len(await session.get_items())` per turn for a week. Read your real p95 now and set the
   budget from that, not from this chapter's 600-token demo. If you did not log it, that is
   the task: start today and pick the number next week.
2. **A WhatsApp thread has no end.** There is no "new conversation" button, so a Spendly
   session runs for months. Decide what a fold means at that timescale — and whether a summary
   that has been folded thirty times still describes anything.
3. **One compactor per phone number.** The same rule as the spine, and the failure mode is
   worse in production than in a demo: one user's summary surfacing in another user's chat is
   a privacy incident, not a bug report.

**You're done when** a conversation that has run past your budget still answers a question
whose answer was given before the first fold.

---

## Session-by-session plan

| Session | Do | Ends when |
|---|---|---|
| 1 | README §1–§5, Exercises 1–2 | You can explain why a legal window needs two rules, not one |
| 2 | README §6–§7, Exercise 3, both tracks | `check_regression.py` green and `RUNS.md` written |
