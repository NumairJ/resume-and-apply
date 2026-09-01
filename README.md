# resume-and-apply

Basic full-stack scaffold:
- `frontend/` → Next.js app (runs on http://localhost:3000)
- `backend/` → FastAPI app (runs on http://localhost:8000)

Run both servers at the same time — the frontend fetches the backend's status
on page load and displays it, using the `NEXT_PUBLIC_API_URL` env var
(see `frontend/.env.example`) to know where the backend lives.

## Run backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Run frontend
```bash
cd frontend
cp .env.example .env.local  # only needed once
npm install
npm run dev
```

Then open http://localhost:3000 — it should show "Backend is running".
