import { createClient } from "@supabase/supabase-js";

// Fournisseur d'identité pour le portail d'accès simple (Phase 9, voir
// CLAUDE.md section Auth) — aucune table applicative de George ne vit ici,
// uniquement l'authentification. Pas de fallback par défaut (contrairement
// à VITE_API_BASE_URL) : ces deux valeurs n'ont pas de défaut sensé.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// `createClient` lève une exception SYNCHRONE si l'URL/la clé manquent
// (vérifié en direct : "supabaseUrl is required.") — un simple import de ce
// module planterait alors toute l'app avec un écran blanc plutôt qu'un
// message clair. `isSupabaseConfigured` permet à AuthGate.jsx d'afficher un
// message explicite à la place, même principe que
// `api/auth.py:SupabaseUnavailableError` côté backend.
export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

export const supabase = isSupabaseConfigured ? createClient(supabaseUrl, supabaseAnonKey) : null;
