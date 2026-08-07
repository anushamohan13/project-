$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot

Set-Location "$RootDir\backend"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.seed

Set-Location "$RootDir\mobile"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm install

Write-Host ""
Write-Host "Setup complete."
Write-Host "Backend: cd backend; .\.venv\Scripts\uvicorn.exe app.main:app --reload"
Write-Host "Mobile:  cd mobile; npm start"
