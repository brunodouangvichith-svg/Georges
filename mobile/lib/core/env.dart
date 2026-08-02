/// URL de base de l'API George — surchargeable via
/// `--dart-define=API_BASE_URL=...` (voir mobile/README.md pour les valeurs
/// par environnement : émulateur Android, simulateur iOS, appareil physique).
/// Même défaut que web/.env.example (`VITE_API_BASE_URL`).
const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
);

/// Projet Supabase utilisé comme fournisseur d'identité (Phase 9 — portail
/// d'accès simple, voir CLAUDE.md section Auth). Pas de valeur par défaut
/// sensée pour ces deux-là (contrairement à `apiBaseUrl`) : à fournir via
/// `--dart-define=SUPABASE_URL=...`/`--dart-define=SUPABASE_ANON_KEY=...`,
/// même convention que web/.env.example (`VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY`).
const supabaseUrl = String.fromEnvironment('SUPABASE_URL', defaultValue: '');
const supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY', defaultValue: '');
