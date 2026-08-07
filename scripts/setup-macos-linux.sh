#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/backend"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
[[ -f .env ]] || cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed

cd "$ROOT_DIR/mobile"
[[ -f .env ]] || cp .env.example .env
npm install

printf '\nSetup complete.\n'
printf 'Backend: cd backend && .venv/bin/uvicorn app.main:app --reload\n'
printf 'Mobile:  cd mobile && npm start\n'
