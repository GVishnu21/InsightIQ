// Turns the report element into a downloadable A4 PDF, entirely in the browser.
// html2pdf photographs the element (html2canvas) and places the pictures on
// pages (jsPDF). Consequence worth knowing: the PDF text is not selectable.

import html2pdf from "html2pdf.js";

export function reportFilename(datasetName) {
  const base = (datasetName || "dataset").replace(/\.csv$/i, "").replace(/[^\w-]+/g, "-");
  return `insightiq-report-${base}.pdf`;
}

export async function downloadReportPdf(element, filename) {
  if (!element) throw new Error("Report is not ready yet.");

  await html2pdf()
    .set({
      margin: [0.5, 0.5, 0.7, 0.5], // top, left, bottom, right (inches); room for page numbers
      filename,
      image: { type: "jpeg", quality: 0.95 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: "in", format: "a4", orientation: "portrait" },
      // Try not to cut a question block, paragraph, heading, table row, chart or
      // the SQL in half (a page break through a line of text looks broken).
      pagebreak: {
        mode: ["css", "legacy"],
        avoid: [".report-qa", "p", "h3", "tr", "img", "pre"],
      },
    })
    .from(element)
    .toPdf()
    .get("pdf")
    .then((pdf) => {
      const pages = pdf.internal.getNumberOfPages();
      const width = pdf.internal.pageSize.getWidth();
      const height = pdf.internal.pageSize.getHeight();
      pdf.setFontSize(9);
      pdf.setTextColor(120);
      for (let page = 1; page <= pages; page += 1) {
        pdf.setPage(page);
        pdf.text(`Page ${page} of ${pages}`, width / 2, height - 0.3, { align: "center" });
      }
    })
    .save();
}
