"""Pydantic models: the exact shape of what the API accepts and returns.

FastAPI uses them to reject malformed requests automatically (HTTP 422) and to
document every endpoint at /docs.
"""

from pydantic import BaseModel, Field, field_validator

MAX_QUESTION_LENGTH = 500


class QuestionRequest(BaseModel):
    question: str = Field(max_length=MAX_QUESTION_LENGTH)

    @field_validator("question")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be empty.")
        return value


class DatasetResponse(BaseModel):
    """Returned after an upload: the id to use from now on, plus the profile."""
    dataset_id: str
    filename: str
    preview: list[dict]
    profile: dict
    anomalies: list[dict]


class SummaryResponse(BaseModel):
    filename: str
    summary: str


class AnswerResponse(BaseModel):
    """Everything the UI needs to show one answer and how it was obtained."""
    question: str
    explanation: str
    explanation_verified: bool  # False = Python fallback text instead of AI text
    sql: str
    columns: list[str]
    results: list[dict]
    row_count: int              # rows the query returned (capped at 1000)
    truncated: bool             # True when `results` holds fewer rows than row_count
    attempts: int               # 2 = the first SQL failed and was corrected
    chart: dict | None = None   # {"type": ..., "figure": Plotly JSON} or None
