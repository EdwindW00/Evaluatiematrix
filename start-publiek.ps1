# Start de app met inlogbeveiliging aan, klaar om via een tunnel (bijv. tunnelto) publiek
# bereikbaar te maken. Vereist 'secrets.local.ps1' (zie secrets.local.ps1.example) met
# APP_USERNAME/APP_PASSWORD, anders wordt de app zonder inlogscherm gestart — niet
# geschikt om publiek te delen.

Set-Location $PSScriptRoot

$secretsFile = Join-Path $PSScriptRoot "secrets.local.ps1"
if (Test-Path $secretsFile) {
    . $secretsFile
} else {
    Write-Warning "secrets.local.ps1 niet gevonden — de app start ZONDER inlogbeveiliging."
    Write-Warning "Kopieer secrets.local.ps1.example naar secrets.local.ps1 en vul een wachtwoord in voordat je 'm publiek deelt."
}

if (-not (Test-Path ".venv")) {
    Write-Host "Eerste keer: virtuele omgeving aanmaken en dependencies installeren..."
    python -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

Write-Host ""
Write-Host "App start op http://127.0.0.1:5151 — laat dit venster open staan."
Write-Host "Start in een NIEUW PowerShell-venster 'tunnelto add <jouw-domein> 5151' om 'm publiek te maken."
Write-Host ""

& .\.venv\Scripts\python.exe -m app.webapp.run_dev
