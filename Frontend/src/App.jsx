import { useRef, useState } from "react";
import { askQuestion, blockedSql, createDataset, describeError, fetchSummary } from "./api.js";
import ChatPanel from "./components/ChatPanel.jsx";
import Header from "./components/Header.jsx";
import OverviewPanel from "./components/OverviewPanel.jsx";
import ReportDocument from "./components/ReportDocument.jsx";
import SummaryPanel from "./components/SummaryPanel.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import { downloadReportPdf, reportFilename } from "./pdf.js";

// App owns the state and the actions; the components only draw what they are given.
function App() {
  const [file, setFile] = useState(null);
  const [dataset, setDataset] = useState(null); // response of POST /datasets
  const [summary, setSummary] = useState("");
  const [turns, setTurns] = useState([]); // the conversation
  const [busy, setBusy] = useState(false); // uploading or writing the summary
  const [problem, setProblem] = useState("");

  // Counts dataset changes. A slow reply that belongs to an OLD dataset checks it
  // and is dropped instead of appearing under the new one.
  const generation = useRef(0);
  const nextTurnId = useRef(1);
  const reportRef = useRef(null); // the off-screen report that becomes the PDF

  const forgetResults = () => {
    generation.current += 1;
    setDataset(null);
    setSummary("");
    setTurns([]);
    setProblem("");
  };

  const pickFile = (chosen) => {
    setFile(chosen);
    forgetResults();
  };

  const analyze = async () => {
    if (!file) {
      setProblem("Please choose a CSV file first.");
      return;
    }

    forgetResults();
    setBusy(true);
    try {
      setDataset(await createDataset(file));
    } catch (error) {
      console.error(error);
      setProblem(describeError(error, "The upload failed."));
    } finally {
      setBusy(false);
    }
  };

  const writeSummary = async () => {
    if (!dataset) return;

    const mine = generation.current;
    setBusy(true);
    setProblem("");
    try {
      const text = await fetchSummary(dataset.dataset_id);
      if (mine === generation.current) setSummary(text);
    } catch (error) {
      console.error(error);
      if (mine === generation.current) {
        setProblem(describeError(error, "The summary could not be written."));
      }
    } finally {
      setBusy(false);
    }
  };

  const ask = async (question) => {
    if (!dataset) return;

    const mine = generation.current;
    const id = nextTurnId.current++;
    const update = (changes) => {
      if (mine !== generation.current) return;
      setTurns((all) => all.map((turn) => (turn.id === id ? { ...turn, ...changes } : turn)));
    };

    setTurns((all) => [...all, { id, question, status: "pending" }]);

    try {
      update({ status: "answered", answer: await askQuestion(dataset.dataset_id, question) });
    } catch (error) {
      console.error(error);
      update({
        status: "failed",
        error: describeError(error, "That question could not be answered."),
        sql: blockedSql(error),
      });
    }
  };

  // A chart's PNG arrives after it is drawn and is used only by the PDF.
  const attachChartImage = (id, chartImage) => {
    setTurns((all) => all.map((turn) => (turn.id === id ? { ...turn, chartImage } : turn)));
  };

  const downloadReport = async () => {
    try {
      await downloadReportPdf(reportRef.current, reportFilename(dataset?.filename));
    } catch (error) {
      console.error(error);
      setProblem("Could not create the PDF report. Please try again.");
    }
  };

  const waitingForAnswer = turns.some((turn) => turn.status === "pending");

  return (
    <>
      <Header />

      <main className="page">
        <div className="intro">
          <h2>From raw CSV to answers you can verify</h2>
          <p>
            Upload a file, check its quality, then ask questions. Every answer shows the SQL that
            produced it and the exact rows behind it.
          </p>
        </div>

        <UploadPanel
          file={file}
          hasDataset={Boolean(dataset)}
          busy={busy}
          onPick={pickFile}
          onAnalyze={analyze}
          onSummarize={writeSummary}
        />

        {busy && <p className="alert alert-info">Working on it...</p>}
        {problem && <p className="alert alert-error">{problem}</p>}

        {dataset && <OverviewPanel dataset={dataset} />}
        {summary && <SummaryPanel summary={summary} onDownload={downloadReport} />}

        {dataset && (
          <ChatPanel
            turns={turns}
            busy={waitingForAnswer}
            onAsk={ask}
            onChartImage={attachChartImage}
            onDownload={downloadReport}
          />
        )}

        {/* Hidden, print-styled copy of the results: this is what gets exported. */}
        {dataset && (
          <div className="report-offscreen" aria-hidden="true">
            <ReportDocument ref={reportRef} dataset={dataset} summary={summary} turns={turns} />
          </div>
        )}
      </main>
    </>
  );
}

export default App;
