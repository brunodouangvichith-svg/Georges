import { afterEach, describe, expect, it, vi } from "vitest";
import { dateFr } from "./format";

describe("dateFr", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("keeps the calendar day of a date-only string west of UTC", () => {
    vi.stubEnv("TZ", "America/New_York");
    expect(dateFr("2026-10-23")).toBe("23 octobre 2026");
  });

  it("shows a timestamp on the viewer's local day", () => {
    vi.stubEnv("TZ", "America/New_York");
    expect(dateFr("2026-10-23T02:00:00Z")).toBe("22 octobre 2026");
  });

  it("shows a dash when the date is missing", () => {
    expect(dateFr(null)).toBe("—");
  });
});
