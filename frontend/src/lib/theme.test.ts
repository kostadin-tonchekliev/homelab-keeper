import { describe, expect, it, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { applyTheme, useTheme } from "./theme";

describe("applyTheme", () => {
  it("sets the data-theme attribute on <html>", () => {
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});

describe("useTheme", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("reads a previously persisted theme from localStorage", () => {
    localStorage.setItem("hlb-theme", "light");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
  });

  it("applies the theme to the DOM and persists it", () => {
    localStorage.setItem("hlb-theme", "light");
    renderHook(() => useTheme());
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem("hlb-theme")).toBe("light");
  });

  it("toggles between dark and light and persists the change", () => {
    localStorage.setItem("hlb-theme", "dark");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");

    act(() => result.current.toggle());
    expect(result.current.theme).toBe("light");
    expect(localStorage.getItem("hlb-theme")).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    act(() => result.current.toggle());
    expect(result.current.theme).toBe("dark");
  });

  it("setTheme updates the active theme", () => {
    localStorage.setItem("hlb-theme", "dark");
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme("light"));
    expect(result.current.theme).toBe("light");
  });
});
