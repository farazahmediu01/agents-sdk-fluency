# Audit Action Plan

> Response to `prompts/exhaustive-audit.md`, filtered against the boundaries in
> `prompts/exhaustive-system-prompt-v1.md`. **Nothing in the codebase has been modified.**
>
> Mission filter applied throughout: *does this make a student a market-ready Forward
> Deployed Engineer by 2027?* Anything that does not is rejected regardless of merit.

---

## 0. The finding that changes the plan

**Five of the audit's six backlog tickets describe defects that are already fixed and shipped.**

Every claim below was checked against the code, not against the prose:

| Ticket | Audit says | Code says | Evidence |
|---|---|---|---|
| TCK-001 | `true` → `1.0` silently accepted | **Fixed** | `expense_tools.py:61-98` — `_reject_bool` + `Amount = Annotated[float, BeforeValidator(...), Field(gt=0)]` |
| TCK-002 | Raw `"gt"` reaches the model | **Fixed, and better than proposed** | `typed_tool.py:163-193` — maps **7** constraint names, guards non-dict props |
| TCK-003 | Harness clears session per turn | **Fixed** | `check_multiturn.py:397-403` — `session_for()`, built once per case |
| TCK-005 | Category inferred when omitted | **Fixed** | `expense_agent_v3.py:103-105` — *"If the user does not name a category AT ALL, do not infer one."* |
| TCK-006 | Traveller leaks across control runs | **Fixed** | `session_demo.py:106-126` — split into PART 1a / PART 1b |
| TCK-004 | No orphan-window guard | **Genuinely open** | `shared/` contains only `__init__.py`, `models.py` |

### Why the audit got this wrong, and why it matters more than the tickets

This curriculum documents every defect **in place**, in the file that carries the fix, in the
past tense. `check_multiturn.py:370-388` is a docstring that opens:

```
THE BUG THIS FUNCTION SHIPPED FIRST, because it is the one a multi-turn
harness is built to make:

    session = make_session(...)          # inside the turn loop
    await session.clear_session()        # <- wipes turn 1 before turn 2 runs
```

The audit read that block and filed it as **TCK-003, severity P0, live**. The literal next
lines of the same docstring say *"Reset per CASE, never per TURN"*, and the working code
twenty lines down does exactly that.

**The repo's greatest pedagogical asset — documented failure narratives — is unreadable to a
reviewer who does not run the code.** That is worth knowing before anyone acts on any review
of this repo, human or machine. It is also the exact skill an FDE is hired for: *a finding you
have not reproduced is a hypothesis, not a defect.*

Had this backlog been executed as written, the cost would have been a week of re-fixing fixed
bugs — and two acts of real damage (TCK-006 and §5d, below).

---

## 1. Curriculum Filter Matrix

