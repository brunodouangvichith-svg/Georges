# Construit l'APK release de mobile/ avec les --dart-define requis toujours
# renseignes - sans ca, mobile/lib/core/env.dart retombe sur des defauts
# vides pour SUPABASE_URL/SUPABASE_ANON_KEY (pas de defaut sense possible),
# et "Continuer avec Google"/"Continuer avec Yahoo" tente de lancer une URL
# sans domaine (PlatformException ACTIVITY_NOT_FOUND) - deja arrive deux
# fois de suite en construisant l'APK a la main sans ce script (voir
# CLAUDE.md, section "Mobile login fixes and additions").
#
# Usage (depuis la racine du depot) :
#   powershell -ExecutionPolicy Bypass -File scripts\build-mobile-release.ps1
#
# La cle anon ci-dessous est volontairement en clair : c'est la cle
# publique/publishable du projet Supabase george-auth (wziegminwqfrhshnrwes),
# concue par Supabase pour etre embarquee cote client - meme cle deja
# compilee telle quelle dans chaque APK distribue.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$ApiBaseUrl = "https://george-api-mmut.onrender.com"
$SupabaseUrl = "https://wziegminwqfrhshnrwes.supabase.co"
$SupabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6aWVnbWlud3FmcmhzaG5yd2VzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU2NDMxODcsImV4cCI6MjEwMTIxOTE4N30.YXpMTXeoK_AHbhAj8UpnKPoxok_zwC21A3RUE-ZHIy0"

Push-Location (Join-Path $RepoRoot "mobile")
try {
    flutter build apk --release `
        --dart-define=API_BASE_URL=$ApiBaseUrl `
        --dart-define=SUPABASE_URL=$SupabaseUrl `
        --dart-define=SUPABASE_ANON_KEY=$SupabaseAnonKey
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "APK : mobile\build\app\outputs\flutter-apk\app-release.apk" -ForegroundColor Green
