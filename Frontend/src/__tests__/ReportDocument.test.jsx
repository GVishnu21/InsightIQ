import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it } from "vitest";
import ReportDocument from "../components/ReportDocument.jsx";
import { answeredTurn, dataset } from "../test/fixtures.js";

const renderReport = (props) =>
  render(<ReportDocument dataset={dataset} summary="" turns={[]} {...props} />);

describe("ReportDocument (the content of the PDF)", () => {
  it("shows the dataset facts in the header", () => {
    renderReport();
    expect(screen.getByRole("heading", { name: /InsightIQ Data Analysis Report/ })).toBeInTheDocument();
    expect(screen.getByText(/orders\.csv/)).toBeInTheDocument();
    expect(screen.getByText("106")).toBeInTheDocument();
    expect(screen.getByText("51")).toBeInTheDocument();
  });

  it("says so when there is nothing but the dataset facts", () => {
    renderReport();
    expect(screen.getByText(/No summary has been written/)).toBeInTheDocument();
    expect(screen.queryByText("Questions and Answers")).not.toBeInTheDocument();
  });

  it("includes the AI summary, turning numbered lines into headings", () => {
    renderReport({ summary: "1. Dataset Overview\nRows: 106." });
    expect(screen.getByRole("heading", { name: "1. Dataset Overview" })).toBeInTheDocument();
    expect(screen.getByText("Rows: 106.")).toBeInTheDocument();
    expect(screen.queryByText(/No summary has been written/)).not.toBeInTheDocument();
  });

  it("includes only answered questions, numbered in order", () => {
    renderReport({
      turns: [
        answeredTurn(1, "First?"),
        { id: 2, question: "Still waiting?", status: "pending" },
        { id: 3, question: "Failed?", status: "failed", error: "x" },
        answeredTurn(4, "Fourth?"),
      ],
    });
    expect(screen.getByRole("heading", { name: "1. First?" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "2. Fourth?" })).toBeInTheDocument();
    expect(screen.queryByText(/Still waiting/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Failed\?/)).not.toBeInTheDocument();
  });

  it("embeds the chart picture when one was captured", () => {
    renderReport({ turns: [answeredTurn(1, "Q?", {}, { chartImage: "data:image/png;base64,AAA" })] });
    expect(screen.getByAltText(/Chart for: Q\?/)).toHaveAttribute("src", "data:image/png;base64,AAA");
  });

  it("leaves out the picture when no chart was captured", () => {
    renderReport({ turns: [answeredTurn(1, "Q?")] });
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("limits each table to 10 rows and says how many there really are", () => {
    const many = Array.from({ length: 25 }, (_, i) => ({ n: i + 1 }));
    renderReport({ turns: [answeredTurn(1, "Q?", { results: many, row_count: 25 })] });
    expect(screen.getAllByRole("row")).toHaveLength(11); // header + 10 rows
    expect(screen.getByText(/first 10 of 25 rows/)).toBeInTheDocument();
  });

  it("flags explanations that could not be checked", () => {
    renderReport({ turns: [answeredTurn(1, "Q?", { explanation_verified: false })] });
    expect(screen.getByText(/could not be checked against the data/)).toBeInTheDocument();
  });

  it("passes its ref to the element that gets exported", () => {
    const ref = createRef();
    renderReport({ ref });
    expect(ref.current).toBeInstanceOf(HTMLElement);
    expect(ref.current).toHaveClass("report");
  });
});
