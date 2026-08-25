# Chapter 5 — Exercises

**Track 1: drills.** Small, isolated, disposable. Rotating throwaway domains — **never
expenses**, that is the spine's job. Work in `exercises/`; nothing here is imported by the
project.

**Core 80 min · Full 180 min.** The header equals the sum below.

| # | Exercise | Tier | SDK-native | Min |
|---|---|---|---|-----|
| 1 | Warm-up — the dungeon master forgets your name | `[core]` | 🚀 | 20 |
| 2 | Warm-up — a tool that will not shut up | `[core]` | 🚀 | 20 |
| 3 | **Blank-file challenge — mandatory** | `[core]` | 🚀 | 40 |
| 4 | Guided build — the budget dial | `[depth]` | 🚀 | 40 |
| 5 | Challenge — trim by relevance, not recency | `[depth]` | 🚀 | 30 |
| 6 | Challenge — prove your trimmer, offline | `[depth]` | — | 30 |

Five of six are SDK-native. Chapter 4 was the first chapter at 100%; this one has a spike
again, so it is not — but the drills stay where the destination is.

---

## 1. Warm-up — the dungeon master forgets your name `[core]` · 20 min 🚀

`exercises/dungeon.py`. Build a text-adventure narrator with two tools — `roll_dice(sides)`
and `check_inventory()` — and a `SQLiteSession`.

Play ten turns. **Turn 1 must name your character and one thing they are trying to do.**
Then attach a tail-window filter with a budget small enough to bite, and on turn 10 ask:
*"Who am I, and why am I here?"*

**You're done when:**
- [ ] The agent answers turn 10 wrongly, or admits it does not know
- [ ] You can name the exact turn at which the answer stopped being available
- [ ] `stored` from `len(await session.get_items())` is larger than what the filter sent

> Do not fix it. Exercise 3 fixes it. This one exists so that you have felt it.

---

## 2. Warm-up — a tool that will not shut up `[core]` · 20 min 🚀

`exercises/noisy_tool.py`. Give an agent one tool, `search_lore(topic: str)`, that returns
**4,000 characters** of plausible filler every time.

Call it three times in one conversation. Measure the transcript after each call.

Then add:

```python
from agents.extensions import ToolOutputTrimmer
RunConfig(call_model_input_filter=ToolOutputTrimmer(recent_turns=1, max_output_chars=400))
```

**You're done when:**
- [ ] You have before/after transcript sizes for the same three calls
- [ ] The agent can still answer a question about the **most recent** search
- [ ] You can state in one sentence why this is a different problem from §6's, and why
      solving one does not solve the other

---

## 3. Blank-file challenge — **mandatory** `[core]` · 40 min 🚀

> **Open an empty file. No scaffolding, no copying from `solutions/`.** From Chapter 3 on,
> every chapter has one of these, and it is the only exercise that tests whether you can
> *generate* rather than *recognise*.

Build **an interview practice coach.**

- The candidate states, in turn 1, the role they are practising for and one weakness they
  want to work on. **Nothing else in the conversation repeats either fact.**
- Two tools: `next_question(topic: str)` and `score_answer(answer: str, criterion: str)`.
- A file-backed `SQLiteSession`, with a `session_id` you derive rather than accept.
- A `call_model_input_filter` that keeps the conversation under a token budget you choose.
- Run it for **at least twelve turns**, then ask: *"Remind me what I said I wanted to work
  on."*

**You're done when:**
- [ ] Twelve or more turns run without a 400
- [ ] The last turn recovers the weakness stated in turn 1
- [ ] You ran the same twelve turns with a plain tail window and it did **not**
- [ ] Your filter never orphans a tool pair and never opens on a non-user item
- [ ] The whole thing is under 120 lines

> The last box is not arbitrary. If it is over 120 lines you have rebuilt something the SDK
> gave you. Find it and delete it.

---

## 4. Guided build — the budget dial `[depth]` · 40 min 🚀

Take Exercise 3's agent and make the budget a command-line argument. Run the *same*
twelve-turn script at budgets of 400, 800, 1600 and 6400 tokens, capturing for each:

| budget | folds | total requests | final answer correct? |
|---|---|---|---|

**You're done when** you can point at the row where the answer starts being right, the row
where the cost stops falling, and say which one you would ship — with a reason that is not
"the middle one".

---

## 5. Challenge — trim by relevance, not recency `[depth]` · 30 min 🚀

Every strategy in this chapter is positional: keep the newest, summarise the oldest. Build
one that is not.

Score each turn (a keyword overlap with the current question is enough — this is not a RAG
chapter) and keep the highest-scoring turns that fit the budget, **plus** whatever
`align_to_turn_start` and `drop_orphans` demand.

**You're done when** you have found the case where it is clearly better than recency, **and**
the case where it is clearly worse. Both exist. If you only found one, you have not run
enough turns.

---

## 6. Challenge — prove your trimmer, offline `[depth]` · 30 min

No API key. Write `test_my_trim.py` for Exercise 3's filter, asserting the four properties:

1. never orphans a call/result pair
2. never exceeds the budget
3. always opens on a legal turn boundary
4. **returns a healthy window byte-identical — by identity, not equality**

Property 4 is the one people skip. Then break it deliberately: rewrite your filter to
reconstruct each item as a fresh dict with the same keys. Watch test 4 fail — and then run it
against the live model and watch a 400 that mentions neither trimming nor tokens.

**You're done when** the identity assertion has caught a bug you introduced on purpose, and
you can explain what `provider_data.thought_signature` has to do with it.

---

## Where these go

Nothing in `exercises/` is graded, imported, or maintained. It is scratch space that the
quality gate still holds to the same standard as everything else — `ruff`, `pyright` and
`pytest` all run over it, deliberately.
