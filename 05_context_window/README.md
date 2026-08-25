# Chapter 5 — The Context Window 🧠📐

> **Chapter 4 ended with a table it did not explain.**
>
> ```
>   limit     items    chars   first item            orphaned?
>   --------------------------------------------------------------
>   2             2      372   function_call_output  YES
>   6             6    1,221   function_call_output  YES
> ```
>
> That was the SDK's only knob for a transcript that grows forever, and Chapter 4 said it
> "counts the wrong unit" and "some providers reject that" — then moved on.
>
> Read those two words again: **some providers**. Nobody checked. This chapter starts by
> checking.

| | |
|---|---|
| **Axis** | 🧠 State · 📐 Proof |
| **Depth** | 🔨 one spike (≤60 lines, disposable) → 🚀 SDK |
| **Budget** | **Core ≈ 7 hrs** · Full ≈ 12 hrs |
| **Sessions** | 2 sessions of 90–120 min |
| **Builds on** | Ch4's session and packing agent, Ch4's spine, both imported unchanged |

---

## The one sentence to memorise

> **A session is what you store. A filter is what you send. They are not the same list, and
> the bill is for the second one.**

Everything in this chapter follows from that split. Chapter 4 built the first list and
watched it grow. This chapter builds the second and decides what goes in it.

---

## Budget

Every section is marked `[core]` or `[depth]`. A student on the core path can skip every
`[depth]` block and still meet Chapter 6's prerequisites. The header equals the sum.

| § | Section | Tier | Min |
|---|---|---|-----|
| 1 | The 400 you have not seen yet | `[core]` | 25 |
| 2 | Counting the right unit | `[core]` | 30 |
| 2b | `tiktoken`, and why it changes nothing | `[depth]` | 20 |
| 3 | 🔨 The spike — trim to a budget | `[core]` | 40 |
| 4 | What the spike lost | `[core]` | 20 |
| 5 | 🚀 The seam | `[core]` | 35 |
| 5b | `ToolOutputTrimmer` — the other growth curve | `[depth]` | 25 |
| 6 | Compaction — summarise the head | `[core]` | 45 |
| 6b | Cheaper summarisers, and the arithmetic | `[depth]` | 30 |
| 6c | Composing filters, and ordering hazards | `[depth]` | 30 |
| 7 | What a summary costs you | `[core]` | 20 |
| | **README** | | **core 215 · full 320** |
| | `EXERCISES.md` | | core 80 · full 180 |
| | `PROJECT.md` | | core 120 · full 210 |
| | **Chapter total** | | **core 415 (≈7 hrs) · full 710 (≈12 hrs)** |

This is the first chapter deliberately smaller than the one before it. Chapter 4 was ≈10.5
core hours. The saving is real and not a thinning: this chapter's proof layer runs offline,
so the hours that Chapter 4 spent waiting on golden-dataset runs are simply not spent here.

---

## §1 — The 400 you have not seen yet `[core]` · 25 min

Chapter 4 hedged. Let us stop hedging.

```powershell
uv run python 05_context_window/spike/orphan_400.py     # 2 requests
```

The script takes the exact window Chapter 4 flagged — `items[-6:]` from a real captured
conversation — and sends it. Then it sends the *same* window with the orphan removed.

### 🔮 Predict first

Write down, before running:

1. Does the orphaned window fail, or does the provider quietly cope?
2. If it fails, what does the error message talk about? Tokens? Length? Something else?

Rate your confidence 1–5.

<details>
<summary>What actually happened</summary>

```
  A. the orphaned window
    7 items, first = function_call_output
    REJECTED -> BadRequestError: '* GenerateContentRequest.contents[0].parts[0]
                .function_response.name: Name cannot be empty.'

  B. the same window, orphans dropped
    6 items, first = assistant
    ACCEPTED -> You have packed a pair of hiking boots so far.
```

**The error does not mention orphans, tool calls, or trimming.** It says a name is empty.

That is what this class of bug looks like from the outside. A tool *result* carries a
`call_id` and nothing else; the function's **name** lives on the *call*. Cut the call away
and the provider has a result it cannot attribute — so it reports the symptom it can see,
which is a missing name, three layers below the mistake you actually made.

> **You will not debug this from the error message.** You will debug it from knowing that a
> window can start in the middle of a turn. That is why this chapter exists.

</details>

### 🔨 Practice 1 (10 min)

Change `items[-6:]` to `items[-5:]`, `items[-4:]`, `items[-2:]`. Which of them fail?

