import { describe, expect, it } from "vitest";
import { easterSunday, isEuronextHoliday, marketStatus } from "./marketStatus";

describe("marketStatus", () => {
  it("is closed on Saturday", () => {
    // Samedi 17 octobre 2026, 10h30 à Paris (UTC+2).
    const s = marketStatus(new Date("2026-10-17T08:30:00Z"));
    expect(s.open).toBe(false);
    expect(s.reason).toBe("week-end");
    expect(s.time).toBe("10:30");
  });

  it("is open on a weekday during the session", () => {
    const s = marketStatus(new Date("2026-10-19T08:30:00Z")); // lundi 10h30
    expect(s.open).toBe(true);
    expect(s.label).toBe("Marché ouvert");
  });

  it("is closed before 9:00 and after 17:30 Paris time", () => {
    expect(marketStatus(new Date("2026-10-19T06:59:00Z")).reason).toBe("ouverture à 09:00"); // 8h59
    expect(marketStatus(new Date("2026-10-19T15:30:00Z")).reason).toBe("séance terminée"); // 17h30
    expect(marketStatus(new Date("2026-10-19T15:29:00Z")).open).toBe(true); // 17h29
  });

  it("uses winter time correctly", () => {
    // Lundi 7 décembre 2026, 8h30 UTC = 9h30 à Paris (UTC+1).
    const s = marketStatus(new Date("2026-12-07T08:30:00Z"));
    expect(s.time).toBe("09:30");
    expect(s.open).toBe(true);
  });

  it("closes on Euronext holidays and early on 24 December", () => {
    expect(easterSunday(2026)).toEqual({ month: 4, day: 5 });
    expect(isEuronextHoliday(2026, 4, 3)).toBe(true); // Vendredi saint
    expect(isEuronextHoliday(2026, 4, 6)).toBe(true); // lundi de Pâques
    expect(isEuronextHoliday(2026, 7, 14)).toBe(false); // 14 juillet : ouvert
    expect(marketStatus(new Date("2026-05-01T08:00:00Z")).reason).toBe("jour férié");
    expect(marketStatus(new Date("2026-12-24T13:30:00Z")).reason).toBe("séance terminée"); // 14h30
  });
});
