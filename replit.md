# ABTalks Interview Agent

A minimal FastAPI server that provides the starting point for the ABTalks hackathon interview agent.

## Run & Operate

- `uvicorn main:app --reload` from `artifacts/api-server` — run the API server locally
- `POST /api/interview` — start an in-memory interview or submit an answer
- `GET /api/healthz` — service health check

## Stack

- Python
- API: FastAPI
- Server: Uvicorn

## Where things live

- `artifacts/api-server/main.py` — FastAPI application and routes
- `artifacts/api-server/data_loader.py` — local JSON loading and lookup functions
- `artifacts/api-server/interview_session.py` — in-memory interview session state
- `artifacts/api-server/data/candidates.json` — candidate data copied from the uploaded file
- `artifacts/api-server/data/curriculum.json` — curriculum data copied from the uploaded file
- `artifacts/api-server/requirements.txt` — Python dependencies

## Architecture decisions

- The first milestone intentionally has no AI, database, authentication, or frontend dependencies.

## Product

- Interview sessions are intentionally in-memory and reset when the server restarts.
- The first two temporary questions cover curriculum days 7 and 8.
- The temporary candidate test route returns data from the local JSON files.

## User preferences

- Keep the initial project beginner-friendly and add the AI interviewer only in a later milestone.

## Gotchas

- Run Uvicorn from `artifacts/api-server` so `main:app` resolves correctly.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
