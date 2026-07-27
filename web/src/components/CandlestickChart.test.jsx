import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CandlestickChart from "./CandlestickChart";

const candles = [
  { open: 100, high: 102, low: 99, close: 101 },
  { open: 101, high: 103, low: 100, close: 102 },
  { open: 102, high: 104, low: 101, close: 103 },
];

describe("CandlestickChart", () => {
  it("shows a message when there is no price history", () => {
    render(<CandlestickChart candles={[]} />);
    expect(screen.getByText(/pas d'historique de prix/i)).toBeInTheDocument();
  });

  it("renders one candle body plus the current-price tag when no context/TP/SL is given", () => {
    const { container } = render(<CandlestickChart candles={candles} />);
    expect(container.querySelectorAll("rect").length).toBe(candles.length + 1);
  });

  it("draws take-profit/stop-loss price tags when provided", () => {
    const { container } = render(<CandlestickChart candles={candles} takeProfit={110} stopLoss={95} />);
    // corps de bougies + étiquettes TP/SL + étiquette de prix courant
    expect(container.querySelectorAll("rect").length).toBe(candles.length + 3);
  });

  it("marks the pattern's key points from real context, translated by indexOffset", () => {
    const context = {
      bottom_1: { index: 100, price: 99 },
      bottom_2: { index: 102, price: 99.2 },
      resistance: { index: 101, price: 105 },
    };
    // la fenêtre récupérée correspond aux indices absolus 100-102 de l'historique complet
    const { container } = render(<CandlestickChart candles={candles} context={context} indexOffset={100} />);
    expect(container.querySelectorAll("circle").length).toBe(3);
    // 3 mèches de chandelier + 1 ligne de prix courant + 1 ligne de résistance (clé de niveau)
    expect(container.querySelectorAll("line").length).toBe(candles.length + 2);
  });

  it("ignores context points that fall outside the fetched window", () => {
    const context = { bottom_1: { index: 5, price: 50 } }; // bien avant indexOffset
    const { container } = render(<CandlestickChart candles={candles} context={context} indexOffset={100} />);
    expect(container.querySelectorAll("circle").length).toBe(0);
  });
});
