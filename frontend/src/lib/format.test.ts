import { describe, expect, it } from "vitest";
import { formatBytes, formatDate, timeAgo } from "./format";

describe("formatBytes", () => {
  it("renders a placeholder for an unknown (negative) size", () => {
    expect(formatBytes(-1)).toBe("calculating…");
  });

  it("formats zero and byte-scale values", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
  });

  it("formats KB/MB/GB with one decimal", () => {
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(48234496)).toBe("46.0 MB");
    expect(formatBytes(4503599627)).toBe("4.2 GB");
  });
});

describe("timeAgo", () => {
  it("returns 'never' for missing input", () => {
    expect(timeAgo(null)).toBe("never");
    expect(timeAgo(undefined)).toBe("never");
  });

  it("returns relative seconds/minutes/hours/days", () => {
    const now = Date.now();
    expect(timeAgo(new Date(now - 5_000).toISOString())).toMatch(/^\d+s ago$/);
    expect(timeAgo(new Date(now - 5 * 60_000).toISOString())).toBe("5m ago");
    expect(timeAgo(new Date(now - 3 * 3_600_000).toISOString())).toBe("3h ago");
    expect(timeAgo(new Date(now - 2 * 86_400_000).toISOString())).toBe("2d ago");
  });
});

describe("formatDate", () => {
  it("returns a dash for missing input", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
  });

  it("passes through unparseable strings unchanged", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });
});
