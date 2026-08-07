"""Minimal FastAPI application for the ABTalks Interview Agent."""

from typing import Any

from fastapi import FastAPI, HTTPException

from data_loader import find_candidate

app = FastAPI(title="ABTalks Interview Agent")


@app.get("/api/healthz")
async def health_check() -> dict[str, str]:
    """Return a simple health response for the Replit service check."""
    return {"status": "ok"}


@app.get("/api/test/candidate/{candidate_id}")
async def test_candidate(candidate_id: str) -> dict[str, Any]:
    """Return one candidate from the local JSON data."""
    candidate = find_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return candidate


@app.post("/api/interview")
async def interview(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept interview input and return a basic test response."""
    return {
        "message": "Interview endpoint is working",
        "received": payload,
    }