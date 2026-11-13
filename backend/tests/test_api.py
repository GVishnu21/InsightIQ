"""API tests. Gemini is replaced by fakes, so these run offline and instantly."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import interpreter  # noqa: E402
import main  # noqa: E402
import sql_agent  # noqa: E402

client = TestClient(main.app)

CSV = b"region,sales\nNorth,10\nSouth,20\nNorth,5\n"
GROUPED_SQL = "SELECT region, SUM(sales) AS total FROM uploaded_data GROUP BY region ORDER BY total DESC"


def upload(content=CSV, name="data.csv"):
    return client.post("/datasets", files={"file": (name, content, "text/csv")})


def new_dataset_id():
    return upload().json()["dataset_id"]


def ask(dataset_id, question="a question"):
    return client.post(f"/datasets/{dataset_id}/ask", json={"question": question})


def fake_gemini(monkeypatch, sql, explanation="South had the most sales with 20."):
    """Fake Gemini: SQL prompts get `sql`, explanation prompts get `explanation`."""
    def answer(prompt):
        return explanation if "You explain database query results" in prompt else sql

    monkeypatch.setattr(sql_agent, "ask_llm", answer)
    monkeypatch.setattr(interpreter, "ask_llm", answer)


def test_health_check():
    assert client.get("/health").json() == {"status": "ok"}


# ------------------------------------------------------------------ upload

def test_upload_returns_201_with_dataset_id_and_profile():
    response = upload()
    assert response.status_code == 201
    body = response.json()
    assert body["dataset_id"]
    assert body["profile"]["rows"] == 3 and body["profile"]["columns"] == 2
    assert body["preview"][0] == {"region": "North", "sales": 10}


def test_uppercase_extension_is_accepted():
    assert upload(name="DATA.CSV").status_code == 201


def test_wrong_extension_is_400():
    assert upload(name="data.txt").status_code == 400


def test_too_large_is_413(monkeypatch):
    monkeypatch.setattr(main.config, "MAX_UPLOAD_MB", 0)  # any content is now too big
    assert upload().status_code == 413


@pytest.mark.parametrize("content", [b"", b"   \n", b"a,b\n"])
def test_empty_or_headers_only_is_422(content):
    assert upload(content).status_code == 422


def test_windows_1252_encoding_is_handled():
    response = upload("name,city\nJosé,Málaga\n".encode("cp1252"))
    assert response.status_code == 201
    assert response.json()["preview"][0]["name"] == "José"


def test_numeric_headers_are_converted_to_text():
    response = upload(b"1,2\n3,4\n5,6\n")
    assert response.status_code == 201
    assert list(response.json()["preview"][0]) == ["1", "2"]


# ----------------------------------------------------------------- lookups

def test_unknown_dataset_is_404_for_summary_and_ask():
    assert client.post("/datasets/nope/summary").status_code == 404
    assert ask("nope").status_code == 404


def test_blank_question_is_422():
    assert ask(new_dataset_id(), "   ").status_code == 422


def test_overlong_question_is_422():
    assert ask(new_dataset_id(), "x" * 501).status_code == 422


# --------------------------------------------------------------------- ask

def test_ask_returns_verified_explanation_sql_and_rows(monkeypatch):
    fake_gemini(monkeypatch, GROUPED_SQL)
    response = ask(new_dataset_id(), "which region sells most?")

    assert response.status_code == 200
    body = response.json()
    assert body["explanation"] == "South had the most sales with 20."
    assert body["explanation_verified"] is True
    assert body["columns"] == ["region", "total"]
    assert body["results"][0] == {"region": "South", "total": 20}
    assert body["row_count"] == 2 and body["truncated"] is False and body["attempts"] == 1
    assert "SUM(sales)" in body["sql"]


def test_ask_replaces_an_invented_number_with_the_safe_fallback(monkeypatch):
    fake_gemini(monkeypatch, GROUPED_SQL, explanation="South sold 9,999 units.")
    body = ask(new_dataset_id()).json()

    assert body["explanation_verified"] is False
    assert "9,999" not in body["explanation"]
    assert body["results"][0]["total"] == 20  # real numbers still come from DuckDB


def test_ask_blocked_sql_is_422_and_returns_the_sql(monkeypatch):
    fake_gemini(monkeypatch, "DROP TABLE uploaded_data", "irrelevant")
    response = ask(new_dataset_id())

    assert response.status_code == 422
    assert "blocked" in response.json()["detail"]["message"]
    assert response.json()["detail"]["sql"] == "DROP TABLE uploaded_data"


def test_ask_gemini_failure_is_502_without_leaking_details(monkeypatch):
    def boom(prompt):
        raise ConnectionError("secret internal detail")

    monkeypatch.setattr(sql_agent, "ask_llm", boom)
    response = ask(new_dataset_id())

    assert response.status_code == 502
    assert "secret" not in response.text


def test_ask_missing_api_key_is_503(monkeypatch):
    def no_key(prompt):
        raise RuntimeError("GEMINI_API_KEY is not set.")

    monkeypatch.setattr(sql_agent, "ask_llm", no_key)
    response = ask(new_dataset_id())

    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_ask_still_answers_when_only_the_explanation_call_fails(monkeypatch):
    def explanation_fails(prompt):
        raise ConnectionError("down")

    monkeypatch.setattr(sql_agent, "ask_llm", lambda prompt: GROUPED_SQL)
    monkeypatch.setattr(interpreter, "ask_llm", explanation_fails)
    response = ask(new_dataset_id())

    assert response.status_code == 200 and response.json()["explanation_verified"] is False


def test_ask_includes_a_chart_for_grouped_results_and_none_for_a_single_value(monkeypatch):
    dataset_id = new_dataset_id()

    fake_gemini(monkeypatch, GROUPED_SQL)
    chart = ask(dataset_id, "sales by region").json()["chart"]
    assert chart["type"] == "bar"
    assert chart["figure"]["data"][0]["x"] == ["South", "North"]
    assert chart["figure"]["data"][0]["y"] == [20, 15]

    fake_gemini(monkeypatch, "SELECT SUM(sales) AS total FROM uploaded_data", "Total sales were 35.")
    body = ask(dataset_id, "total sales").json()
    assert body["chart"] is None and body["results"] == [{"total": 35}]


# ----------------------------------------------------------------- summary

def test_summary_uses_the_stored_dataset(monkeypatch):
    monkeypatch.setattr(main, "generate_executive_summary", lambda profile, outliers: f"rows={profile['rows']}")
    response = client.post(f"/datasets/{new_dataset_id()}/summary")

    assert response.status_code == 200
    assert response.json() == {"filename": "data.csv", "summary": "rows=3"}


def test_summary_gemini_failure_is_502(monkeypatch):
    def boom(profile, outliers):
        raise ConnectionError("secret")

    monkeypatch.setattr(main, "generate_executive_summary", boom)
    response = client.post(f"/datasets/{new_dataset_id()}/summary")

    assert response.status_code == 502 and "secret" not in response.text