| # | Audit recommendation | Verdict | Architectural justification |
|---|---|---|---|
| 1 | TCK-001 — `BeforeValidator` bool rejection | ❌ **REJECT — already shipped** | Fixed at `expense_tools.py:88`. The proposed patch is a near-verbatim copy of code already in the file. |
| 2 | TCK-002 — `_clean_schema` gt/ge rewrite | ❌ **REJECT — already shipped, proposal is a downgrade** | Ours maps 7 names (`gt/ge/lt/le/multiple_of/min_length/max_length`); theirs maps 2 and drops the `isinstance(prop, dict)` guard, so it raises on any non-dict property. Applying it would *lose* four working constraints. |
| 3 | TCK-003 — per-case session clearing | ❌ **REJECT — already shipped** | The audit quoted our own docstring documenting the fixed bug and filed it as live. |
| 4 | **TCK-004 — `clean_orphaned_turns`** | ✅ **ACCEPT the requirement, REJECT the code** | The only real gap. But the proposed implementation is broken (§2) and this is **Chapter 5's core deliverable**, not a patch to Ch0–4. Building it now spends the chapter's central lesson before the chapter opens. |
| 5 | TCK-005 — forbid category inference | ❌ **REJECT — already shipped** | Fixed at `expense_agent_v3.py:103-105`; case 8 is in the passing 58/58 dataset. |
| 6 | TCK-006 — deep-copy `Traveller` between runs | ❌ **REJECT — actively harmful** | Already fixed *the right way*. PART 1b keeps the shared context **deliberately**: state leaking through the other primitive is the single most common reason people conclude they do not need sessions. Deep-copying would delete the chapter's opening lesson to fix a bug that no longer exists. |
| 7 | §5d — replacement `pyproject.toml` | ❌ **REJECT — a regression** | Collapses 15+ per-folder `executionEnvironments` into 5 per-chapter ones. Every chapter has its own `tools.py`; a chapter-level root resolves all of them to whichever loads first. `CLAUDE.md` names this as the #1 config trap. Also downgrades `openai-agents>=0.20.0` → `>=0.1.0` and sets `testpaths = ["."]`, which would collect `.venv`. |
| 8 | §3c — migrate to the Responses API | ❌ **REJECT — boundary #2** | Non-negotiable. You cannot teach trimming when the server owns the transcript. Already answered in `RESPONSES_VS_CHATCOMPLETIONS.md`; the audit calls it "structural debt" without engaging the argument. |
| 9 | §3c — remove `_bootstrap.py` path shims | ⚠️ **DEFER — real, not urgent** | Correctly identified as fragile. But it is 3 lines buying one continuous spine, and the alternative (a `src/` package) is a repo-wide refactor. Revisit at Ch10, when FastAPI forces a packaging decision anyway. |
| 10 | §5c — three capstone blueprints | ⚠️ **ACCEPT ONE, REJECT THREE** | Ch12's assessment validity depends on the domain being **unfamiliar and unpublished**. Printing three specs in a public repo converts a cold build into a warm one. Keep them sealed; see §3. |
| 11 | Checklist #3/#4/#17 — SQLite concurrency, `session_id` as authz, multi-worker | ✅ **ACCEPT — highest FDE value in the whole audit** | The audit rates these merely "UNDERDEVELOPED" and files no ticket. They are the most FDE-shaped gap in the roadmap: an FDE's job is deploying an agent into someone else's infrastructure, where "works on one process" is the failure mode. Assign to Ch10. |
| 12 | §6b — "34-hour core path" | ❌ **REJECT — factually wrong** | See §4. Chapters 0–4 alone are **≈44.5 core hours**. The audit asserts a number it did not compute. |
| 13 | Rate-limit defaults → `gemini-3.5-flash-lite` | ❌ **REJECT — already shipped** | `.env.example:43`, plus the measured per-model quota table (500/day vs 20/day) in four files. |

**Score: 1 accepted requirement (with its code rejected), 1 accepted gap the audit under-rated,
1 partial, 2 deferred, 8 rejected.**

---

## 2. P0 / P1 Code Diffs

### There are no P0 diffs to write for Chapters 0–4.

All five claimed defects are fixed, the gate is clean (`0 ruff · 0 pyright errors · 0 warnings ·
86 tests`), and both golden datasets pass in one run (multi-turn 36/36, regression 58/58).
Writing patches here would mean editing working code to match a report that misread it.

### The one real gap — and why the proposed code cannot ship

The audit's `clean_orphaned_turns` has a defect that makes it worse than nothing:

```python
# proposed — shared/session_utils.py
call_ids = {item.call_id for item in cleaned if hasattr(item, "call_id") and item.role == "assistant"}
```

**Session items in this repo are TypedDicts, not objects.** `growth_demo.py:70-72` proves it:

```python
def kind_of(item: Any) -> str:
    """One label per stored item. `TResponseInputItem` is a union of TypedDicts."""
    return str(item.get("role") or item.get("type") or "?")
```

`hasattr({"call_id": "x"}, "call_id")` is `False`. Every guard fails, `call_ids` is empty, the
filter never fires, and the function **returns the input unchanged while appearing to work**.
It is a silent no-op wearing the costume of a fix — the exact failure class this curriculum
teaches against in Ch2 §7b.

