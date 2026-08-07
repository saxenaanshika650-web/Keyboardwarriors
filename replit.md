# ABTalks Interview Agent

A minimal FastAPI server that provides the starting point for the ABTalks hackathon interview agent.

## Run & Operate

- `uvicorn main:app --reload` from `artifacts/api-server` — run the API server locally
- `POST /api/interview` — accept a JSON object and return a test response
- `GET /api/healthz` — service health check

## Stack

- Python
- API: FastAPI
- Server: Uvicorn

## Where things live

- `artifacts/api-server/main.py` — FastAPI application and routes
- `artifacts/api-server/requirements.txt` — Python dependencies

## Architecture decisions

- The first milestone intentionally has no AI, database, authentication, or frontend dependencies.

## Product

- The interview endpoint currently confirms that the API is working and echoes the submitted JSON.

## User preferences

- Keep the initial project beginner-friendly and add the AI interviewer only in a later milestone.

## Gotchas

- Run Uvicorn from `artifacts/api-server` so `main:app` resolves correctly.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
