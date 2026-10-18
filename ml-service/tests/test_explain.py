"""explain_with_llm with a fake Gemma: a good reply is used, anything bad falls back to the template.

Code-owned fields (priority, sources, needs_human_review, action prefix) must never depend on the LLM.
"""

import pytest

from app import config, explain, llm
from app.llm import LLMOutput
from app.qc_rules import decide

TYPES = ["bent", "melt", "scratch", "missing", "unknown"]
SEVERITIES = ["low", "medium", "high"]


@pytest.fixture(autouse=True)
def fake_model_name(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", "fake-gemma")


def use_reply(monkeypatch, make):
    """make(facts) -> LLMOutput, or an Exception instance to raise."""
    def fake_rewrite(facts, question=None, history=None):
        if isinstance(make, Exception):
            raise make
        return make(facts)
    monkeypatch.setattr(llm, "rewrite", fake_rewrite)


def good(facts):
    return LLMOutput(summary="Defect found on the board.",
                     recommended_action=f"{facts['action']}: follow the cited section.",
                     answer="See the cited section.")


def run(t="melt", s="high", q=None):
    return explain.explain_with_llm(t, s, 0.023, question=q)


def test_good_reply_is_used(monkeypatch):
    use_reply(monkeypatch, good)
    r = run()
    assert r["model"] == "fake-gemma"
    assert r["summary"] == "Defect found on the board."


def test_good_reply_keeps_code_owned_fields(monkeypatch):
    template = explain.build_explanation("melt", "high", 0.023)
    use_reply(monkeypatch, good)
    r = run()
    for key in ("priority", "sources", "likely_causes", "needs_human_review"):
        assert r[key] == template[key], key


def test_wrong_prefix_falls_back(monkeypatch):
    def wrong(facts):
        other = "accept" if facts["action"] != "accept" else "reject"
        return LLMOutput(summary="Fine.", recommended_action=f"{other}: ship it.", answer=None)
    use_reply(monkeypatch, wrong)
    assert run()["model"] == "template"


def test_invented_number_falls_back(monkeypatch):
    use_reply(monkeypatch, lambda f: LLMOutput(summary="About 87% is melted.",
                                               recommended_action=f"{f['action']}: check it.", answer=None))
    assert run()["model"] == "template"


def test_stop_line_falls_back(monkeypatch):
    use_reply(monkeypatch, lambda f: LLMOutput(summary="Stop the line.",
                                               recommended_action=f"{f['action']}: check it.", answer=None))
    assert run()["model"] == "template"


def test_llm_exception_falls_back(monkeypatch):
    use_reply(monkeypatch, TimeoutError("Gemma took too long"))
    r = run()
    assert r["model"] == "template"
    assert r["recommended_action"].startswith(f"{decide('melt', 'high').action}: ")


def test_unknown_needs_human_review(monkeypatch):
    use_reply(monkeypatch, good)
    r = run("unknown", "medium")
    assert r["needs_human_review"] is True
    assert r["recommended_action"].startswith("review: ")


def test_answer_dropped_without_question(monkeypatch):
    use_reply(monkeypatch, good)
    assert run(q=None)["answer"] is None


def test_answer_used_with_question(monkeypatch):
    use_reply(monkeypatch, good)
    assert run(q="Why reject?")["answer"] == "See the cited section."


@pytest.mark.parametrize("t", TYPES)
@pytest.mark.parametrize("s", SEVERITIES)
@pytest.mark.parametrize("mode", ["good", "fail"])
def test_prefix_always_matches_table(monkeypatch, t, s, mode):
    use_reply(monkeypatch, good if mode == "good" else RuntimeError("down"))
    r = explain.explain_with_llm(t, s, 0.01)
    assert r["recommended_action"].startswith(f"{decide(t, s).action}: ")
    assert r["priority"] in {"low", "medium", "high"}  # never stop_line
