// Sample backend responses shared by the tests.

export const dataset = {
  dataset_id: "abc123",
  filename: "orders.csv",
  preview: [{ region: "North", revenue: 10 }],
  profile: {
    rows: 106,
    columns: 11,
    total_missing: 51,
    duplicate_rows: 0,
    duplicate_samples: [],
    columns_summary: [{ column: "region", dtype: "str", type: "text" }],
    numeric_summary: [{ column: "revenue", min: 1, max: 9 }],
    missing_columns: [],
  },
  anomalies: [],
};

export function answer(overrides = {}) {
  return {
    question: "q",
    explanation: "Central had the highest revenue at 115,073.5.",
    explanation_verified: true,
    sql: 'SELECT "region" FROM uploaded_data',
    columns: ["region", "total"],
    results: [{ region: "Central", total: 115073.5 }],
    row_count: 1,
    truncated: false,
    attempts: 1,
    chart: null,
    ...overrides,
  };
}

// A conversation turn that has been answered.
export function answeredTurn(id, question, answerOverrides = {}, extra = {}) {
  return { id, question, status: "answered", answer: answer(answerOverrides), ...extra };
}
