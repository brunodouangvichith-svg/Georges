import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RiskMetrics from "./RiskMetrics";

const index = { name: "CAC 40", ticker: "^FCHI", available: true, as_of: "2026-11-25" };
const metrics = {
  symbol: "AIR.PA",
  as_of: "2026-11-25",
  average_daily_volume: 1234567,
  atr: 3.5,
  atr_pct: 2.1,
  volatility_pct: 28.4,
  beta: 1.12,
  index_correlation: 0.71,
  sector_family: "Aéronautique",
  sector_correlation: 0.55,
  sector_peers: 3,
  suspect_jump_date: null,
};
const values = (container) => [...container.querySelectorAll("dd")].map((dd) => dd.textContent.replace(/\s/g, " "));

describe("RiskMetrics", () => {
  it("shows every measure with its unit, formatted in French", () => {
    const { container } = render(<RiskMetrics metrics={metrics} index={index} />);
    expect(values(container)).toEqual(["1 234 567 titres", "28,4 %", "3,50 € (2,1 % du cours)", "1,12", "0,71", "0,55"]);
    expect(screen.getByText(/secteur Aéronautique \(1 an, 3 autres valeurs\)/)).toBeInTheDocument();
    expect(screen.queryByText(/à vérifier/)).not.toBeInTheDocument();
  });

  it("shows a dash, never zero, when measures are missing", () => {
    const { container } = render(<RiskMetrics index={{ ...index, available: false, as_of: null }} />);
    // Tiret à l'écran, « non disponible » pour les lecteurs d'écran.
    expect(values(container)).toEqual(Array(6).fill("—non disponible"));
    expect(container.querySelector("dd [aria-hidden='true']")).toHaveTextContent("—");
    expect(screen.getByText(/Cours du CAC 40 indisponibles/)).toBeInTheDocument();
  });

  it("keeps a real zero", () => {
    const { container } = render(<RiskMetrics metrics={{ ...metrics, beta: 0 }} index={index} />);
    expect(values(container)[3]).toBe("0,00");
  });

  it("warns about a one-session jump above 50 %", () => {
    render(<RiskMetrics metrics={{ ...metrics, suspect_jump_date: "2026-03-02" }} index={index} />);
    expect(screen.getByText(/02 mars 2026.*à vérifier/)).toBeInTheDocument();
  });

  it("announces loading and failure instead of empty values", () => {
    const { rerender, container } = render(<RiskMetrics loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Calcul des mesures");
    rerender(<RiskMetrics error />);
    expect(screen.getByRole("status")).toHaveTextContent("indisponibles");
    expect(container.querySelector("dd")).toBeNull();
  });
});
