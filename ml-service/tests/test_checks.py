"""Unit tests for app/checks.py: each check alone, then problems() as a whole."""

from app.checks import check_no_stop_line, check_numbers, check_prefix, problems
from app.llm import LLMOutput

FACTS = {
    "action": "reject",
    "severity": "high",
    "area_percent": 2.3,
    "cited_sections": [{"section": "QC-2.3", "snippet": "Melted area: reject."}],
}


def reply(summary="Melted area on the board.", action="reject: check the solder joints.", answer=None):
    return LLMOutput(summary=summary, recommended_action=action, answer=answer)


def test_good_reply_has_no_problems():
    assert problems(reply(), FACTS) == []


def test_prefix_wrong_action_fails():
    assert check_prefix(reply(action="accept: looks fine."), FACTS)


def test_prefix_without_colon_fails():
    assert check_prefix(reply(action="reject the board."), FACTS)


def test_prefix_is_case_insensitive():
    assert check_prefix(reply(action="Reject: check the joints."), FACTS) is None


def test_stop_line_order_fails():
    assert check_no_stop_line(reply(summary="Stop the line now."), FACTS)


def test_stop_line_in_answer_fails():
    assert check_no_stop_line(reply(answer="You should stop line PCB1."), FACTS)


def test_stop_line_quoting_qc61_passes_known_gap():
    # Known limitation (README): the check is string-based, so an order that cites QC-6.1 passes.
    assert check_no_stop_line(reply(summary="Stop the line as in QC-6.1."), FACTS) is None


def test_invented_number_fails():
    assert check_numbers(reply(summary="About 7.5% of the board is melted."), FACTS)


def test_number_from_facts_passes():
    assert check_numbers(reply(summary="About 2.3% of the image is melted."), FACTS) is None


def test_invented_number_in_answer_fails():
    assert check_numbers(reply(answer="It takes 45 minutes to fix."), FACTS)


def test_problems_lists_every_failure():
    bad = reply(summary="Stop the line, 99 boards affected.", action="accept: fine.")
    assert len(problems(bad, FACTS)) == 3
