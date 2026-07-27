import { useState } from "react";
import Layout from "./components/Layout";
import Univers from "./views/Univers";
import Paniers from "./views/Paniers";
import MonPortefeuille from "./views/MonPortefeuille";

function Placeholder({ label }) {
  return (
    <div className="h-full flex items-center justify-center text-sm" style={{ color: "var(--text-dim)" }}>
      Vue « {label} » — pas encore implémentée.
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("univers");

  return (
    <Layout view={view} setView={setView}>
      {view === "univers" && <Univers />}
      {view === "paniers" && <Paniers />}
      {view === "decisions" && <Placeholder label="Décisions" />}
      {view === "alertes" && <Placeholder label="Alertes" />}
      {view === "portefeuille" && <MonPortefeuille />}
    </Layout>
  );
}
