// Every call to the InsightIQ backend lives in this file. Components import these
// functions instead of using axios or URLs directly, so an endpoint or the
// backend address changes in exactly one place.

import axios from "axios";

// Set VITE_API_URL in Frontend/.env to use a deployed backend.
const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const http = axios.create({ baseURL: API_BASE });

const datasetPath = (datasetId) => `/datasets/${encodeURIComponent(datasetId)}`;

export async function createDataset(file) {
  const body = new FormData();
  body.append("file", file);
  const { data } = await http.post("/datasets", body);
  return data; // { dataset_id, filename, preview, profile, anomalies }
}

export async function fetchSummary(datasetId) {
  const { data } = await http.post(`${datasetPath(datasetId)}/summary`);
  return data.summary;
}

export async function askQuestion(datasetId, question) {
  const { data } = await http.post(`${datasetPath(datasetId)}/ask`, { question });
  return data;
}

// The backend reports problems as { detail: "text" }, { detail: [{ msg }] } or
// { detail: { message, sql } }. This turns any of them into one sentence.
export function describeError(error, fallback) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(" ");
  if (!error.response) return "Cannot reach the backend. Is it running?";
  return fallback;
}

// When generated SQL is blocked or fails, the backend returns it so it can be shown.
export function blockedSql(error) {
  return error.response?.data?.detail?.sql ?? null;
}