**You're done when** you can state the rule for which slice sizes are safe *without*
running them — and you have found at least one that surprised you.

### 🔨 Practice 1b `[depth]` (5 min)

Delete `NEXT_TURN` from both `send()` calls and run again. A *third* distinct 400 appears:
`"Requests ending with a model turn are not supported."`

**You're done when** you can say why appending the user's next message makes that error go
away, and why a real trimmer never sees a transcript without one.

---

## §2 — Counting the right unit `[core]` · 30 min

`SessionSettings(limit=N)` counts **items**. Here is what an item is worth:

| Item | Realistic size |
|---|---|
| `"Groceries."` | ~4 tokens |
| a `function_call_output` holding a search result | ~4,000 tokens |

Both are one item. `limit=10` is therefore not a budget; it is a guess that happens to be
right for conversations shaped like the one you tested on.

**A budget has to count the thing you are charged for.** That is tokens.

### How this chapter counts them

```python
CHARS_PER_TOKEN = 4

def tokens(items: list[Item]) -> int:
    return len(json.dumps(items)) // CHARS_PER_TOKEN
```

That is wrong, deliberately, and it is the right kind of wrong. Four characters per token
is within roughly 15% for English JSON. It needs no download, no per-provider tokeniser, and
no network call in a function that runs before *every* model call.

> **You are not measuring, you are budgeting.** A budget you enforce yourself with a margin
> you chose does not need three significant figures. It needs to be cheap, monotonic, and
> never to under-estimate by so much that you sail past the real limit.

### 🔨 Practice 2 (15 min)

```powershell
uv run python 05_context_window/with_sdk/filter_demo.py    # PART 1 is free
```

PART 1 prints the captured transcript's size and trims it to four budgets. Before running,
predict the number of items kept at a 400-token budget.

**You're done when** your prediction is within two items, and you can explain why the
`in` column stays at 22 while `out` changes.

---

## §2b — `tiktoken`, and why it changes nothing `[depth]` · 20 min

Install `tiktoken`, count the captured transcript properly, and compare against
`len(json.dumps(items)) // 4`.

You will find an error of a few percent for this transcript, larger for one heavy in
punctuation or non-English text. Then answer the question that matters:

**Does the true count change any decision you made?** Your budget is a number you invented.
If a 15% error moves you from "safe" to "over the limit", the problem is not the estimator —
it is that you set the budget with no margin.

**You're done when** you can argue for the estimator *or* for `tiktoken` on grounds of cost
and failure mode rather than accuracy, and you have written down which you would ship and
why.

> Gemini's tokeniser is not `tiktoken`'s. An exact count for the wrong model is not an
> exact count. Being *approximately right for every provider* beats being *exactly right for
> one*, unless you only ever ship to one.

---

## §3 — 🔨 The spike: trim to a budget `[core]` · 40 min

```powershell
uv run python 05_context_window/spike/trim.py    # free, offline
```

> **Disposable, by policy.** `spike/` is ≤60 lines, never imported by the project, never
> maintained, and safe to delete when this chapter validates. It exists so that when an
> agent "forgets" something at 2am you can picture the list being cut.

The whole mechanism is three ideas:

```python
def trim(items, budget):
    kept = []
    for item in reversed(items):          # 1. newest first
        if kept and tokens([*kept, item]) > budget:
            break
        kept.insert(0, item)
    return drop_orphans(kept)             # 2. repair the seam
```

`drop_orphans` keeps a `function_call` only if its `function_call_output` is also in the
window, and vice versa:

```python
calls   = {i.get("call_id") for i in items if i.get("type") == "function_call"}
outputs = {i.get("call_id") for i in items if i.get("type") == "function_call_output"}
paired  = calls & outputs
```

Note `.get()`. **Session items are TypedDicts, not objects** — `hasattr(item, "call_id")` is
`False` for every one of them, and code that uses attribute access here does not crash. It
silently matches nothing and returns the list unchanged, which is the worst behaviour
available: a guard that appears to work.

### 🔮 Predict, then run

The spike prints two columns: `orphans?` and `legal?`. You have just written the code that
guarantees the first column says `no`. What will the second column say?

<details>
<summary>The real output</summary>

```
    budget  kept  tokens              first item  orphans?  legal?
  ------------------------------------------------------------------
      2000    22    1195                    user        no     yes
      1000    17     926               assistant        no      NO
       600     9     491               assistant        no      NO
       400     5     275               assistant        no      NO
       200     3     186           function_call        no      NO
       100     1      73               assistant        no      NO
```

**Five of six windows are orphan-free and illegal.**

