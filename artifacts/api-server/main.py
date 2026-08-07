"""Minimal FastAPI application for the ABTalks Interview Agent."""

from typing import Any

from fastapi import FastAPI, HTTPException

from data_loader import find_candidate
from interview_session import create_session, get_session, record_answer

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
    """Start an interview or record an answer in an existing session."""
    session_id = payload.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required")

    has_candidate = "candidate" in payload
    has_message = "message" in payload

    if has_candidate and has_message:
        raise HTTPException(
            status_code=400,
            detail="Provide candidate when starting or message when answering",
        )

    if has_candidate:
        if not isinstance(payload["candidate"], dict):
            raise HTTPException(status_code=400, detail="candidate must be an object")
        if get_session(session_id) is not None:
            raise HTTPException(status_code=409, detail="Session already exists")

        session = create_session(session_id, payload["candidate"])
        return {
            "sessionId": session.session_id,
            "status": session.status,
            "question": session.questions[-1],
        }

    if has_message:
        if not isinstance(payload["message"], str):
            raise HTTPException(status_code=400, detail="message must be a string")

        session = get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")

        next_question = record_answer(session, payload["message"])
        return {
            "sessionId": session.session_id,
            "status": session.status,
            "question": next_question,
        }

    raise HTTPException(
        status_code=400,
        detail="Provide candidate when starting or message when answering",
    )