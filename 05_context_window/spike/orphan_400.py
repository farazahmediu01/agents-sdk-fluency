"""
SPIKE -- disposable. Delete it once Chapter 5 validates.

Chapter 4 printed a table saying a tail window "can" start on a tool result
whose call was cut away, and that "some providers reject that". This sends two
windows so you stop taking our word for it:

    A  the orphaned window        -> expected: rejected
    B  the SAME window, repaired  -> expected: accepted

One variable, one difference in outcome. That is the whole experiment.

    uv run python 05_context_window/spike/orphan_400.py     # 2 requests

Transport layer only, no agent framework -- this is a `spike/`.
"""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from trim import drop_orphans

load_dotenv()
MODEL = os.environ.get("MODEL_NAME", "gemini-3.5-flash-lite")
TRANSCRIPT = Path(__file__).with_name("transcript.json")


def to_wire(items: list[dict[str, Any]], *, keep_provider_data: bool) -> list[Any]:
    """Stored session items -> Chat Completions messages. The SDK does this for you."""
    out: list[Any] = []
    for item in items:
        if item.get("type") == "function_call":
            call: dict[str, Any] = {
                "id": item["call_id"],
                "type": "function",
                "function": {"name": item["name"], "arguments": item["arguments"]},
            }
            signature = (item.get("provider_data") or {}).get("thought_signature")
            if keep_provider_data and signature:
                # Gemini 3.x REQUIRES this back on replay. The SDK stores it in
                # `provider_data` and restores it here; hand-built code forgets.
                call["extra_content"] = {"google": {"thought_signature": signature}}
            out.append({"role": "assistant", "tool_calls": [call]})
        elif item.get("type") == "function_call_output":
            out.append({"role": "tool", "tool_call_id": item["call_id"], "content": item["output"]})
        elif item.get("role") == "user":
            out.append({"role": "user", "content": item["content"]})
        elif item.get("role") == "assistant":
            out.append(
                {
                    "role": "assistant",
                    "content": "".join(p.get("text", "") for p in item.get("content", [])),
                }
            )
    return out


def send(label: str, items: list[dict[str, Any]], *, keep_provider_data: bool) -> None:
    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL")
    )
    first = str(items[0].get("role") or items[0].get("type")) if items else "-"
    print(f"\n  {label}\n    {len(items)} items, first = {first}")
    try:
        reply = client.chat.completions.create(
            model=MODEL, messages=to_wire(items, keep_provider_data=keep_provider_data)
        )
        answer = (reply.choices[0].message.content or "").strip().replace("\n", " ")
        print(f"    ACCEPTED -> {answer[:66]}")
    except Exception as exc:
        message = str(exc)
        detail = message.split("'message':", 1)[-1][:150].strip()
        print(f"    REJECTED -> {type(exc).__name__}: {detail}")


# Every window gets the same new question appended, because that is when a real
# trimmer runs: immediately before a model call, with the user's next message
# already on the end. A bare historical slice ends on an assistant turn, which
# Gemini rejects for a third unrelated reason -- worth seeing once (Practice 1b),
# but it would confound the comparison here.
NEXT_TURN = {"role": "user", "content": "In one sentence, what have I packed so far?"}


def main() -> None:
    items: list[dict[str, Any]] = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
    window = items[-6:]  # Chapter 4's table flagged this one: orphaned = YES
    repaired = drop_orphans(window)

    print(f"  Model: {MODEL}")
    send("A. the orphaned window", [*window, NEXT_TURN], keep_provider_data=True)
    send("B. the same window, orphans dropped", [*repaired, NEXT_TURN], keep_provider_data=True)

    print("\n  A failed and B succeeded -> the orphan was the cause, not the length.")


if __name__ == "__main__":
    main()
