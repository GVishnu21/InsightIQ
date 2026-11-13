import { useEffect, useRef, useState } from "react";
import AnswerTurn from "./AnswerTurn.jsx";

const EXAMPLES = [
  "Which region had the highest revenue?",
  "Show total revenue by month",
  "What are the top five categories by units sold?",
];

// The conversation. Earlier questions stay visible and the newest is at the bottom.
function ChatPanel({ turns, busy, onAsk, onChartImage, onDownload }) {
  const [draft, setDraft] = useState("");
  const bottomRef = useRef(null);

  // Bring the newest turn into view when one is added or finishes.
  const newest = turns[turns.length - 1];
  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [turns.length, newest?.status]);

  const submit = (event) => {
    event.preventDefault(); // Enter submits the form without reloading the page
    const question = draft.trim();
    if (!question || busy) return;
    onAsk(question);
    setDraft("");
  };

  const anyAnswered = turns.some((turn) => turn.status === "answered");

  return (
    <section className="panel" aria-labelledby="chat-title">
      <div className="panel-head">
        <h2 className="panel-title" id="chat-title">
          Ask your data
        </h2>
        {anyAnswered && (
          <button className="btn btn-quiet" onClick={onDownload}>
            Download report (PDF)
          </button>
        )}
      </div>

      {turns.length === 0 && (
        <>
          <p className="note">Try a question such as:</p>
          <ul className="hint-list">
            {EXAMPLES.map((example) => (
              <li key={example}>{example}</li>
            ))}
          </ul>
        </>
      )}

      {turns.map((turn) => (
        <AnswerTurn key={turn.id} turn={turn} onChartImage={onChartImage} />
      ))}
      <div ref={bottomRef} />

      <form className="ask-form" onSubmit={submit}>
        <input
          className="ask-input"
          type="text"
          aria-label="Your question"
          placeholder="e.g. Which region had the highest revenue?"
          value={draft}
          maxLength={500}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button className="btn" type="submit" disabled={busy || !draft.trim()}>
          Ask
        </button>
      </form>
    </section>
  );
}

export default ChatPanel;