`drop_orphans` is correct and insufficient. A window that opens on an assistant message
followed by a `function_call` is rejected:

```
400 INVALID_ARGUMENT
"Please ensure that function call turn comes immediately after a user turn
 or after a function response turn."
```

This chapter's author found that by running `filter_demo.py` PART 3, not by thinking about
it — and the fix is one more rule: advance the window until it opens on a user message.

> **Pairing is necessary and not sufficient.** A conversation is not a bag of items that
> reference each other; it is a sequence with legal start positions. Guarding one invariant
> does not make a request valid. It makes one specific failure impossible, which is a much
> smaller claim than it sounds like.

</details>

### 🔨 Practice 3 (20 min)

Add `align_to_turn_start` to the spike yourself — five lines — and re-run until the `legal?`
column is `yes` everywhere.

Then find the case it still gets wrong: **what happens when the budget is smaller than the
single most recent user message?**

**You're done when** every budget from 50 to 1400 yields a window that is orphan-free, opens
on a user message, and either fits the budget or is empty — and you can say which of those
three the function gives up first, and why that is the right one to give up.

---

## §4 — What the spike lost `[core]` · 20 min

Go back to §1's output and read case B's answer again:

```
  B. the same window, orphans dropped
    ACCEPTED -> You have packed a pair of hiking boots so far.
```

The trim succeeded. The request was legal. **The answer is wrong.**

The conversation packed two t-shirts, jeans, a jacket *and* hiking boots. Only the boots
survived the window, so only the boots were in the answer — delivered with no hedge, no
qualification, and nothing in the response to suggest anything was missing.

### The shape of the loss is not random

A tail window keeps the newest items. But look at where information actually sits in a
conversation:

| Position | What is usually there |
|---|---|
| **Turn 1** | what the user wants, constraints, the deadline, the budget, the destination |
| middle | working, tool calls, corrections |
| **latest turn** | "ok" |

**A tail window throws away precisely the end that matters.** It is not a compromise between
cost and fidelity; on this axis it is the worst available strategy, and it is the only one
the SDK ships.

### 🔨 Practice 4 (15 min)

Take any conversation you have had with an AI assistant that ran past ten turns. Write down
the three facts from it that would break the conversation if they vanished.

Now find where they were said.

**You're done when** you can state what fraction of your load-bearing facts were in the
first two turns — and you have an opinion about `limit=N` that you can defend.

---

## §5 — 🚀 The seam `[core]` · 35 min

Chapter 4 gave you one knob. The SDK has a much better one, and Chapter 4 never mentioned it:

```python
from agents import RunConfig
from agents.run_config import CallModelData, ModelInputData

def my_filter(data: CallModelData[Any]) -> ModelInputData:
    return ModelInputData(
        input=trim_to_budget(data.model_data.input, 3000),
        instructions=data.model_data.instructions,
    )

result = await Runner.run(agent, prompt, run_config=RunConfig(call_model_input_filter=my_filter))
```

`call_model_input_filter` receives the exact list about to go to the model and returns a
possibly-modified one. It may be `async`, so it may itself call a model. **This is where all
context management lives.**

Two things about it are not obvious.

### It has two fields, and everyone forgets the second

`ModelInputData` is `input` **and** `instructions`. The item list is not the only thing you
can change on the way out, and §6 depends on that.

### It fires per model call, not per turn

```
PART 2 - how often does the filter actually fire?

  Predict before reading: ONE user message that needs two tool calls.
  How many times does call_model_input_filter run?

  agent: I have packed both your raincoat and your book.

  the filter fired 3 times, seeing [1, 3, 5] items
```

One user message. **Three invocations**, seeing a growing list each time, because a turn
that calls two tools is three round trips to the model.

Anything expensive you put in this function is charged per model call. §6 walks into that
trap on purpose.

### Filter, never rebuild

```python
return [i for i in items if ...]         # good: same objects, filtered
return [{"role": i["role"], ...} for i in items]   # a live 400 waiting to happen
```

Stored `function_call` items carry provider state you did not put there:

```json
{
  "type": "function_call", "name": "add_item", "call_id": "call_3681811",
  "provider_data": {
    "thought_signature": "El4KXAERTTIPbS2gQjLy029MNKzccbX0YfvDUUozY2On..."
  }
}
```

Gemini 3.x requires that signature back when the call is replayed. The SDK stores and
restores it for you. A trimmer that constructs equal-looking dicts drops it and earns:

```
400  "Function call is missing a thought_signature in functionCall parts."
```

