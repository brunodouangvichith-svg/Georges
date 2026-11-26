import Cac40Panel from "../components/Cac40Panel";
import { useStrategicReport } from "../api/queries";

// Onglet "Trading" — valeurs du CAC 40, tirées du dernier rapport stratégique.
// George ne passe AUCUN ordre.
export default function Trading() {
  const latestReport = useStrategicReport(null);

  return (
    <div className="h-full overflow-y-auto gd-scrollbar">
      <div className="mx-auto flex flex-col gap-4 px-5 py-4" style={{ maxWidth: 1600 }}>
        <div>
          <h1 className="display m-0 text-[18px] font-semibold">Trading</h1>
          <div className="text-xs mt-0.5" style={{ color: "var(--text-dim)" }}>
            Valeurs du CAC 40. Aucun ordre n'est passé.
          </div>
        </div>

        <Cac40Panel query={latestReport} />
      </div>
    </div>
  );
}
