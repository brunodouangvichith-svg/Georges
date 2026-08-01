import { useState } from "react";
import Layout from "./components/Layout";
import Univers from "./views/Univers";
import Paniers from "./views/Paniers";
import MonPortefeuille from "./views/MonPortefeuille";
import CarryTrade from "./views/CarryTrade";

export default function App() {
  const [view, setView] = useState("univers");

  return (
    <Layout view={view} setView={setView}>
      {view === "univers" && <Univers />}
      {view === "paniers" && <Paniers />}
      {view === "portefeuille" && <MonPortefeuille />}
      {view === "carry-trade" && <CarryTrade />}
    </Layout>
  );
}
