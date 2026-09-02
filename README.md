# resume-and-apply

Basic full-stack scaffold:
- `frontend/` → Next.js app (runs on http://localhost:3000)
- `backend/` → FastAPI app (runs on http://localhost:8000)

The frontend proxies API calls to the backend via Next.js rewrites
(`frontend/next.config.mjs`): any request to `/api/*` on the frontend is
forwarded server-side to the backend, so the browser only ever talks to
`localhost:3000` and no CORS setup is needed. The backend URL used for this
proxying is controlled by the `BACKEND_INTERNAL_URL` env var
(see `frontend/.env.example`).

## Run with Docker (recommended)

```bash
docker compose up --build
```

This builds and starts both services with hot reload — source changes on
your machine are picked up automatically. Then open http://localhost:3000 —
it should show "Backend is running".

## Run without Docker

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000 — it should show "Backend is running".
