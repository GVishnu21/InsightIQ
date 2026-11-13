import { lazy, Suspense } from "react";
import DataTable from "./DataTable.jsx";

// Plotly is large, so it is only downloaded when a chart is first shown.
const ChartView = lazy(() => import("./ChartView.jsx"));

// One exchange in the conversation: the question and whatever became of it.
// turn = { id, question, status: "pending" | "answered" | "failed", answer, error, sql }
function AnswerTurn({ turn, onChartImage }) {
  const { question, status, answer, error, sql } = turn;

  return (
    <article className="turn">
      <p className="turn-question">{question}</p>

      <div className="turn-answer">
        {status === "pending" && <p className="alert alert-info">Working on it...</p>}

        {status === "failed" && (
          <>
            <p className="alert alert-error">{error}</p>
            {sql && (
              <>
                <h3 className="turn-label">SQL that was rejected</h3>
                <pre className="code-block">{sql}</pre>
              </>
            )}
          </>
        )}

        {status === "answered" && (
          <>
            <p className="turn-explanation">{answer.explanation}</p>
            {!answer.explanation_verified && (
              <p className="note">
                This wording could not be checked against the data, so a plain summary is shown.
                The table below is always the exact result.
              </p>
            )}

            {answer.chart && (
              <Suspense fallback={<p className="empty">Loading chart...</p>}>
                <ChartView
                  chart={answer.chart}
                  onImage={(image) => onChartImage?.(turn.id, image)}
                />
              </Suspense>
            )}

            <h3 className="turn-label">SQL used</h3>
            <pre className="code-block">{answer.sql}</pre>
            {answer.attempts > 1 && (
              <p className="note">The first query failed, so the AI corrected it once.</p>
            )}

            <h3 className="turn-label">Result rows</h3>
            <DataTable rows={answer.results} />
            {answer.truncated && (
              <p className="note">
                Showing the first {answer.results.length} of {answer.row_count} rows.
              </p>
            )}
          </>
        )}
      </div>
    </article>
  );
}

export default AnswerTurn;
