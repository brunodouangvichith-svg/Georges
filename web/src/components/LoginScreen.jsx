import { useState } from "react";
import { supabase } from "../api/supabaseClient";

// Écran de connexion — affiché par AuthGate.jsx tant qu'aucune session
// Supabase n'existe (portail d'accès simple, Phase 9, voir CLAUDE.md
// section Auth). Email/mot de passe + "Continuer avec Google", mêmes 3
// appels que la version mobile (mobile/lib/features/auth/login_screen.dart).
export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  async function submitEmailPassword(e) {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage("Email et mot de passe requis.");
      return;
    }
    setIsSubmitting(true);
    setErrorMessage(null);
    const { error } = isSignUp
      ? await supabase.auth.signUp({ email, password })
      : await supabase.auth.signInWithPassword({ email, password });
    if (error) setErrorMessage(error.message);
    setIsSubmitting(false);
    // Pas de navigation manuelle ici : AuthGate re-rend automatiquement dès
    // que supabase.auth.onAuthStateChange voit la nouvelle session.
  }

  async function signInWithGoogle() {
    setErrorMessage(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      // Revenir sur l'origine où l'appli est ouverte (localhost en dev, le site
      // Render en production) — sinon Supabase renvoie vers son "Site URL".
      // Cette origine doit figurer dans Supabase → Auth → Redirect URLs.
      options: { redirectTo: window.location.origin },
    });
    if (error) setErrorMessage(error.message);
  }

  return (
    <div className="h-screen flex items-center justify-center" style={{ background: "var(--bg)" }}>
      <form
        onSubmit={submitEmailPassword}
        className="w-full max-w-[360px] p-8 rounded-2xl border"
        style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}
      >
        <div className="display font-bold text-[22px] tracking-tight text-center mb-1" style={{ color: "var(--text)" }}>
          George<span style={{ color: "var(--accent)" }}>.</span>
        </div>
        <div className="text-[13px] text-center mb-6" style={{ color: "var(--text-dim)" }}>
          {isSignUp ? "Créer un compte" : "Se connecter"}
        </div>

        <label className="block text-[11.5px] mb-1.5" style={{ color: "var(--text-dim)" }}>
          Email
        </label>
        <input
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full mb-3 px-3 py-2 rounded-lg border text-sm outline-none"
          style={{ borderColor: "var(--hairline)", background: "var(--panel-alt)", color: "var(--text)" }}
        />

        <label className="block text-[11.5px] mb-1.5" style={{ color: "var(--text-dim)" }}>
          Mot de passe
        </label>
        <input
          type="password"
          autoComplete={isSignUp ? "new-password" : "current-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full mb-4 px-3 py-2 rounded-lg border text-sm outline-none"
          style={{ borderColor: "var(--hairline)", background: "var(--panel-alt)", color: "var(--text)" }}
        />

        {errorMessage && (
          <div className="text-[12.5px] mb-4" style={{ color: "var(--negative)" }}>
            {errorMessage}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full py-2.5 rounded-lg font-semibold text-[13px] mb-2"
          style={{ background: "var(--accent)", color: "#fff", opacity: isSubmitting ? 0.7 : 1 }}
        >
          {isSubmitting ? "…" : isSignUp ? "S'inscrire" : "Se connecter"}
        </button>

        <button
          type="button"
          onClick={() => setIsSignUp((v) => !v)}
          className="w-full py-1.5 text-[12.5px]"
          style={{ color: "var(--text-dim)" }}
        >
          {isSignUp ? "Déjà un compte ? Se connecter" : "Pas de compte ? Créer un compte"}
        </button>

        <div className="my-4 border-t" style={{ borderColor: "var(--hairline)" }} />

        <button
          type="button"
          onClick={signInWithGoogle}
          className="w-full py-2.5 rounded-lg font-medium text-[13px] border"
          style={{ borderColor: "var(--hairline)", color: "var(--text)" }}
        >
          Continuer avec Google
        </button>
      </form>
    </div>
  );
}
