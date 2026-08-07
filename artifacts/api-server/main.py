"""Minimal FastAPI application for the ABTalks Interview Agent."""

from typing import Any

from fastapi import FastAPI

app = FastAPI(title="ABTalks Interview Agent")


@app.get("/api/healthz")
async def health_check() -> dict[str, str]:
    """Return a simple health response for the Replit service check."""
    return {"status": "ok"}


@app.post("/api/interview")
async def interview(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept interview input and return a basic test response."""
    return {
        "message": "Interview endpoint is working",
        "received": payload,
    }