Which mentions neither trimming nor tokens. This is why `test_trim.py` asserts **identity**:

```python
assert all(a is b for a, b in zip(window, items, strict=True))
```

Not "equal" — *the same object*. It is a strange-looking assertion and it is the one that
protects you from a class of bug you cannot see.

### 🔨 Practice 5 (20 min)

Run `filter_demo.py` PART 3 and read the `in->sent` column:

```
  turn 1  stored=  6  in->sent  1->1 3->3 5->5
  turn 2  stored= 10  in->sent  7->7 9->3
  turn 3  stored= 14  in->sent  11->5 13->7
  turn 4  stored= 18  in->sent  15->5 17->7
           You have packed two t-shirts, jeans, and a jacket.
```

**You're done when** you can explain why `stored` only ever rises while the number after
`->` goes both up and down — and why that means trimming is not deletion.

---

## §5b — `ToolOutputTrimmer`: the other growth curve `[depth]` · 25 min

The SDK ships a filter you do not have to write:

```python
from agents.extensions import ToolOutputTrimmer

RunConfig(call_model_input_filter=ToolOutputTrimmer(
    recent_turns=2, max_output_chars=500, preview_chars=200,
    trimmable_tools={"search", "execute_code"},
))
```

It solves a **different** problem from this chapter's. Transcript length grows with *turns*;
tool output size grows with *one call to a chatty tool*. An agent with a web-search tool can
blow its budget in a single turn without having a long conversation at all.

### 🔨 Practice 5b (20 min)

Give the packing agent a tool that returns 5,000 characters of junk. Measure the transcript
before and after adding `ToolOutputTrimmer`.

**You're done when** you can name a situation where `ToolOutputTrimmer` alone is sufficient
and compaction is unnecessary — and one where it is the reverse.

---

## §6 — Compaction: summarise the head `[core]` · 45 min

§4 established the problem: the tail window deletes the end of the conversation that carries
the goal. The fix is not to keep more; it is to **replace the head with a description of
itself**.

```powershell
uv run python 05_context_window/with_sdk/compaction_demo.py            # ~20 requests
uv run python 05_context_window/with_sdk/compaction_demo.py --trim     # the control
```

### The experiment

Turn 1 states two facts that live nowhere else — not in the context object, not returned by
any tool, never repeated. Eight turns of packing push them far outside a 600-token budget.
Turn 9 asks for them back.

```
COMPACTION
   turn  stored  est tok  summaries   answer
      1       6      318          0   I've packed two t-shirts for your trip to Sk
      3      14      752          1   I've added the fleece to your bag.
      6      26     1401          2   Added your sleeping bag.
      9      38     2029          4   You are flying to Skardu on Friday.

TAIL WINDOW (control)
      9      40     2166          0   I only have your allowance details, not your
```

Same agent, same budget, same nine turns. **Only the filter differs.**

> **The control is not padding.** Without it, "compaction worked" is a claim about one run of
> a non-deterministic system. Chapter 4 shipped a control that was contaminated by a shared
> context object and it was *convincing* — so the fact under test here is deliberately one
> that only the transcript can carry.

### Two design decisions worth arguing with

**1. The summary goes in `instructions`, not into the item list.**

Injecting it as an item means inventing a turn nobody took — a `user` message the user never
sent, or an `assistant` message it never said. The model will quote invented turns back at
you. `instructions` is the field that already means *"true, but not spoken in this
conversation"*.

**2. The summary is cached — and the first cache did not work.**

```
before hysteresis:   9 turns -> 13 summarisation calls
after  hysteresis:   9 turns ->  4 summarisation calls
```

Thirteen extra model calls for a nine-turn conversation. **Staying under budget cost more
than going over it would have.** The cause is §5's own measurement — the filter fires per
model call — combined with one line of arithmetic:

```python
if tokens(items[covered:]) > budget * keep:   # trigger
    ...cut the tail back to budget * keep      # target
```

The trigger and the target were the same number, so the very next call crossed it again.

> **A cache whose invalidation condition is also its reset condition is not a cache.**

The fix is hysteresis: fold when the tail passes the **full** budget, and cut back to
**half** of it. The gap between those two numbers is the entire difference between
compaction as an optimisation and compaction as an expense.

### 🔨 Practice 6 (25 min)

Open `compaction.py` and set `keep=1.0`, so the trigger and the target coincide again. Run
the demo and count the folds.

**You're done when** you can predict the fold count for `keep=0.25`, `0.5` and `0.9` before
running, and your predictions are ordered correctly.

---

