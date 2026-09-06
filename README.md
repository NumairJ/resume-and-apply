# Resume and Apply

A locally-run tool that reads a job posting, tailors your résumé to it from experience you
actually have, and tracks the application. Next.js and TypeScript on the front, FastAPI and
Postgres behind, Anthropic's API for the parts that need a language model.

The interesting problem here is not "call a model and print the answer". It is making the output
**trustworthy enough to send to an employer** — which is where nearly all of the design effort
went, and what most of this README is about.

---

## What it does

1. **Paste a job posting URL.** Extraction runs cheapest-first: a recognised job board is read from
   its JSON API, a page carrying `schema.org/JobPosting` data is parsed directly, and only what is
   left over reaches a model. A page that is not a job posting is rejected, with reasons, before a
   token is spent.
2. **Generate.** Your stored experience is tailored to the posting, then validated against your
   profile. A draft that fails validation is retried with the specific failure named, and never
   returned quietly. Able to download the résumé after generation.
3. **Track it.** The résumé becomes a PDF on a Docker volume and an application you can move
   through saved → applied → interviewing → offer / rejected / withdrawn.

---

## Running it

You need Docker, and an [Anthropic API key](https://console.anthropic.com/) if you want the steps
that use a model. Extraction from a supported job board works without one.

```bash
cp .env.example .env      # then edit if you like; the defaults work as-is
docker compose up --build

# In another terminal, once the stack is healthy. The database starts empty and
# migrations are not run automatically, so this step is required, not optional.
docker compose exec backend alembic upgrade head
```

Three services come up: Postgres, the FastAPI backend, and the Next.js frontend, which waits for
the backend's healthcheck, which waits for Postgres to actually accept connections.

Now open <http://localhost:3000>, and:

- **Fill in `/settings` first.** It is the only thing a generated résumé is allowed to draw on, so
  an empty profile means there is nothing to tailor.
- **Add your API key** with the button in the top right. It is held in your browser's
  `localStorage`, sent as a header with each request, and never written to the server's database or
  logs. There is also an optional `ANTHROPIC_API_KEY` in `.env` as a convenience for local
  development.

<details>
<summary>Running without Docker</summary>

You still need Postgres. `docker-compose.yml` publishes it on `127.0.0.1:5432`, so the simplest
mixed setup is to run just the database in Docker and the two apps on the host.

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
cd frontend && npm install && npm run dev
```

`DATABASE_URL` and `BACKEND_INTERNAL_URL` in `.env` already hold the bare-metal values; Compose
overrides both to point at service names. Note that PDF rendering needs WeasyPrint's system
libraries (pango, cairo, and fonts), which the backend image installs for you and your machine
probably does not have.

</details>

---

## Design decisions

### The model cannot invent an employer

This is the load-bearing idea. The model **never writes a company, job title, school, degree or
date**. It returns short reference labels naming which of your real entries to use, plus rewritten
bullet text:

```jsonc
{
  "summary": "…",
  "experiences": [
    { "source": "E1", "bullets": [{ "source": "E1B2", "text": "Migrated the billing database…" }] }
  ],
  "skills": ["Python", "Postgres"]
}
```

The server resolves `E1` and `E1B2` against the database and fills every factual field from the
rows it finds. Fabrication in structured fields is therefore **impossible by construction** rather
than something to detect afterwards — and the guardrails are left with only the free text they can
actually police.

Labels are short tokens rather than UUIDs because models copy `E1B2` reliably and 36 characters of
hex unreliably, and a mis-copied identifier would look like fabrication when it was a typo.

### Guardrails are hardcoded, never LLM-judged

Asking a model whether another model made something up inherits the same failure mode. Every check
is decidable:

| Check | Rejects |
|---|---|
| Reference integrity | A label resolving to no profile row — which is what an invented employer looks like in this schema |
| Bullet traceability | A rewrite sharing too few meaningful words with the source bullet it cites |
| Metric integrity | A figure that is not in the bullet being rewritten — including one computed from it, or borrowed from a sibling |
| Skill membership | A skill the profile's own text never claims — a whole-word match, not a judgement |
| Date sanity | A year in prose that the claiming experience's own date range does not cover, and any future date |

Violations are fed back into a retry naming exactly what was wrong, up to two attempts, and a
generation that still fails surfaces as a `422` listing the violations rather than returning bad
output. The guardrail suite is the most valuable test set in the repo: it is fed deliberately
fabricated résumés and must reject every one — *and* must accept a legitimately rephrased bullet,
without which it could be trivially rejecting everything and still look green.

### Duplicate detection is a warning, never a constraint

Company and title are normalised — corporate suffixes and seniority noise stripped, location
reduced to a city or `remote` token — and hashed into a fingerprint. When you extract a posting
matching one you applied to in the last 90 days, the UI says so and offers to continue anyway.

That column is indexed but deliberately **not unique**. Reapplying after a rejection is legitimate,
and a false positive on a unique index would block a real application — far worse than a duplicate
row.

### Abandoned postings expire themselves

Extraction inserts a posting with `expires_at = now() + 24h`. Tracking it clears that, making it
permanent; deleting the application restores it. Cleanup is an opportunistic sweep at the top of the
extract endpoint rather than a scheduled job — it runs a few times a day at most, and sweep-on-write
has no background machinery that can fail silently.

---

## Testing

```bash
docker compose exec backend python -m pytest    # 296 tests
docker compose exec frontend npm test           # 54 tests
```

Both suites run **inside the containers** — the host is not expected to have Python dependencies,
and the frontend suite needs a newer Node than the host may have. Neither suite touches the network:
a `FakeLLMProvider` stands in for the model in the backend, and MSW intercepts every request in the
frontend, configured so that an unmocked call fails the test rather than escaping.

`FakeLLMProvider` is deliberately **not** registered as a selectable provider. A fake reachable in
production would serve invented job details and invented résumés as though they were real — far
worse than an honest failure.

There is also one end-to-end test, and it is opt-in because it spends money:

```bash
cd frontend && npm run test:e2e     # ~40s, one real API call
```

It drives a real browser through the whole path — paste, correct, generate, track, download — and
asserts the downloaded bytes are a real PDF. Mocking the model there would leave the integration it
exists to protect covered by nothing. It seeds its own profile data and removes it afterwards.

---

## Layout

```
backend/
  routers/      thin: validate, call a service, return a schema
  services/     business logic — extraction, tailoring, guardrails, rendering
  repositories/ data access, no business logic, never commits
  models/       SQLAlchemy          schemas/  Pydantic
  prompts/      versioned prompt templates, recorded on every generated résumé
  templates/    the Jinja2 résumé
frontend/
  app/          four routes: landing, /apply, /applications, /settings
  components/   the UI
  lib/api.ts    the one typed client — every backend call goes through it
```

---

## Future features

What this is growing into, roughly in the order it matters. Written by me not Claude.

- **More Providers** — I want to add more LLM providers like OpenAI and also local llm support. I want local LLM support to keep user's resume details to be private on their own machine instead of their data being fed into corporation's training set.
- **Enhanced Guardrail System** — Currently the guardrail system checks for simple fabrications like years, numbers and skills. I want the system to also detect companies and actions that are fabricated by the LLM with a low false positive rate.
- **Interactable Preview** — I want the resume preview to be interactable by the user letting them edit or flag parts of the resume to be regenerated with the fix in mind. This could be a potential fix or add on to the future enchanced guardrail.

