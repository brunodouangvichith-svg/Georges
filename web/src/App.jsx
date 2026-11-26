import Layout from "./components/Layout";
import Univers from "./views/Univers";
import Trading from "./views/Trading";
import Energie from "./views/Energie";
import Rapport from "./views/Rapport";
import { useViewHistory } from "./hooks/useViewHistory";

// L'écran views/Obligataire.jsx est conservé mais n'est plus proposé (demande
// de l'utilisateur, nov. 2026).
const VIEWS = ["univers", "trading", "energie", "rapport"];

export default function App() {
  const [view, setView] = useViewHistory(VIEWS);

  return (
    <Layout view={view} setView={setView}>
      {view === "univers" && <Univers />}
      {view === "trading" && <Trading />}
      {view === "energie" && <Energie />}
      {view === "rapport" && <Rapport />}
    </Layout>
  );
}
