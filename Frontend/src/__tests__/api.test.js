import { beforeEach, describe, expect, it, vi } from "vitest";

// api.js calls axios.create() when it loads, so the fake must exist before the import.
const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("axios", () => ({ default: { create: () => ({ post }) } }));

import { askQuestion, blockedSql, createDataset, describeError, fetchSummary } from "../api.js";

const failure = (status, detail) => ({ response: { status, data: { detail } } });

describe("describeError", () => {
  it("uses a plain-text detail from the backend", () => {
    expect(describeError(failure(400, "Only .csv files are allowed."), "x")).toBe(
      "Only .csv files are allowed.",
    );
  });

  it("uses the message of an object detail (blocked SQL)", () => {
    const error = failure(422, { message: "Generated SQL was blocked", sql: "DROP" });
    expect(describeError(error, "x")).toBe("Generated SQL was blocked");
  });

  it("joins FastAPI validation errors", () => {
    const error = failure(422, [{ msg: "Field required" }, { msg: "Too long" }]);
    expect(describeError(error, "x")).toBe("Field required Too long");
  });

  it("explains an unreachable backend when there is no response", () => {
    expect(describeError(new Error("Network Error"), "x")).toMatch(/Cannot reach the backend/);
  });

  it("falls back to the caller's text for unknown error shapes", () => {
    expect(describeError({ response: { status: 500, data: {} } }, "Upload failed.")).toBe(
      "Upload failed.",
    );
  });
});

describe("blockedSql", () => {
  it("returns the SQL the backend attached to an error", () => {
    expect(blockedSql(failure(422, { message: "m", sql: "SELECT 1" }))).toBe("SELECT 1");
  });

  it("returns null when there is none", () => {
    expect(blockedSql(failure(404, "Dataset not found."))).toBeNull();
    expect(blockedSql(new Error("boom"))).toBeNull();
  });
});

describe("requests", () => {
  // Braces matter: a function RETURNED from beforeEach is run as cleanup by Vitest.
  beforeEach(() => {
    post.mockReset();
  });

  it("createDataset posts the file as multipart form data to /datasets", async () => {
    post.mockResolvedValue({ data: { dataset_id: "d1" } });
    const file = new File(["a,b\n1,2"], "data.csv", { type: "text/csv" });

    const result = await createDataset(file);

    const [url, body] = post.mock.calls[0];
    expect(url).toBe("/datasets");
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("file")).toBe(file);
    expect(result).toEqual({ dataset_id: "d1" });
  });

  it("fetchSummary posts to the dataset's summary path and returns the text", async () => {
    post.mockResolvedValue({ data: { summary: "Hello" } });
    expect(await fetchSummary("d1")).toBe("Hello");
    expect(post).toHaveBeenCalledWith("/datasets/d1/summary");
  });

  it("askQuestion sends the question as JSON to the dataset's ask path", async () => {
    post.mockResolvedValue({ data: { explanation: "ok" } });
    expect(await askQuestion("d1", "top products?")).toEqual({ explanation: "ok" });
    expect(post).toHaveBeenCalledWith("/datasets/d1/ask", { question: "top products?" });
  });

  it("encodes the dataset id so it cannot alter the URL path", async () => {
    post.mockResolvedValue({ data: {} });
    await askQuestion("../admin?x=1", "q");
    expect(post.mock.calls[0][0]).toBe("/datasets/..%2Fadmin%3Fx%3D1/ask");
  });

  it("lets errors propagate so the caller can show them", async () => {
    post.mockRejectedValue(failure(413, "File is too large."));
    await expect(createDataset(new File(["x"], "a.csv"))).rejects.toMatchObject({
      response: { status: 413 },
    });
  });
});
