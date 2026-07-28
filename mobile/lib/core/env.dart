/// URL de base de l'API George — surchargeable via
/// `--dart-define=API_BASE_URL=...` (voir mobile/README.md pour les valeurs
/// par environnement : émulateur Android, simulateur iOS, appareil physique).
/// Même défaut que web/.env.example (`VITE_API_BASE_URL`).
const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
);