Two further faults: it strips orphaned *outputs* but not orphaned *calls* (a trailing
`function_call` with no result is equally a 400), and it is typed against
`ChatCompletionMessageParam`, which is the wrong shape for the SDK's item stream.

### The corrected version — **for Chapter 5, not for now**

Written here so the requirement is captured, **not to be installed**. It belongs in
`05_context_window/`, built by the student after they have felt the 400:

```python
def drop_orphans(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove tool calls missing their result, and results missing their call.

    A tail window (`get_items(limit=N)`) slices by item count, so it can begin on a
    `function_call_output` whose `function_call` fell outside the window. The model is
    handed an answer to a question it cannot see having asked, and the server 400s.

    Items are TypedDicts -- use .get(), never attribute access.
    """
    call_ids = {i.get("call_id") for i in items if i.get("type") == "function_call"}
    result_ids = {i.get("call_id") for i in items if i.get("type") == "function_call_output"}
    paired = call_ids & result_ids

    return [
        item
        for item in items
        if item.get("type") not in {"function_call", "function_call_output"}
        or item.get("call_id") in paired
    ]
```

**Its test is the interesting part**, and it is the assertion the audit never proposes:
`growth_demo.py` PART 3 already produces windows flagged `orphaned=YES` at `limit=2` and
`limit=6`. Feed those exact windows in; assert the output is orphan-free **and that a
non-orphaned window is returned byte-identical**. A trimmer that quietly rewrites healthy
history is a worse bug than the one it fixes.

---

## 3. Chapters 5–12 — refined specification

Only two changes to the roadmap. Ruthless prioritisation means the other ten chapters keep
their existing hypotheses until the chapter before each is built and validated.

### Ch5 — The Context Window `🔨 → 🚀` · **absorbs TCK-004**

Already the best-prepared chapter in the repo: Ch4 §9 does not assert its problem, it
**measures** it (transcript `1,377 → 4,782` chars over five turns; `tok/req` `401 → 714`), and
Ch4 §9b already demonstrates the SDK's `limit=N` producing orphaned windows.

| Layer | Content |
|---|---|
| 🔨 Spike | `drop_orphans` + a token-budget trimmer, ≤60 lines, built after seeing a real 400 |
| 📖 Observe | `SessionSettings(limit=N)` — why counting items is not counting tokens |
| 🚀 SDK | Spendly Lite v5: trimming behind a seam, chosen strategy explicit |
| 📐 Proof | Ch3's 9 cases **and** Ch4's 5 multi-turn cases must both stay green |

**Bug-first sequencing, per the playbook:** the student runs a `limit=2` window *first*, gets
the 400, and only then writes the guard. Do not warn them.

### Ch10 — Serving & MCP · **absorbs checklist #3, #4, #17**

The audit's most valuable content is the three items it filed no ticket for, because they are
where an FDE actually fails on a client site:

1. **`session_id` is an authorisation decision wearing a cache key's costume.** Ch4 says this
   in prose. Ch10 makes it code: derive the id server-side from an authenticated principal,
   and include a drill where a spoofed id reads another user's conversation.
2. **`:memory:` is a bug with a schedule.** It works all through development — one process,
   one object — and fails on the second worker as *"the agent forgot everything."* Ch4 §5b
   already has the demo; Ch10 runs it under two uvicorn workers so the amnesia is real.
3. **SQLite under concurrent writes.** `database is locked` is a deployment failure, not a
   Python one, and it is what an FDE meets in week one at a client.

**Why Ch10 and not now:** all three require a server to be meaningful. Teaching multi-worker
safety before FastAPI exists is teaching a symptom with no way to reproduce it.

### Ch12 — Cold Build Capstone · **blueprints accepted, sealed**

The audit's three domains (smart grid / credit underwriting / cargo logistics) are well chosen
— each maps cleanly onto 🧠🔒📐, and each has a natural approval gate.

