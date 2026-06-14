import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiffView } from "./DiffView";

describe("DiffView", () => {
  it("shows an empty state for blank input", () => {
    const { container } = render(<DiffView diff="   " />);
    expect(screen.getByText("No differences.")).toBeInTheDocument();
    expect(container.querySelector(".diff")).toBeNull();
  });

  it("classifies added, removed and hunk lines", () => {
    const diff = [
      "@@ -1,2 +1,2 @@",
      "+added line",
      "-removed line",
      " context line",
    ].join("\n");
    const { container } = render(<DiffView diff={diff} />);

    expect(container.querySelector(".hunk")?.textContent).toBe("@@ -1,2 +1,2 @@");
    expect(container.querySelector(".add")?.textContent).toBe("+added line");
    expect(container.querySelector(".del")?.textContent).toBe("-removed line");
  });

  it("does not misclassify file headers (+++ / ---) as add/del", () => {
    const diff = ["+++ b/file.txt", "--- a/file.txt"].join("\n");
    const { container } = render(<DiffView diff={diff} />);
    expect(container.querySelector(".add")).toBeNull();
    expect(container.querySelector(".del")).toBeNull();
  });
});
