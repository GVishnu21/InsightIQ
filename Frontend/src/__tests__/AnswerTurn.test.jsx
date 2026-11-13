import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AnswerTurn from "../components/AnswerTurn.jsx";
import { answeredTurn } from "../test/fixtures.js";

// Plotly cannot run in a fake browser, so replace the chart with a stand-in that,
// like the real one, reports a picture of itself through onImage.
vi.mock("../components/ChartView.jsx", async () => {
  const { useEffect } = await import("react");
  return {
    default: function FakeChart({ chart, onImage }) {
      useEffect(() => onImage?.("data:image/png;base64,FAKE"), [onImage]);
      return <div data-testid="chart">{chart.type} chart</div>;
    },
  };
});

describe("AnswerTurn", () => {
  it("shows a waiting state while the answer is pending", () => {
    render(<AnswerTurn turn={{ id: 1, question: "Q?", status: "pending" }} />);
    expect(screen.getByText("Q?")).toBeInTheDocument();
    expect(screen.getByText("Working on it...")).toBeInTheDocument();
  });

  it("shows the error and the SQL that was rejected", () => {
    const turn = {
      id: 1,
      question: "Q?",
      status: "failed",
      error: "Generated SQL was blocked: nope",
      sql: "DROP TABLE x",
    };
    render(<AnswerTurn turn={turn} />);
    expect(screen.getByText(/Generated SQL was blocked/)).toBeInTheDocument();
    expect(screen.getByText("DROP TABLE x")).toBeInTheDocument();
  });

  it("shows only the error text when there is no SQL", () => {
    render(
      <AnswerTurn
        turn={{ id: 1, question: "Q?", status: "failed", error: "Dataset not found.", sql: null }}
      />,
    );
    expect(screen.getByText("Dataset not found.")).toBeInTheDocument();
    expect(screen.queryByText(/SQL that was rejected/)).not.toBeInTheDocument();
  });

  it("shows the explanation, the SQL and the result table", () => {
    render(<AnswerTurn turn={answeredTurn(1, "Which region?")} />);
    expect(screen.getByText(/Central had the highest revenue/)).toBeInTheDocument();
    expect(screen.getByText(/SELECT "region" FROM uploaded_data/)).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "115073.5" })).toBeInTheDocument();
    expect(screen.queryByText(/could not be checked/)).not.toBeInTheDocument();
  });

  it("warns when the explanation could not be checked against the data", () => {
    render(<AnswerTurn turn={answeredTurn(1, "Q?", { explanation_verified: false })} />);
    expect(screen.getByText(/could not be checked against the data/)).toBeInTheDocument();
  });

  it("says when the SQL was corrected and when rows were cut off", () => {
    render(<AnswerTurn turn={answeredTurn(1, "Q?", { attempts: 2, truncated: true, row_count: 500 })} />);
    expect(screen.getByText(/first query failed/)).toBeInTheDocument();
    expect(screen.getByText(/Showing the first 1 of 500 rows/)).toBeInTheDocument();
  });

  it("draws a chart and hands its picture to the PDF through onChartImage", async () => {
    const onChartImage = vi.fn();
    const chart = { type: "bar", figure: { data: [], layout: {} } };
    render(<AnswerTurn turn={answeredTurn(7, "Q?", { chart })} onChartImage={onChartImage} />);

    expect(await screen.findByTestId("chart")).toHaveTextContent("bar chart");
    expect(onChartImage).toHaveBeenCalledWith(7, "data:image/png;base64,FAKE");
  });

  it("shows no chart when the backend sent none", () => {
    render(<AnswerTurn turn={answeredTurn(1, "Q?")} />);
    expect(screen.queryByTestId("chart")).not.toBeInTheDocument();
  });
});
