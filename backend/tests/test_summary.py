import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import summary  # noqa: E402
from anomalies import find_outliers  # noqa: E402
from profiler import profile_dataset  # noqa: E402

FRAME = pd.DataFrame({
    "region": ["N", "S", None, "N", "S", "N"],
    "amount": [10.0, 12.0, 11.0, 13.0, 14.0, 15.0],  # all different, so no duplicate rows
})


class FakeLLM:
    def __init__(self, reply="5. Suggested Checks\nCheck regions.\n\n6. Possible Next Analysis\nTry amount by region."):
        self.reply, self.prompts = reply, []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.reply


def build(monkeypatch, frame=FRAME, reply=None):
    fake = FakeLLM(*([reply] if reply else []))
    monkeypatch.setattr(summary, "ask_llm", fake)
    return summary.generate_executive_summary(profile_dataset(frame), find_outliers(frame)), fake


def test_facts_are_written_by_python_from_the_profile(monkeypatch):
    text, _ = build(monkeypatch)
    assert "The file contains 6 rows and 2 columns, with 1 empty cells in total." in text
    assert "region: 1 empty (16.67% of rows)." in text
    assert "No row repeats an earlier row." in text


def test_facts_come_before_the_ai_advice(monkeypatch):
    text, _ = build(monkeypatch)
    positions = [text.index(h) for h in ("1. Dataset Overview", "2. Data Completeness",
                                         "3. Duplicate Records", "4. Unusual Values",
                                         "5. Suggested Checks", "6. Possible Next Analysis")]
    assert positions == sorted(positions)


def test_a_complete_file_is_described_as_complete(monkeypatch):
    text, _ = build(monkeypatch, FRAME.fillna("X"))
    assert "Every column is fully populated." in text


def test_duplicates_and_outliers_are_reported(monkeypatch):
    frame = pd.DataFrame({"v": [10.0] * 30 + [10.0, 5000.0]})
    text, _ = build(monkeypatch, frame)
    assert "repeat an earlier row exactly" in text
    assert "Unusually distant values were found in: v." in text


def test_gemini_sees_column_names_and_types_but_no_values(monkeypatch):
    frame = pd.DataFrame({"customer": ["Alice Secret", "Bob Hidden"], "spend": [123.45, 678.9]})
    _, fake = build(monkeypatch, frame)
    prompt = fake.prompts[0]
    assert "- customer (text)" in prompt and "- spend (numeric)" in prompt
    for leaked in ("Alice Secret", "Bob Hidden", "123.45", "678.9"):
        assert leaked not in prompt


def test_the_ai_reply_is_appended_unchanged_except_for_whitespace(monkeypatch):
    text, _ = build(monkeypatch, reply="  5. Suggested Checks\nOnly this.  \n")
    assert text.endswith("5. Suggested Checks\nOnly this.")
