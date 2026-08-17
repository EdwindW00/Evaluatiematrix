Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) {
    Write-Host "Eerste keer: virtuele omgeving aanmaken en dependencies installeren..."
    python -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}
& .\.venv\Scripts\python.exe -m app.desktop
