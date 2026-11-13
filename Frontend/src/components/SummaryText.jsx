const NUMBERED_HEADING = /^\d+\.\s/;

// The backend writes the summary as plain text with numbered headings such as
// "2. Data Completeness". This turns that text into headings and paragraphs; the
// on-screen summary and the PDF report both use it, so they always match.
function SummaryText({ text }) {
  const lines = text
    .split("\n")
    .map((line) => line.replace(/[*#]/g, "").trim()) // in case the model adds markdown
    .filter(Boolean);

  return lines.map((line, index) =>
    NUMBERED_HEADING.test(line) ? <h4 key={index}>{line}</h4> : <p key={index}>{line}</p>,
  );
}

export default SummaryText;
