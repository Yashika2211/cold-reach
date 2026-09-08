# ColdReach

Personal cold outreach platform: research openings, find the right contact, generate
genuinely personalized cold emails with an LLM, review every one, and send them on a
throttled, reply-aware schedule. Single-operator tool — see the project brief for the
full design.

**Status:** Phase 3 (Sending core) complete. See `BUILD PHASES` in the project brief for
what's next.

Log in at `/login` with the `ADMIN_EMAIL`/`ADMIN_PASSWORD` from `api/.env` (seeded via
`make seed`). Add a sending account under Settings — an SMTP account with a Gmail app
password is the fastest path (see below); Gmail OAuth needs a Google Cloud project first.

### Connecting a Gmail account to actually send

**SMTP with an app password (fastest):**
1. Turn on 2-Step Verification on the Google account, if it isn't already:
   https://myaccount.google.com/security
2. Generate an app password: https://myaccount.google.com/apppasswords → app "Mail",
   device "Other" → copy the 16-character password.
3. In ColdReach, go to Settings → "Add SMTP account". Host `smtp.gmail.com`, port `587`,
   username = the Gmail address, password = the app password just generated.
4. Click "Test" to confirm the connection, then "Send test" to send yourself a real email
   and confirm it lands in Gmail Sent.

**Gmail OAuth (recommended long-term, more setup):** requires a Google Cloud project with
the Gmail API enabled, an OAuth consent screen, and a Web OAuth client with redirect URI
`http://localhost:8000/sending-accounts/oauth/gmail/callback`. Put the client ID/secret in
`api/.env` as `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET`, restart the API, then
use "Connect Gmail" in Settings. Full click-by-click steps land in the Phase 10 setup guide;
ask if you want them now.

## Stack

- **API**: Python 3.11, FastAPI, SQLAlchemy 2.x (async), Alembic, Pydantic v2
- **Worker/Scheduler**: Celery + Celery Beat, Redis 7
- **DB**: PostgreSQL 16
- **Web**: Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui, TanStack Query
- **Infra**: Docker Compose

## Two ways to run this

**Native dev (default, fast reload)** — Postgres and Redis run in Docker; the API,
worker, beat, and web app run directly on your machine. This is what you want day to day.

**Full Docker stack (parity/deploy target)** — all six services (`api`, `worker`,
`beat`, `web`, `postgres`, `redis`) run in containers via `docker-compose.yml`. Use this
to sanity-check what production will actually run, or if you'd rather not install
Python/Node locally.

## Prerequisites

- [Colima](https://github.com/abiquo/colima) (or Docker Desktop / OrbStack) + `docker` +
  `docker compose` — `brew install colima docker docker-compose`, then `colima start`
- Python 3.11 — `brew install python@3.11`
- Node.js 20+ (any recent LTS works)

## Quickstart — native dev

```bash
make install       # creates api/.venv, installs Python + Node deps
cp .env.example .env
cp api/.env.example api/.env
cp web/.env.local.example web/.env.local
# Generate a Fernet key and put it in api/.env as CREDENTIALS_ENCRYPTION_KEY:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

make dev-up         # starts postgres + redis in Docker
make migrate         # applies Alembic migrations
make seed            # creates the admin user from api/.env (ADMIN_EMAIL/ADMIN_PASSWORD)

# In separate terminals:
make api              # FastAPI on :8000
make worker            # Celery worker (no tasks registered yet until Phase 6)
make beat               # Celery beat
make web                  # Next.js on :3000
```

Visit `http://localhost:3000` — the homepage's "API connection" card should show `ok`.

Run tests: `make test` (creates a `coldreach_test` database and runs `pytest`).

## Quickstart — full Docker stack

```bash
cp .env.example .env    # fill in secrets as needed; defaults work for local use
make up                  # builds and starts all 6 services
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed
```

Visit `http://localhost:3000`. `make logs` tails all services. `make down` stops them.

## Project structure

```
api/                  FastAPI app, SQLAlchemy models, Alembic migrations, Celery tasks
  app/
    core/             settings, logging, security (password hashing, Fernet encryption)
    db/                base classes, async session
    models/           the full data model (§4 of the brief)
    api/routes/        FastAPI routers
    workers/           Celery tasks
  alembic/             migrations
  scripts/             seed.py, create_test_db.py
  tests/                pytest suite (runs against a real Postgres test DB)
web/                  Next.js 14 App Router app
  src/app/              routes
  src/components/ui/   shadcn/ui components (Radix-based, pinned to shadcn CLI v2.10.0 —
                        the CLI's current default pulls in Base UI instead of Radix,
                        which is too new/undocumented to build a production app on)
docker-compose.yml     full 6-service stack (parity/deploy target)
docker-compose.dev.yml  postgres + redis only (native dev flow)
Makefile                 all the commands above
```

## Notes on choices made without explicit spec

- **Python dependency management**: plain `requirements.txt` / `requirements-dev.txt`
  rather than Poetry/uv — fewer moving parts, no extra tooling to install.
- **Password hashing**: raw `bcrypt` rather than `passlib` — `passlib` is unmaintained
  and breaks on current `bcrypt` releases (`AttributeError: module 'bcrypt' has no
  attribute '__about__'`).
- **shadcn/ui pinned to v2.10.0**: the default `shadcn@latest` (v4.x) now scaffolds
  components on Base UI instead of Radix primitives. Radix is the well-documented,
  battle-tested option; Base UI is too new for a production build right now.
- **`AdminUser` model added** in Phase 1 even though it's not in the brief's §4 data
  model list — §10 (Security) requires session-based login with one admin user seeded
  from env, and adding the table now avoids a later migration.
- **Tests run against a real Postgres database** (`coldreach_test`), not sqlite/mocks —
  matches "pin the stack, don't substitute" and avoids UUID/JSONB dialect mismatches.
