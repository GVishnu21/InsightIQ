import DataTable from "./DataTable.jsx";
import SummaryText from "./SummaryText.jsx";

const ROWS_PER_ANSWER = 10;

// The document that becomes the PDF. App renders it off-screen from the same data
// the page shows: dataset facts, the AI summary if one exists, and every answered
// question with its chart, SQL and first rows.
function ReportDocument({ dataset, summary, turns, ref }) {
  const answered = turns.filter((turn) => turn.status === "answered");
  const today = new Date().toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const { profile } = dataset;

  const facts = [
    ["Rows", profile.rows],
    ["Columns", profile.columns],
    ["Empty cells", profile.total_missing],
    ["Repeated rows", profile.duplicate_rows],
  ];

  return (
    <div className="report" ref={ref}>
      <div className="report-head">
        <h1>InsightIQ Data Analysis Report</h1>
        <p>
          {dataset.filename} · {today}
        </p>
      </div>

      <div className="report-facts">
        {facts.map(([label, value]) => (
          <div className="report-fact" key={label}>
            <b>{label}</b>
            <span>{value}</span>
          </div>
        ))}
      </div>

      {summary && (
        <div className="report-section">
          <h2>Executive Summary</h2>
          <SummaryText text={summary} />
        </div>
      )}

      {answered.length > 0 && (
        <div className="report-section">
          <h2>Questions and Answers</h2>

          {answered.map((turn, index) => {
            const { answer } = turn;
            return (
              <div className="report-turn" key={turn.id}>
                <h3>
                  {index + 1}. {turn.question}
                </h3>
                <p>{answer.explanation}</p>
                {!answer.explanation_verified && (
                  <p className="report-note">
                    This wording could not be checked against the data; the table is the exact
                    result.
                  </p>
                )}

                {turn.chartImage && (
                  <img
                    className="report-chart"
                    src={turn.chartImage}
                    alt={`Chart for: ${turn.question}`}
                  />
                )}

                <pre className="report-code">{answer.sql}</pre>

                <DataTable rows={answer.results.slice(0, ROWS_PER_ANSWER)} />
                {answer.row_count > ROWS_PER_ANSWER && (
                  <p className="report-note">
                    Showing the first {ROWS_PER_ANSWER} of {answer.row_count} rows.
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!summary && answered.length === 0 && (
        <div className="report-section">
          <p>No summary has been written and no questions have been answered yet.</p>
        </div>
      )}

      <div className="report-foot">
        Figures in this report were calculated by DuckDB and Pandas from the uploaded data.
        Written explanations were produced by Google Gemini and checked against those results.
        Review before business use.
      </div>
    </div>
  );
}

export default ReportDocument;
