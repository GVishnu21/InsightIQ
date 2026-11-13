import DataTable from "./DataTable.jsx";

// A collapsible section, so the technical tables do not bury the page.
function Fold({ title, children }) {
  return (
    <details className="fold">
      <summary>{title}</summary>
      <div className="fold-body">{children}</div>
    </details>
  );
}

function Tile({ label, value }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
    </div>
  );
}

// Everything learned about the uploaded file. `dataset` is the upload response.
function OverviewPanel({ dataset }) {
  const { profile, anomalies, preview } = dataset;

  return (
    <section className="panel" aria-labelledby="overview-title">
      <div className="panel-head">
        <h2 className="panel-title" id="overview-title">
          Dataset overview
        </h2>
        <span className="pill">{dataset.filename}</span>
      </div>

      <div className="tiles">
        <Tile label="Rows" value={profile.rows} />
        <Tile label="Columns" value={profile.columns} />
        <Tile label="Empty cells" value={profile.total_missing} />
        <Tile label="Repeated rows" value={profile.duplicate_rows} />
      </div>

      <h3 className="sub-title">Preview (first {preview.length} rows)</h3>
      <DataTable rows={preview} />

      <Fold title="Columns and types">
        <DataTable rows={profile.columns_summary} />
      </Fold>

      <Fold title="Numeric statistics">
        {profile.numeric_summary.length > 0 ? (
          <DataTable rows={profile.numeric_summary} />
        ) : (
          <p className="empty">This file has no numeric columns.</p>
        )}
      </Fold>

      <Fold title={`Repeated rows (${profile.duplicate_rows})`}>
        {profile.duplicate_rows > 0 ? (
          <>
            <p className="note">
              Rows that exactly repeat an earlier row. "row" is the data row number, header
              excluded.
              {profile.duplicate_rows > profile.duplicate_samples.length &&
                ` Showing ${profile.duplicate_samples.length} of ${profile.duplicate_rows}.`}
            </p>
            <DataTable rows={profile.duplicate_samples} />
          </>
        ) : (
          <p className="empty">No row repeats an earlier row.</p>
        )}
      </Fold>

      <Fold title={`Unusual values (${anomalies.length} column${anomalies.length === 1 ? "" : "s"})`}>
        {anomalies.length > 0 ? (
          <>
            <DataTable rows={anomalies} />
            <p className="note">
              Values more than 3 standard deviations from their column average. Worth a look, but
              not necessarily mistakes.
            </p>
          </>
        ) : (
          <p className="empty">No numeric value stands out from its column.</p>
        )}
      </Fold>
    </section>
  );
}

export default OverviewPanel;
