# Demarre l'infra Docker (Postgres/Redis/MinIO/Adminer), l'API FastAPI et le
# serveur web Vite, tous en arriere-plan (le terminal reste libre une fois le
# script termine).
#
# Usage (depuis la racine du depot) :
#   powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1
#
# Prerequis (voir README.md) : environnement Python deja cree dans .venv/
# avec `pip install -e ".[dev]"`, et `npm install` deja lance dans web/.
# Idempotent : ne relance pas ce qui ecoute deja sur les ports 8000/5173.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$LogDir = Join-Path $RepoRoot ".dev-logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-PortListening($Port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

# Un port 8000 "deja en ecoute" ne veut pas forcement dire que c'est
# l'API de George : une autre application Python/uvicorn sans rapport
# (rencontre reelle : un projet nomme "Jaz") peut deja occuper ce port.
# Verifie donc /health et son corps JSON attendu, pas juste que le port
# repond.
function Test-GeorgeApiRunning {
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3 -ErrorAction Stop
        return $response.status -eq "ok"
    } catch {
        return $false
    }
}

function Test-DockerUp {
    try { docker info *> $null } catch {}
    return $LASTEXITCODE -eq 0
}

Write-Host "== Docker ==" -ForegroundColor Cyan
if (-not (Test-DockerUp)) {
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerExe)) {
        Write-Error "Docker Desktop introuvable a '$dockerExe'. Installez-le ou ajustez ce chemin dans le script."
        exit 1
    }
    Write-Host "Demarrage de Docker Desktop..."
    Start-Process $dockerExe
    $waited = 0
    while (-not (Test-DockerUp) -and $waited -lt 180) {
        Start-Sleep -Seconds 5
        $waited += 5
    }
    if (-not (Test-DockerUp)) {
        Write-Error "Docker n'a pas demarre apres 3 minutes - reessayez une fois Docker Desktop pret."
        exit 1
    }
}
Write-Host "Docker pret."

Write-Host "== Infra (Postgres/Redis/MinIO/Adminer) ==" -ForegroundColor Cyan
Push-Location (Join-Path $RepoRoot "infra")
docker compose up -d
Pop-Location

Write-Host "== API FastAPI ==" -ForegroundColor Cyan
if (Test-GeorgeApiRunning) {
    Write-Host "Deja en ecoute sur le port 8000 - rien a faire."
} elseif (Test-PortListening 8000) {
    Write-Error "Le port 8000 est occupe par une autre application (pas l'API de George - /health ne repond pas comme attendu). Liberez le port avant de relancer ce script."
    exit 1
} else {
    $pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        Write-Error "Environnement Python introuvable ($pythonExe). Voir README.md, section 2."
        exit 1
    }
    Start-Process -FilePath $pythonExe `
        -ArgumentList "-m", "uvicorn", "api.main:app", "--port", "8000" `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput (Join-Path $LogDir "api.log") `
        -RedirectStandardError (Join-Path $LogDir "api.err.log") `
        -WindowStyle Hidden
    Write-Host "API demarree (logs : $LogDir\api.log / api.err.log)."
}

Write-Host "== Serveur web Vite ==" -ForegroundColor Cyan
if (Test-PortListening 5173) {
    Write-Host "Deja en ecoute sur le port 5173 - rien a faire."
} else {
    $webDir = Join-Path $RepoRoot "web"
    if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
        Write-Error "Dependances web introuvables. Lancez 'npm install' dans web/ (voir README.md, section 10)."
        exit 1
    }
    Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" `
        -WorkingDirectory $webDir `
        -RedirectStandardOutput (Join-Path $LogDir "web.log") `
        -RedirectStandardError (Join-Path $LogDir "web.err.log") `
        -WindowStyle Hidden
    Write-Host "Serveur web demarre (logs : $LogDir\web.log / web.err.log)."
}

Write-Host ""
Write-Host "API  : http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Web  : http://localhost:5173" -ForegroundColor Green
