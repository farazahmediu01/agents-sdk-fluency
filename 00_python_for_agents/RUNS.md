# Chapter 0 — Run Log

Dated evidence for Chapter 0. Each entry has the actual command output, not a summary of it.

Environment: Windows 11, Python via `uv`, pyright 1.1.411.

---

## 2026-10-11 — Practice 1: break it on purpose (`examples/foundations.py`)

### Run 1 — baseline, original file

```
uv run python 00_python_for_agents/examples/foundations.py    -> exit 0
uv run pyright 00_python_for_agents/examples/foundations.py   -> 0 errors, 0 warnings, 0 informations
```

### Run 2 — `print(found.upper())` (line 59) and `print(raw.upper())` (line 130) uncommented, `REGISTRY` typed `Callable[[float, float], float]`

```
uv run python 00_python_for_agents/examples/foundations.py    -> exit 0 (runs, no crash)
uv run pyright 00_python_for_agents/examples/foundations.py   -> 4 errors
```

| Line | Rule | What it means |
|---|---|---|
| 59:17 | `reportOptionalMemberAccess` | `"upper" is not a known attribute of "None"`. `find_user_message` can return `None`, and the caller didn't handle it. This is Practice 1, step 1. |
| 113:25 | `reportCallIssue` | `Expected 2 more positional arguments`. `function(**args)` passes `a=`/`b=` by name, but the positional `Callable` type has no parameter names. This is Practice 1, step 3. |
| 130:35 | pyright directive | Not a type error. The trailing comment `# pyright: "upper" is not...` was parsed as a pyright directive. The comment has to be reworded before the real `object` error on that line can be seen. |
| 130:44 | pyright directive | Same cause. |

> **Correction (2026-10-12):** the line-130 demo had a second defect. `raw: object = "..."` is narrowed to `str` by pyright at the assignment, so `raw.upper()` produced **no** pyright error at all; the `"object" has no attribute` message came from the editor's Mypy. Fixed in `foundations.py`: `raw` now comes from `load_setting() -> object`, which pyright cannot narrow. Verified that uncommenting line 137 now gives `Cannot access attribute "upper" for class "object"`.

Editor note: a diagnostic from the editor (Mypy, not Pyright) reported `"object" has no attribute "upper"` on line 130. The message wording differs by tool; the catch is the same.

---

## Decisions

- **Step 2 — which fix for `found.upper()`:** `if found is not None:` (option a). Option b (`return ""`) hides "no user message" as an empty string, so the caller can't tell it apart from a user who sent nothing. Option c (`assert`) crashes the program and is removed entirely under `python -O`; it's for conditions that should be impossible if the code is correct, not for input that can be absent.
- **Step 3 — why `...` for `REGISTRY`:** `Callable[..., float]` is right for a registry dispatched with `function(**args)`, because the argument names come from outside the code (in Chapter 1, from the model). `Callable[[float, float], float]` describes unnamed positional parameters and rejects that call. The trade-off is that `...` gives up argument checking at that line, and Chapter 2 restores it at the boundary with Pydantic.

### Run 3 — restored file (`REGISTRY` back to `...`, line-130 comment reworded, `print` lines commented out)

```
uv run python 00_python_for_agents/examples/foundations.py    -> exit 0
uv run pyright 00_python_for_agents/examples/foundations.py   -> 0 errors, 0 warnings, 0 informations
```

---

## Status

- **Practice 1: done.** Steps 1–3 answered, the break-and-fix cycle run with real output, and the file is back to a clean state (Run 3).
- Next: Chapter 0 Practice 2 (`@retry` and `@count_calls`).

