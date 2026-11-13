"""InsightIQ API.

    POST /datasets                      upload a CSV, get a dataset id + profile
    POST /datasets/{id}/summary         AI-written executive summary
    POST /datasets/{id}/ask             a question answered with SQL, rows, chart and explanation
    GET  /health                        liveness check
"""

import logging
from contextlib import contextmanager
from io import StringIO

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import config
from anomalies import find_outliers
from charts import build_chart
from dataset_store import StoredDataset, store
from interpreter import explain_results
from profiler import profile_dataset
from schemas import AnswerResponse, DatasetResponse, QuestionRequest, SummaryResponse
from sql_agent import QueryFailed, answer_question
from summary import generate_executive_summary

log = logging.getLogger("insightiq")

PREVIEW_ROWS = 10
RESULT_ROWS_TO_CLIENT = 50
TEXT_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")  # Excel often saves as Windows-1252

app = FastAPI(title="InsightIQ API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ helpers

def decode_text(raw: bytes) -> str:
    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(422, "Could not decode the file as text.")


async def read_csv_upload(upload: UploadFile) -> pd.DataFrame:
    """Validate an uploaded file and return it as a DataFrame, or raise a clear HTTP error."""
    if not (upload.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are allowed.")

    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    raw = await upload.read(limit + 1)  # one byte past the limit is enough to know it is too big
    if len(raw) > limit:
        raise HTTPException(413, f"File is too large. The limit is {config.MAX_UPLOAD_MB} MB.")
    if not raw.strip():
        raise HTTPException(422, "The file is empty.")

    try:
        frame = pd.read_csv(StringIO(decode_text(raw)))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Could not read the file as a CSV.")

    if frame.empty or frame.columns.empty:
        raise HTTPException(422, "The CSV has no data rows.")

    frame.columns = frame.columns.astype(str)  # numeric headers would break SQL and JSON
    return frame


def find_dataset(dataset_id: str) -> StoredDataset:
    dataset = store.get(dataset_id)
    if dataset is None:
        raise HTTPException(404, "Dataset not found. Please upload the CSV again.")
    return dataset


@contextmanager
def translate_ai_errors():
    """Turn failures of AI-backed work into clean HTTP errors.

    Details are logged on the server only; the browser gets a generic message.
    """
    try:
        yield
    except (HTTPException, QueryFailed):
        raise  # already shaped for the client, or handled by the route
    except RuntimeError as exc:  # config.require_gemini_key(): the key is not configured
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        log.exception("AI request failed")
        raise HTTPException(502, "The AI service is unavailable right now. Please try again.") from exc


# ------------------------------------------------------------------- routes

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/datasets", response_model=DatasetResponse, status_code=201)
async def create_dataset(file: UploadFile = File(...)):
    frame = await read_csv_upload(file)
    dataset = store.add(frame, file.filename)

    return {
        "dataset_id": dataset.dataset_id,
        "filename": dataset.filename,
        "preview": frame.head(PREVIEW_ROWS).fillna("").to_dict(orient="records"),
        "profile": profile_dataset(frame),
        "anomalies": find_outliers(frame),
    }


# The two routes below are plain `def`, not `async def`, because they block on
# Gemini and DuckDB. FastAPI runs them in a thread pool so other requests are
# still served meanwhile.

@app.post("/datasets/{dataset_id}/summary", response_model=SummaryResponse)
def create_summary(dataset_id: str):
    dataset = find_dataset(dataset_id)

    with translate_ai_errors():
        text = generate_executive_summary(profile_dataset(dataset.df), find_outliers(dataset.df))

    return {"filename": dataset.filename, "summary": text}


@app.post("/datasets/{dataset_id}/ask", response_model=AnswerResponse)
def ask_question(dataset_id: str, request: QuestionRequest):
    dataset = find_dataset(dataset_id)

    with translate_ai_errors():
        try:
            outcome = answer_question(dataset.df, request.question)
        except QueryFailed as failure:
            raise HTTPException(422, {"message": failure.message, "sql": failure.sql})

    # explain_results never raises: any problem yields a safe fallback sentence.
    explanation = explain_results(request.question, outcome.results)
    sent = outcome.results.head(RESULT_ROWS_TO_CLIENT)

    return {
        "question": request.question,
        "explanation": explanation.text,
        "explanation_verified": explanation.verified,
        "sql": outcome.sql,
        "columns": [str(c) for c in outcome.results.columns],
        "results": sent.fillna("").to_dict(orient="records"),
        "row_count": len(outcome.results),
        "truncated": len(outcome.results) > len(sent),
        "attempts": outcome.attempts,
        "chart": build_chart(outcome.results, request.question),
    }
