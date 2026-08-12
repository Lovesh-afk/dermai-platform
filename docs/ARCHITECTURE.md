# DermAI Platform — Architecture (Phase 1)

## Scope of this phase

Phase 1 delivers the repository skeleton, the backend's clean-architecture
foundation, the auth/RBAC data model, and local dev infrastructure
(Docker Compose). It does **not** yet include the AI training pipeline,
chatbot, booking, billing, or frontend pages beyond the shell — those are
later phases and depend on the foundation laid here.

## High-level system design

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Next.js     │◄────►│  FastAPI (REST)   │◄────►│  PostgreSQL      │
│  Frontend    │      │  + Celery workers │      │  Redis (cache/   │
│  (patient/   │      │                   │      │  broker)         │
│  doctor/     │      └────────┬─────────┘      └─────────────────┘
│  admin UIs)  │               │
└─────────────┘               ▼
                      ┌──────────────────┐
                      │  AI inference svc │  (separate process/
                      │  (ONNX Runtime)   │   container in Phase 7)
                      └──────────────────┘
```

Single FastAPI app for Phase 1–6 (auth, portals, booking) with a
separately deployable AI inference module from Phase 7 onward. This
keeps early phases simple while leaving room to split inference into
its own scaled service later without a rewrite (it already lives in
`ai/` and is called via an internal service boundary, not imported
directly into request handlers).

## Why these choices

**FastAPI over Django** — async-first, native OpenAPI docs, and a
much better fit for an app whose core is a mix of CRUD + ML inference
+ background jobs. Trade-off: less batteries-included than Django
(no built-in admin), so we build a lightweight admin portal in the
frontend instead of relying on Django admin.

**PostgreSQL + pgvector over a separate vector DB** — keeps
operational surface area smaller for a hospital-facing product where
every extra managed service is another HIPAA/compliance touchpoint.
`pgvector` is used for the chatbot's RAG embeddings (Phase 9); FAISS
remains an option for local/offline experimentation only.

**Celery + Redis + RabbitMQ** — Redis is used for cache and as the
Celery result backend; RabbitMQ is the broker. Reasoning: RabbitMQ
gives more reliable delivery guarantees for tasks that matter
clinically (e.g. "send doctor a new-prediction alert") than
Redis-as-broker would, at the cost of one more moving part.

**Multi-tenancy: row-level (shared schema + `hospital_id` on every
tenant-scoped table) rather than schema-per-tenant** — much simpler
migrations and connection pooling for the expected tenant count
(hospitals/clinics, not thousands of tenants). Trade-off: requires
disciplined use of a tenant-scoping dependency on every query (see
`app/core/tenancy.py` once Phase 3 lands) to avoid cross-tenant leaks.
If tenant count or isolation requirements grow significantly, this is
the first thing to revisit.

**JWT access + refresh tokens, RBAC via a `role` + `permissions`
model** stored in Postgres rather than hardcoded roles — lets
hospital admins define custom staff roles later without a code
change. MFA (TOTP) is scaffolded in Phase 2, not this phase.

**Alembic for migrations, SQLAlchemy 2.0 style (typed, `Mapped[...]`)**
— standard, explicit, and plays well with Pydantic v2 schema
generation.

## Folder structure (top level)

```
frontend/         Next.js app (App Router), TypeScript, Tailwind, shadcn/ui
backend/          FastAPI service — see backend/README.md
ai/               Training pipelines, preprocessing, inference wrappers
datasets/         Dataset download/prep scripts (data itself is gitignored)
docs/             Architecture, API docs, runbooks
infrastructure/   Docker, Nginx, Terraform, k8s manifests
scripts/          One-off ops/dev scripts
tests/            Cross-cutting/integration tests (e2e across services)
```

## Backend internal layering (clean architecture)

```
app/api/v1/endpoints/   → HTTP layer only: request/response, no business logic
app/schemas/            → Pydantic request/response models
app/services/           → Business logic, orchestration
app/models/             → SQLAlchemy ORM models
app/db/                 → Session/engine setup, base class
app/core/               → Config, security, dependencies, exceptions
app/tasks/              → Celery task definitions
```

Rule enforced from Phase 1 on: endpoints never touch the DB session or
call SQLAlchemy directly — they call a service function, which is the
unit tests target. This is what keeps "add a new portal" additive
rather than a refactor later.

## Security posture (Phase 1 baseline)

- Passwords hashed with bcrypt (via `passlib`)
- JWT signed with a rotateable secret from env (`SECRET_KEY`), short-lived
  access tokens (15 min) + longer refresh tokens (7 days) stored hashed
- All config via environment variables (`.env`, never committed —
  `.env.example` provided)
- CORS locked to explicit origins, not `*`
- Structured JSON logging from the start (not added later) so audit
  logs are a first-class citizen given the healthcare context

## What's deliberately deferred

- Image upload / S3 signed URLs → Phase 4 (Patient Portal)
- AI model + Grad-CAM/ONNX → Phase 7
- RAG chatbot / pgvector usage → Phase 9
- Stripe/Razorpay → Phase 13
- Kubernetes manifests are stubbed only; real ones come with Phase 15

## Open trade-off to confirm with you before Phase 2

MFA: TOTP (Google Authenticator-style) is the standard choice for a
healthcare app and what's scaffolded by default. If you'd rather do
SMS-based OTP instead (simpler for less technical clinic staff, but
weaker security and costs per SMS), say so before Phase 2 — it
changes the `core/security.py` design.
