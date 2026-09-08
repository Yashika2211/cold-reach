.PHONY: install dev-up dev-down api worker beat web migrate makemigrations seed test up down logs

# --- Native dev flow (default): postgres + redis in Docker, everything else on the host ---

install:
	cd api && python3.11 -m venv .venv && .venv/bin/pip install --upgrade pip -q && .venv/bin/pip install -r requirements-dev.txt
	cd web && npm install

dev-up:
	docker compose -f docker-compose.dev.yml up -d
	@echo "postgres + redis are up. In separate terminals run: make api / make worker / make beat / make web"

dev-down:
	docker compose -f docker-compose.dev.yml down

api:
	cd api && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd api && .venv/bin/celery -A app.celery_app worker --loglevel=info

beat:
	cd api && .venv/bin/celery -A app.celery_app beat --loglevel=info

web:
	cd web && npm run dev

migrate:
	cd api && .venv/bin/alembic upgrade head

makemigrations:
	cd api && .venv/bin/alembic revision --autogenerate -m "$(m)"

seed:
	cd api && .venv/bin/python -m scripts.seed

test:
	cd api && .venv/bin/python -m scripts.create_test_db && .venv/bin/pytest -v

# --- Full docker-compose parity/deploy stack (all 6 services) ---

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f
