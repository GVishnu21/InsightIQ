import SummaryText from "./SummaryText.jsx";

// On-screen executive summary. The button exports the FULL report (this summary
// plus every question asked so far), which ReportDocument lays out.
function SummaryPanel({ summary, onDownload }) {
  return (
    <section className="panel" aria-labelledby="summary-title">
      <div className="panel-head">
        <h2 className="panel-title" id="summary-title">
          Executive summary
        </h2>
        <button className="btn" onClick={onDownload}>
          Download full report (PDF)
        </button>
      </div>

      <div className="prose">
        <SummaryText text={summary} />
      </div>
      <p className="note">
        Counts come from Pandas. Only the suggestions in sections 5 and 6 were written by Gemini.
      </p>
    </section>
  );
}

export default SummaryPanel;
