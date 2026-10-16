import { useState } from "react";
import Layout from "./components/Layout";
import Univers from "./views/Univers";
import Obligataire from "./views/Obligataire";
import Trading from "./views/Trading";

export default function App() {
  const [view, setView] = useState("univers");

  return (
    <Layout view={view} setView={setView}>
      {view === "univers" && <Univers />}
      {view === "trading" && <Trading />}
      {view === "obligataire" && <Obligataire />}
    </Layout>
  );
}
