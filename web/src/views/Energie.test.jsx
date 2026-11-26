import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Energie from "./Energie";

vi.mock("../api/queries", () => ({ useEnergyPrices: vi.fn() }));

import { useEnergyPrices } from "../api/queries";

const price = (commodity_code, value, change) => ({ commodity_code, price: value, currency: "USD", change_24h_pct: change });

describe("Energie", () => {
  it("lists prices in a fixed order with the direction spelled out", () => {
    useEnergyPrices.mockReturnValue({ data: [price("WTI_USD", 84.59, -1.5), price("BRENT_CRUDE_USD", 95.19, 4.67)] });
    const { container } = render(<Energie />);
    expect(container.textContent.indexOf("Brent")).toBeLessThan(container.textContent.indexOf("WTI"));
    expect(screen.getByText("95.19 USD")).toBeInTheDocument();
    expect(screen.getByText("en hausse")).toBeInTheDocument();
    expect(screen.getByText("en baisse")).toBeInTheDocument();
  });

  it("distinguishes an unreachable API from an empty database", () => {
    useEnergyPrices.mockReturnValue({ data: undefined, isError: true });
    const { unmount } = render(<Energie />);
    expect(screen.getByRole("alert")).toHaveTextContent(/impossible de contacter/i);
    unmount();
    useEnergyPrices.mockReturnValue({ data: [] });
    render(<Energie />);
    expect(screen.getByText(/aucune donnée/i)).toBeInTheDocument();
  });
});
