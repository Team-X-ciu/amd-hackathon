"""Code checks on Gemma's output. Any problem -> the reply is discarded and the template is used.

The prompt asks Gemma to follow these rules; this file makes sure it did.
"""

from __future__ import annotations

import re

from app.llm import LLMOutput


def check_prefix(out: LLMOutput, facts: dict) -> str | None:
    """recommended_action must start with the decided action, e.g. 'reject: '."""
    expected = f"{facts['action']}: "
    if not out.recommended_action.strip().lower().startswith(expected):
        return f"recommended_action does not start with {expected!r}"
    return None


def check_no_stop_line(out: LLMOutput, facts: dict) -> str | None:
    text = " ".join([out.summary, out.recommended_action, out.answer or ""]).lower()
    orders_stop = ("stop the line" in text) or ( "stop line" in text)      # the second phrase from the TODO
    if orders_stop and "qc-6.1" not in text:                            # the section ID that makes it a quote, lowercase
        return "reply tells the operator to stop the line"
    return None
    
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def check_numbers(out: LLMOutput, facts: dict) -> str | None:
    allowed = set(_NUMBER.findall(str(facts)))       # every number written anywhere in the facts
    text = " ".join(t for t in (out.summary, out.recommended_action, out.answer or ""))
    for num in _NUMBER.findall(text):                                  # all numbers in Gemma's text
        if num not in allowed:
            return f"number {num} is not in the facts"
    return None


def problems(out: LLMOutput, facts: dict) -> list[str]:
    """All problems found; an empty list means the reply can be shown."""
    results = [check(out, facts) for check in (check_prefix, check_no_stop_line, check_numbers)]
    return [r for r in results if r]
