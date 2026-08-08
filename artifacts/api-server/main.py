"""Minimal FastAPI application for the ABTalks Interview Agent."""

from typing import Any

from fastapi import FastAPI, HTTPException

from breeth_memory import (
    BreethApiError,
    BreethConfigurationError,
    add_interview_memory,
)
from data_loader import find_candidate
from interview_session import create_session, get_session, record_answer
from llm_interviewer import (
    LlmConfigurationError,
    LlmGenerationError,
    generate_next_question,
)

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

        previous_question = session.questions[-1]
        record_answer(session, payload["message"])
        try:
            add_interview_memory(
                session_id=session.session_id,
                candidate=session.candidate,
                question=previous_question,
                answer=payload["message"],
            )
        except BreethConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except BreethApiError as error:
            raise HTTPException(
                status_code=502,
                detail="Interview answer was stored, but Breeth memory could not be updated.",
            ) from error

        context = {
            "candidate": session.candidate,
            "previous_questions": session.questions,
            "previous_answers": session.answers,
            "questions_asked": session.questions_asked,
        }
        try:
            next_question = generate_next_question(context)
        except LlmConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except LlmGenerationError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

        session.add_question(
            question=next_question["question"],
            day_number=next_question["curriculum_day"],
            question_type=next_question["question_type"],
            reasoning=next_question["reasoning"],
        )
        return {
            "sessionId": session.session_id,
            "status": session.status,
            **next_question,
        }

    raise HTTPException(
        status_code=400,
        detail="Provide candidate when starting or message when answering",
    )