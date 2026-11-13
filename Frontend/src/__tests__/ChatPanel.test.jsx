import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ChatPanel from "../components/ChatPanel.jsx";
import { answeredTurn } from "../test/fixtures.js";

function setup(props = {}) {
  const onAsk = vi.fn();
  const onDownload = vi.fn();
  render(<ChatPanel turns={[]} busy={false} onAsk={onAsk} onDownload={onDownload} {...props} />);
  return { onAsk, onDownload, input: screen.getByLabelText("Your question") };
}

describe("ChatPanel", () => {
  it("submits the trimmed question with Enter and clears the box", async () => {
    const user = userEvent.setup();
    const { onAsk, input } = setup();

    await user.type(input, "  top 5 products  {Enter}");

    expect(onAsk).toHaveBeenCalledExactlyOnceWith("top 5 products");
    expect(input).toHaveValue("");
  });

  it("submits with the Ask button too", async () => {
    const user = userEvent.setup();
    const { onAsk, input } = setup();

    await user.type(input, "revenue by month");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(onAsk).toHaveBeenCalledWith("revenue by month");
  });

  it("ignores blank questions and keeps the button disabled", async () => {
    const user = userEvent.setup();
    const { onAsk, input } = setup();

    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    await user.type(input, "   {Enter}");

    expect(onAsk).not.toHaveBeenCalled();
  });

  it("blocks new questions while one is still being answered", async () => {
    const user = userEvent.setup();
    const { onAsk, input } = setup({ busy: true });

    await user.type(input, "another question{Enter}");

    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    expect(onAsk).not.toHaveBeenCalled();
  });

  it("suggests example questions until the first one is asked", () => {
    setup();
    expect(screen.getByText("Show total revenue by month")).toBeInTheDocument();
  });

  it("keeps every earlier question and answer on screen, oldest first", () => {
    setup({ turns: [answeredTurn(1, "First question?"), answeredTurn(2, "Second question?")] });

    const questions = screen.getAllByText(/question\?/).map((el) => el.textContent);
    expect(questions).toEqual(["First question?", "Second question?"]);
    expect(screen.queryByText("Try a question such as:")).not.toBeInTheDocument();
  });

  it("offers the PDF download only once something has been answered", () => {
    setup();
    expect(screen.queryByRole("button", { name: /Download report/ })).not.toBeInTheDocument();
  });

  it("calls onDownload when the report button is clicked", async () => {
    const user = userEvent.setup();
    const { onDownload } = setup({ turns: [answeredTurn(1, "Q?")] });

    await user.click(screen.getByRole("button", { name: /Download report/ }));

    expect(onDownload).toHaveBeenCalledOnce();
  });
});
