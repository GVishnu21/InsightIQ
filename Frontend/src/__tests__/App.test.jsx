import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.jsx";
import { answer, dataset } from "../test/fixtures.js";

// Replace only the functions that talk to the network; keep the real error helpers.
vi.mock("../api.js", async (importOriginal) => ({
  ...(await importOriginal()),
  createDataset: vi.fn(),
  fetchSummary: vi.fn(),
  askQuestion: vi.fn(),
}));
vi.mock("../pdf.js", () => ({
  downloadReportPdf: vi.fn(),
  reportFilename: () => "report.pdf",
}));

import * as api from "../api.js";
import * as pdf from "../pdf.js";

const csv = (name = "orders.csv") => new File(["a,b\n1,2"], name, { type: "text/csv" });
const fileInput = () => document.querySelector('input[type="file"]');
const analyzeButton = () => screen.getByRole("button", { name: "Analyze file" });

// The hidden PDF report (.report-offscreen) repeats the answers, so look only at
// what a user can actually see on the page.
const visible = (text) =>
  screen.queryAllByText(text).filter((el) => !el.closest(".report-offscreen"));

async function findVisible(text) {
  return waitFor(() => {
    const matches = visible(text);
    expect(matches).toHaveLength(1);
    return matches[0];
  });
}

async function uploadDataset(user) {
  await user.upload(fileInput(), csv());
  await user.click(analyzeButton());
  await screen.findByRole("heading", { name: "Dataset overview" });
}

async function ask(user, question) {
  await user.type(screen.getByLabelText("Your question"), `${question}{Enter}`);
}

beforeEach(() => {
  vi.resetAllMocks(); // also drops any queued "once" answers from an earlier test
  api.createDataset.mockResolvedValue(dataset);
  api.askQuestion.mockResolvedValue(answer());
  window.alert = vi.fn();
});

describe("upload", () => {
  it("shows an inline message, not a popup, when no file was chosen", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(analyzeButton());

    expect(screen.getByText("Please choose a CSV file first.")).toBeInTheDocument();
    expect(api.createDataset).not.toHaveBeenCalled();
    expect(window.alert).not.toHaveBeenCalled();
  });

  it("shows the overview after a successful upload", async () => {
    const user = userEvent.setup();
    render(<App />);

    await uploadDataset(user);

    expect(api.createDataset).toHaveBeenCalledOnce();
    expect(visible("106")).toHaveLength(1); // rows
    expect(screen.getByRole("heading", { name: "Ask your data" })).toBeInTheDocument();
  });

  it("shows the backend's error text when the upload is rejected", async () => {
    const user = userEvent.setup();
    api.createDataset.mockRejectedValue({
      response: { status: 400, data: { detail: "Only .csv files are allowed." } },
    });
    render(<App />);

    await user.upload(fileInput(), csv());
    await user.click(analyzeButton());

    expect(await screen.findByText("Only .csv files are allowed.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Dataset overview" })).not.toBeInTheDocument();
  });
});

describe("conversation", () => {
  it("sends the dataset id with the question and shows the answer", async () => {
    const user = userEvent.setup();
    render(<App />);
    await uploadDataset(user);

    await ask(user, "Which region has the highest revenue?");

    expect(await findVisible(/Central had the highest revenue/)).toBeInTheDocument();
    expect(api.askQuestion).toHaveBeenCalledWith("abc123", "Which region has the highest revenue?");
  });

  it("keeps earlier answers when another question is asked", async () => {
    const user = userEvent.setup();
    api.askQuestion
      .mockResolvedValueOnce(answer({ explanation: "First answer." }))
      .mockResolvedValueOnce(answer({ explanation: "Second answer." }));
    render(<App />);
    await uploadDataset(user);

    await ask(user, "one?");
    await findVisible("First answer.");
    await ask(user, "two?");

    expect(await findVisible("Second answer.")).toBeInTheDocument();
    expect(visible("First answer.")).toHaveLength(1);
  });

  it("shows blocked SQL together with the reason", async () => {
    const user = userEvent.setup();
    api.askQuestion.mockRejectedValue({
      response: {
        status: 422,
        data: { detail: { message: "Generated SQL was blocked: nope", sql: "DROP TABLE x" } },
      },
    });
    render(<App />);
    await uploadDataset(user);

    await ask(user, "delete everything");

    expect(await screen.findByText(/Generated SQL was blocked: nope/)).toBeInTheDocument();
    expect(screen.getByText("DROP TABLE x")).toBeInTheDocument();
  });

  it("ignores an answer that arrives after the dataset was replaced", async () => {
    const user = userEvent.setup();
    let resolveSlowAnswer;
    api.askQuestion.mockReturnValue(new Promise((resolve) => (resolveSlowAnswer = resolve)));
    render(<App />);
    await uploadDataset(user);

    await ask(user, "slow question?");
    await screen.findByText("Working on it...");

    // The user picks a different file while the answer is still on its way.
    await user.upload(fileInput(), csv("other.csv"));
    expect(screen.queryByText("slow question?")).not.toBeInTheDocument();

    await act(async () => resolveSlowAnswer(answer({ explanation: "STALE ANSWER" })));
    expect(screen.queryAllByText("STALE ANSWER")).toHaveLength(0);
    expect(screen.queryByRole("heading", { name: "Dataset overview" })).not.toBeInTheDocument();
  });
});

describe("summary and report", () => {
  it("ignores a summary that arrives after the dataset was replaced", async () => {
    const user = userEvent.setup();
    let resolveSummary;
    api.fetchSummary.mockReturnValue(new Promise((resolve) => (resolveSummary = resolve)));
    render(<App />);
    await uploadDataset(user);

    await user.click(screen.getByRole("button", { name: "Write summary" }));
    await user.upload(fileInput(), csv("other.csv")); // a different file while the summary is pending

    await act(async () => resolveSummary("1. Dataset Overview\nOLD SUMMARY"));

    // Without the guard, the old file's summary would appear under the new dataset.
    expect(screen.queryAllByText("OLD SUMMARY")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /Download full report/ })).not.toBeInTheDocument();
  });

  it("writes the AI summary and offers the full report download", async () => {
    const user = userEvent.setup();
    api.fetchSummary.mockResolvedValue("1. Dataset Overview\nRows: 106.");
    render(<App />);
    await uploadDataset(user);

    await user.click(screen.getByRole("button", { name: "Write summary" }));

    expect(api.fetchSummary).toHaveBeenCalledWith("abc123");
    expect(await screen.findByRole("button", { name: /Download full report/ })).toBeInTheDocument();
  });

  it("exports the report element with a filename when downloading", async () => {
    const user = userEvent.setup();
    render(<App />);
    await uploadDataset(user);
    await ask(user, "Q?");
    await findVisible(/Central had the highest revenue/);

    await user.click(screen.getByRole("button", { name: /Download report/ }));

    expect(pdf.downloadReportPdf).toHaveBeenCalledOnce();
    const [element, filename] = pdf.downloadReportPdf.mock.calls[0];
    expect(element).toHaveClass("report");
    expect(filename).toBe("report.pdf");
  });

  it("shows an inline error if PDF creation fails", async () => {
    const user = userEvent.setup();
    pdf.downloadReportPdf.mockRejectedValue(new Error("canvas failed"));
    render(<App />);
    await uploadDataset(user);
    await ask(user, "Q?");
    await findVisible(/Central had the highest revenue/);

    await user.click(screen.getByRole("button", { name: /Download report/ }));

    expect(await screen.findByText(/Could not create the PDF report/)).toBeInTheDocument();
  });
});
