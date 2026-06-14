import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle", () => {
  it("renders both theme options", () => {
    render(<ThemeToggle theme="dark" onToggle={() => {}} />);
    expect(screen.getByText("Dark")).toBeInTheDocument();
    expect(screen.getByText("Light")).toBeInTheDocument();
  });

  it("marks the active option based on the current theme", () => {
    const { rerender } = render(<ThemeToggle theme="dark" onToggle={() => {}} />);
    expect(screen.getByText("Dark").className).toContain("active");
    expect(screen.getByText("Light").className).not.toContain("active");

    rerender(<ThemeToggle theme="light" onToggle={() => {}} />);
    expect(screen.getByText("Light").className).toContain("active");
    expect(screen.getByText("Dark").className).not.toContain("active");
  });

  it("calls onToggle when clicked", () => {
    const onToggle = vi.fn();
    render(<ThemeToggle theme="dark" onToggle={onToggle} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("exposes an accessible label describing the next theme", () => {
    render(<ThemeToggle theme="dark" onToggle={() => {}} />);
    expect(
      screen.getByRole("button", { name: /switch to light theme/i }),
    ).toBeInTheDocument();
  });
});
