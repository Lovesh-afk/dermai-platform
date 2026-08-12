# DermAI Platform

Production-grade AI dermatology SaaS for hospitals and clinics — patient
skin-image analysis (with disclaimers), AI chatbot, doctor booking, and
multi-tenant hospital dashboards.

**Status: Phase 1 — repository setup, auth/RBAC foundation.** See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design
and the reasoning behind each major tech choice, and
[`CLAUDE_MASTER_PROMPT.md`](CLAUDE_MASTER_PROMPT.md) for the full product
spec and phase roadmap this build follows.

## What's here right now

- `backend/` — FastAPI service. Clean-architecture layering (API → services
  → models), JWT auth, RBAC/multi-tenancy data model, Alembic migrations,
  unit tests (all passing).
- `frontend/` — Next.js 14 (App Router) + TypeScript + Tailwind shell.
- `docker-compose.yml` — Postgres, Redis, RabbitMQ, backend, Celery worker,
  frontend, wired together for local dev.
- `docs/ARCHITECTURE.md` — architecture + explicit trade-offs for this phase.
- `.github/workflows/backend-ci.yml` — runs backend tests on every PR.

## Quickstart (local dev)

```bash
# 1. Copy env files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# edit backend/.env — set a real SECRET_KEY and DB credentials

# 2. Bring the stack up
docker compose up --build

# 3. Run migrations + seed platform roles (first time only)
docker compose exec backend alembic revision --autogenerate -m "init"
docker compose exec backend alembic upgrade head
docker compose exec backend python /app/../scripts/seed_roles.py
```

- Backend: http://localhost:8000 (docs at `/api/docs`)
- Frontend: http://localhost:3000

## Running backend tests without Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
SECRET_KEY=test DATABASE_URL=sqlite:///./test.db pytest tests/ -v
```

## Roadmap

See `CLAUDE_MASTER_PROMPT.md` for the full 16-phase plan. Next up: Phase 2
(MFA, session/refresh-token revocation, password reset flow).