**But publishing them destroys the instrument.** Ch12's only job is distinguishing *learned it*
from *copied it*, which requires a domain the student has not seen specified. A student who
reads `AUDIT_ACTION_PLAN.md` in a public repo has read the capstone.

**Decision:** move the three specs to an instructor-only section of `INSTRUCTOR.md` before Ch12
is built, keep one in reserve per cohort, and rotate. Do not expand to three published tracks —
one cold build is the assessment; three is scope creep wearing a rubric.

---

## 4. The risk the audit did not find

The system prompt's boundary #3 says: *reject anything that pushes core completion past
**34 hours**.* The audit repeats "34-hour core path" as established fact in §6b.

**Neither checked it.** Summing the chapters' own published budgets:

| Ch | Core |
|---|---|
| 0 Python for Agents | ≈6.0 |
| 1 The Agent Loop | ≈8.0 |
| 2 Typed Tools | ≈11.0 |
| 3 Structured Outputs | ≈9.0 |
| 4 Sessions & State | ≈10.5 |
| **Ch0–4 subtotal** | **≈44.5 hrs** |

**Already 10.5 hours over the ceiling, with eight chapters unbuilt.** At the current mean
(≈8.9 core hrs/chapter) the finished curriculum lands near **115 core hours** — roughly five
months at 20 hrs/week, for the curriculum alone.

This is the actual threat to FDE-readiness by 2027, and it is larger than every code defect in
the audit combined. Three honest options:

| Option | What it costs | Recommendation |
|---|---|---|
| **Raise the ceiling to ~100 hrs and say so** | Nothing but the fiction | ✅ **Do this.** The repo's own rule is *"state budgets honestly or don't state them."* A 34-hour ceiling that five chapters already broke is exactly the dishonest header Ch1's retrofit deleted. |
| Compress Ch5–12 to ≈4 core hrs each | Would produce the shallow chapters the Depth Policy exists to prevent | ❌ |
| Cut chapters | Ch6 (Evals) and Ch12 (Capstone) are structural; Ch11 is already optional/paid | ⚠️ Only Ch9 and Ch11 are genuinely cuttable |

**Recommended split:** declare Ch0–6 the **core FDE track** (≈62 hrs — a complete, evaluable,
deployable agent skill set ending on the evals chapter) and Ch7–12 the **specialist
extension**. That gives a defensible stopping point, which a 12-chapter monolith does not.

---

## 5. Recommended execution order

| # | Action | Effort | Gate |
|---|---|---|---|
| 1 | **Do nothing to Ch0–4.** Both datasets green, gate clean | 0 | — |
| 2 | Correct the budget claim; adopt the Ch0–6 / Ch7–12 split in `CLAUDE.md` | 30 min | Roadmap table updated |
| 3 | **Build Chapter 5**, absorbing TCK-004 as its spike | 1 build cycle | Ch3's 9 cases + Ch4's 5 cases still green |
| 4 | Append checklist #3/#4/#17 to Ch10's roadmap row as committed scope | 15 min | — |
| 5 | Move the three capstone blueprints to instructor-only before Ch12 | at Ch12 | — |
| 6 | Revisit `_bootstrap.py` when Ch10 forces packaging | at Ch10 | — |

**Not scheduled, deliberately:** TCK-001, 002, 003, 005, 006, the `pyproject.toml` rewrite, and
the Responses migration.

---

## 6. What to keep from the audit

Rejecting most of the backlog is not the same as rejecting the review. Three things in it are
worth keeping:

1. **Checklist items #3, #4, #17** — the FDE gap, correctly spotted and under-rated by its own
   author. Now committed to Ch10.
2. **The three capstone domains** — genuinely well-mapped to the three axes. Sealed, not
   published.
3. **The 19-point checklist as a format** — a standing pre-release audit for Ch5+ is a good
   idea. Run it against **code**, with a reproduction required before any severity is assigned.

And one thing to take from how it failed: **every finding needs a reproduction before it gets a
severity.** Five P0s here were prose. That is the FDE lesson of this whole exercise, and it is
worth more to a student than any of the patches would have been.