## §6b — Cheaper summarisers, and the arithmetic `[depth]` · 30 min

The summariser is an `Agent`. It does not have to be the same model as the main agent, and
usually should not be.

Work out, for your own numbers: at what conversation length does compaction start saving
money? Include the fold calls, the summary tokens re-sent on every subsequent request, and
the tokens you avoided.

**You're done when** you have a break-even turn count and can say what would have to change
to halve it.

---

## §6c — Composing filters, and ordering hazards `[depth]` · 30 min

`call_model_input_filter` takes **one** callable. Two behaviours means composing them
yourself, and order matters:

- trim-then-compact summarises a head that has already been cut — you summarise what you
  were about to throw away, which is either exactly right or completely pointless depending
  on which part got cut
- compact-then-trim can trim away the tail that the summary was written to complement

**You're done when** you have written a `compose(*filters)` helper, used it, and can name
one ordering that produces a legal request whose content is nonsense.

---

## §7 — What a summary costs you `[core]` · 20 min

This is the chapter's honest-limitation section, and it belongs to a family that now runs
four chapters deep.

| | The rule | What it still cannot stop |
|---|---|---|
| Ch2 §7b | a type stops a bad value being **accepted** | the model **fabricating** a good one |
| Ch3 §8 | a schema stops a bad answer being **hidden** | a **well-formed false** one |
| Ch4 §8 | a session stops context being **lost** | the model **reciting** a fact that has since changed |
| **Ch5 §7** | compaction stops the context **overflowing** | the summary being **confidently incomplete** |

### The finding that changed this section

The spec for this chapter predicted that compaction's danger was *"the agent forgets and does
not know it forgot"*. Running the control showed that is only half true, and the wrong half.

Read the two failures side by side:

```
TAIL WINDOW   "I only have your allowance details, not your travel details."
COMPACTION    "You are flying to Skardu on Friday."
```

The tail window **failed loudly**. It had a hole where turn 1 used to be, it noticed, and it
said so. That is a good failure: the user learns immediately that the agent lost something.

Compaction succeeded here. But consider what happens when the summariser omits something —
and it will, because 120 words cannot hold nine turns:

**There is no hole.** The summary reads as a complete account of the earlier conversation.
The agent has no way to distinguish "this was not important enough to summarise" from "this
never happened", so it answers from the summary with exactly the confidence it would have had
from the transcript.

> **Deletion leaves a gap the agent can feel. Summarisation fills the gap with something
> plausible.** That is why compaction is the better strategy *and* the more dangerous one.

### 🔨 Practice 7 (15 min)

Run the demo, then read the summary it printed:

```
- User flies to Skardu on Friday.
- Bag contents: two t-shirts (0.2 kg each), pair of jeans (0.8 kg), fleece (0.5 kg),
  hiking boots (1.5 kg), down jacket (1.1 kg), sleeping bag (1.8 kg), water filter (0.3 kg).
- Total bag weight: 6.4 kg.
- User requested remaining weight allowance.
```

Now find something in the original nine turns that is **not** in those four lines. Then write
one question whose correct answer needs the missing detail, and ask the agent.

**You're done when** you have an answer that is confident and wrong, and you can say which
layer should own the fix — a type, a schema, a cross-check, or a prompt.

> Ch3 taught the division of labour and it still holds: *a type makes a failure impossible to
> express, a schema makes it impossible to hide, a cross-check makes it impossible to ship,
> and a prompt does none of the three.* Ask which one a lossy summary needs. The answer is
> uncomfortable, and it is Chapter 6's subject.

---

## What this chapter cannot do — the hook for Chapter 6

You now have an agent that survives a long conversation, stays inside a budget you chose, and
keeps the goal from turn 1 alive through a compaction fold.

**You have no way to know whether the summary was any good.**

Every check in this chapter is structural — did the window orphan a pair, did it open on a
user message, did it fit the budget. Those are worth having and they are all *free*, which is
exactly why they were easy to write. Not one of them looks at the content.

The question §7 ends on — *"is this summary missing something that matters?"* — cannot be
answered by a type, a schema, or an assertion about item counts. It needs a judgement, made
repeatedly, against examples you have decided are correct.

**Chapter 6 — Evals** is how you make a judgement into a test.

---

## 🔁 Spendly Transfer

See `PROJECT.md`. In short: real Spendly conversations run for weeks, not turns, and a
WhatsApp thread has no natural end. Measure your real p95 transcript length first — Chapter 4
asked you to start logging it — then pick a budget from that number rather than from this
chapter's demo.
