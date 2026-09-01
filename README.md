# resume-and-apply

Basic full-stack scaffold:
- `frontend/` → Next.js app
- `backend/` → FastAPI app

## Run frontend
```bash
cd /home/runner/work/resume-and-apply/resume-and-apply/frontend
npm install
npm run dev
```

## Run backend
```bash
cd /home/runner/work/resume-and-apply/resume-and-apply/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
