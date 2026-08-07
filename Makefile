.PHONY: setup backend mobile test migrate seed db

setup:
	./scripts/setup-macos-linux.sh

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload

mobile:
	cd mobile && npm start

test:
	cd backend && .venv/bin/python -m pytest

migrate:
	cd backend && .venv/bin/alembic upgrade head

seed:
	cd backend && .venv/bin/python -m app.seed

db:
	docker compose up -d db
