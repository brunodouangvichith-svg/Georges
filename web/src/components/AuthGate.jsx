import { useEffect, useState } from "react";
import { isSupabaseConfigured, supabase } from "../api/supabaseClient";
import LoginScreen from "./LoginScreen";

// Portail d'accès simple (Phase 9, voir CLAUDE.md section Auth) : affiche
// LoginScreen tant qu'aucune session Supabase n'existe, sinon les enfants.
// `onAuthStateChange` couvre la session existante au chargement (persistée
// via localStorage par @supabase/supabase-js, aucun code à écrire pour ça),
// la connexion par mot de passe/inscription ET le retour de redirection
// OAuth — un seul point d'entrée, même principe que MeteoIA/static/index.html.
export default function AuthGate({ children }) {
  const [session, setSession] = useState(undefined); // undefined = pas encore su, null = déconnecté

  useEffect(() => {
    if (!isSupabaseConfigured) return;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => subscription.unsubscribe();
  }, []);

  if (!isSupabaseConfigured) {
    return (
      <div
        className="h-screen flex items-center justify-center text-center px-6"
        style={{ background: "var(--bg)", color: "var(--text-dim)" }}
      >
        <div className="max-w-[420px] text-[13px] leading-relaxed">
          Configuration Supabase manquante — copiez <code>.env.example</code> en <code>.env</code> et renseignez{" "}
          <code>VITE_SUPABASE_URL</code>/<code>VITE_SUPABASE_ANON_KEY</code> (voir CLAUDE.md, section Auth).
        </div>
      </div>
    );
  }

  if (session === undefined) return null;
  if (session === null) return <LoginScreen />;
  return children;
}
