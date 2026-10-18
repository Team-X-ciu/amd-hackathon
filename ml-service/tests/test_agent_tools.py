"""Tool-using chat (AGENT_TOOLS=1) with a fake Gemma and a fake backend.

At most one tool call; an unknown tool or a failing tool means answering without it; the tool result
joins the facts, so the number check accepts its figures and still rejects invented ones.
"""

import io
import json

import pytest

from app import config, explain, llm, tools
from app.llm import LLMOutput, ToolRequest

TOOL_RESULT = {
    "tool": "recent_inspections",
    "defect_type": "melt",
    "count": 7,
    "severities": {"high": 7},
    "accepted": 0,
    "reworked": 2,
    "rejected": 5,
    "undecided": 0,
}


@pytest.fixture(autouse=True)
def agent_on(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", "fake-gemma")
    monkeypatch.setattr(config, "AGENT_TOOLS", True)


def answer(text):
    def make(facts, question=None, history=None):
        make.facts = dict(facts)
        return LLMOutput(
            summary="Defect found on the board.",
            recommended_action=f"{facts['action']}: follow the cited section.",
            answer=text,
        )

    return make


def first_turn(reply):
    calls = []

    def fake(facts, question, history=None):
        calls.append(question)
        return reply

    fake.calls = calls
    return fake


def run(q="How were recent melt boards handled?"):
    return explain.explain_with_llm("melt", "high", 0.023, question=q)


def test_tool_requested_result_used(monkeypatch):
    monkeypatch.setattr(
        llm,
        "chat_turn",
        first_turn(ToolRequest(tool="recent_inspections", args={"defect_type": "melt", "limit": 7})),
    )
    seen = {}
    monkeypatch.setitem(tools.TOOLS, "recent_inspections", lambda **a: seen.update(a) or TOOL_RESULT)
    second = answer("5 of the last 7 melt boards were rejected and 2 reworked.")
    monkeypatch.setattr(llm, "rewrite", second)
    r = run()
    assert seen == {"defect_type": "melt", "limit": 7}
    assert second.facts["tool_result"] == TOOL_RESULT
    assert r["model"] == "fake-gemma"  # numbers from the tool passed the check
    assert r["answer"].startswith("5 of the last 7")


def test_direct_answer_needs_no_second_call(monkeypatch):
    monkeypatch.setattr(
        llm,
        "chat_turn",
        first_turn(
            LLMOutput(
                summary="Defect found.",
                recommended_action="reject: follow the cited section.",
                answer="See the cited section.",
            )
        ),
    )
    monkeypatch.setattr(llm, "rewrite", lambda *a, **k: pytest.fail("no second call expected"))
    assert run()["answer"] == "See the cited section."


def test_unknown_tool_ignored(monkeypatch):
    monkeypatch.setattr(llm, "chat_turn", first_turn(ToolRequest(tool="delete_all", args={})))
    second = answer("See the cited section.")
    monkeypatch.setattr(llm, "rewrite", second)
    r = run()
    assert "tool_result" not in second.facts
    assert r["model"] == "fake-gemma"


@pytest.mark.parametrize(
    "error", [TimeoutError("timed out"), OSError("connection refused"), KeyError("items")]
)
def test_tool_error_answers_without_it(monkeypatch, error):
    monkeypatch.setattr(
        llm, "chat_turn", first_turn(ToolRequest(tool="recent_inspections", args={"defect_type": "melt"}))
    )

    def broken(**_):
        raise error

    monkeypatch.setitem(tools.TOOLS, "recent_inspections", broken)
    second = answer("See the cited section.")
    monkeypatch.setattr(llm, "rewrite", second)
    r = run()
    assert "tool_result" not in second.facts
    assert r["model"] == "fake-gemma"


def test_tool_error_then_invented_number_falls_back_to_template(monkeypatch):
    monkeypatch.setattr(
        llm, "chat_turn", first_turn(ToolRequest(tool="recent_inspections", args={"defect_type": "melt"}))
    )
    monkeypatch.setitem(tools.TOOLS, "recent_inspections", lambda **_: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr(llm, "rewrite", answer("5 of the last 7 melt boards were rejected."))
    assert run()["model"] == "template"  # without the tool result those numbers are invented


def test_flag_off_or_first_explanation_never_offers_tools(monkeypatch):
    monkeypatch.setattr(llm, "chat_turn", lambda *a, **k: pytest.fail("tools must not be offered"))
    monkeypatch.setattr(llm, "rewrite", answer("See the cited section."))
    explain.explain_with_llm("melt", "high", 0.023, question=None)  # first explanation
    monkeypatch.setattr(config, "AGENT_TOOLS", False)
    run()  # chat with the flag off


def test_recent_inspections_summarises_backend_page(monkeypatch):
    page = {
        "items": [
            {"vision": {"severity": "high"}, "decision": {"decision": "reject"}},
            {"vision": {"severity": "high"}, "decision": {"decision": "rework"}},
            {"vision": {"severity": "medium"}, "decision": None},
        ]
    }
    urls = []

    def fake_urlopen(url, timeout):
        urls.append((url, timeout))
        return io.BytesIO(json.dumps(page).encode())

    monkeypatch.setattr(tools.urllib.request, "urlopen", fake_urlopen)
    s = tools.recent_inspections("melt", limit=50)
    assert urls == [(f"{config.BACKEND_URL}/api/inspections?defect_type=melt&limit=20", 3.0)]  # limit capped
    assert s["count"] == 3 and s["severities"] == {"high": 2, "medium": 1}
    assert (s["accepted"], s["reworked"], s["rejected"], s["undecided"]) == (0, 1, 1, 1)


def test_recent_inspections_rejects_unknown_defect_type():
    assert tools.run_tool("recent_inspections", {"defect_type": "crack"}) is None
