function UploadPanel({ file, hasDataset, busy, onPick, onAnalyze, onSummarize }) {
  return (
    <section className="panel" aria-labelledby="upload-title">
      <div className="panel-head">
        <h2 className="panel-title" id="upload-title">
          1. Choose a CSV file
        </h2>
      </div>

      <div className="upload-row">
        <label className="file-field">
          <span className="note">CSV files only</span>
          <br />
          <input
            type="file"
            accept=".csv"
            onChange={(event) => onPick(event.target.files[0] ?? null)}
          />
        </label>

        <div className="panel-actions">
          <button className="btn" onClick={onAnalyze} disabled={busy}>
            Analyze file
          </button>
          {hasDataset && (
            <button className="btn btn-quiet" onClick={onSummarize} disabled={busy}>
              Write summary
            </button>
          )}
        </div>
      </div>

      {file && <p className="note">Selected: {file.name}</p>}
    </section>
  );
}

export default UploadPanel;
