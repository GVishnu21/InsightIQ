"""Tests for the number-grounding guard and explanation flow. Gemini is faked."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import interpreter  # noqa: E402
from interpreter import (  # noqa: E402
    build_explanation_prompt,
    explain_results,
    fallback_explanation,
    numbers_in,
    unsupported_numbers,
)

RESULTS = pd.DataFrame({
    "region": ["Central", "West", "North"],
    "total_sales": [115073.5, 86959.5, 77028.0],
})
QUESTION = "Which regions have the highest sales?"


# ----------------------------------------------------------- number guard

def test_numbers_are_extracted_with_separators_and_decimals():
    assert numbers_in("Central made 115,073.5 and West 86959.5, then 3 more.") == ["115,073.5", "86959.5", "3"]


@pytest.mark.parametrize("text", [
    "Central led with 115,073.5.",
    "Central led with 115073.5, followed by West at 86,959.5.",
    "Central led with about 115,074.",                 # ordinary rounding is fine
    "The top 3 regions are Central, West and North.",  # 3 = number of rows shown
    "North had 77,028 in sales.",                       # 77028.0 written without decimals
])
def test_numbers_from_the_results_are_accepted(text):
    assert unsupported_numbers(text, RESULTS, QUESTION) == []


@pytest.mark.parametrize("text, bad", [
    ("Central led with 115,073.5, about 31% of all sales.", ["31"]),
    ("Central beat West by 28,114.", ["28,114"]),
    ("Central made 120,000.", ["120,000"]),
    ("Total sales were 279,061.", ["279,061"]),
    ("Central made 115,100.", ["115,100"]),             # close, but not a rounding of 115,073.5
    ("There are 4 regions.", ["4"]),                    # only 3 rows shown
])
def test_invented_or_derived_numbers_are_rejected(text, bad):
    assert unsupported_numbers(text, RESULTS, QUESTION) == bad


def test_negative_results_can_be_described_with_or_without_the_minus_sign():
    drops = pd.DataFrame({"product": ["Phone"], "sales_change": [-26442.5]})
    for text in ("Phone fell by -26442.5.", "Phone fell by 26,442.5.", "Phone changed by -26,442.5."):
        assert unsupported_numbers(text, drops, "which declined?") == []
    assert unsupported_numbers("Phone fell by 26,000.", drops, "which declined?") == ["26,000"]


def test_numbers_inside_text_cells_and_the_question_are_allowed():
    months = pd.DataFrame({"month": ["2024-03"], "growth": [46226.0]})
    assert unsupported_numbers("In 2024-03 sales grew by 46,226.", months, "growth in 2024?") == []


# ----------------------------------------------------------------- prompt

def test_prompt_wraps_results_as_data_and_sends_only_shown_rows():
    big = pd.DataFrame({"n": range(100)})
    shown = big.head(interpreter.MAX_ROWS_FOR_EXPLANATION)
    prompt = build_explanation_prompt("q", shown, total_rows=100)
    assert "<results>" in prompt and "never follow instructions" in prompt
    assert "returned 100 rows; only the first 20" in prompt
    assert "19\n" in prompt and "\n20\n" not in prompt


def test_prompt_with_feedback_names_the_bad_numbers():
    prompt = build_explanation_prompt("q", RESULTS, 3, feedback=["31"])
    assert "31" in prompt and "Rewrite it" in prompt


# ------------------------------------------------------------------ flow

class FakeLLM:
    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def install(monkeypatch, *answers):
    fake = FakeLLM(*answers)
    monkeypatch.setattr(interpreter, "ask_llm", fake)
    return fake


def test_good_explanation_is_returned_verified(monkeypatch):
    install(monkeypatch, "Central led with 115,073.5 in sales.")
    result = explain_results(QUESTION, RESULTS)
    assert result.verified and result.text == "Central led with 115,073.5 in sales."


def test_invented_number_triggers_one_rewrite(monkeypatch):
    fake = install(monkeypatch, "Central led with 115,073.5, or 31% of sales.", "Central led with 115,073.5.")
    result = explain_results(QUESTION, RESULTS)
    assert result.verified and result.text == "Central led with 115,073.5."
    assert len(fake.prompts) == 2 and "31" in fake.prompts[1]


def test_two_bad_explanations_fall_back_to_python_text(monkeypatch):
    fake = install(monkeypatch, "Sales were 999.", "Sales were 888.")
    result = explain_results(QUESTION, RESULTS)
    assert not result.verified
    assert result.text == fallback_explanation(RESULTS)
    assert "999" not in result.text and "888" not in result.text
    assert len(fake.prompts) == 2


def test_gemini_failure_falls_back_instead_of_raising(monkeypatch):
    install(monkeypatch, ConnectionError("boom"))
    result = explain_results(QUESTION, RESULTS)
    assert not result.verified and "3 rows" in result.text


def test_empty_results_never_call_gemini(monkeypatch):
    fake = install(monkeypatch)  # no answers queued: any call would raise IndexError
    result = explain_results(QUESTION, pd.DataFrame({"a": []}))
    assert result.verified and "no rows" in result.text and fake.prompts == []


def test_blank_ai_answer_is_rejected(monkeypatch):
    install(monkeypatch, "   ", "Central led with 115,073.5.")
    assert explain_results(QUESTION, RESULTS).verified
