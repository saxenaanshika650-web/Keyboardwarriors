"""Minimal FastAPI application for the ABTalks Interview Agent."""

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from breeth_memory import (
    BreethApiError,
    BreethConfigurationError,
    add_interview_memory,
)
from data_loader import find_candidate
from interview_session import (
    REQUIRED_QUESTION_COUNT,
    create_session,
    get_session,
    record_answer,
)
from llm_interviewer import (
    LlmConfigurationError,
    LlmGenerationError,
    generate_feedback,
    generate_next_question,
)

app = FastAPI(title="ABTalks Interview Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://keyboardwarriors-interview.onrender.com",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


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


def _session_context(session) -> dict[str, Any]:
    return {
        "candidate": session.candidate,
        "previous_questions": session.questions,
        "previous_answers": session.answers,
        "question_details": session.question_details,
        "answers": session.answers,
        "questions_asked": session.questions_asked,
        "curriculum_days_covered": session.curriculum_days_covered,
        "topics_covered": session.topics_covered,
    }


def _store_answer_memory(session, question: str, answer: str) -> None:
    try:
        add_interview_memory(
            session_id=session.session_id,
            candidate=session.candidate,
            question=question,
            answer=answer,
        )
    except BreethConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except BreethApiError as error:
        raise HTTPException(
            status_code=502,
            detail="Interview answer was stored, but Breeth memory could not be updated.",
        ) from error


def _generate_and_complete(session) -> dict[str, Any]:
    if session.feedback is not None:
        return session.feedback
    try:
        feedback = generate_feedback(_session_context(session))
    except LlmConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except LlmGenerationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    session.complete(feedback)
    return feedback


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

        try:
            session = create_session(session_id, payload["candidate"])
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "sessionId": session.session_id,
            "status": session.status,
            "question": session.questions[-1],
            "questionsAsked": session.questions_asked,
            "requiredQuestions": REQUIRED_QUESTION_COUNT,
        }

    if has_message:
        if not isinstance(payload["message"], str):
            raise HTTPException(status_code=400, detail="message must be a string")

        session = get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.status == "completed":
            raise HTTPException(status_code=409, detail="Interview session is already completed")

        previous_question = session.questions[-1]
        try:
            record_answer(session, payload["message"])
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        _store_answer_memory(session, previous_question, payload["message"])

        if session.is_ready_for_feedback:
            return {
                "sessionId": session.session_id,
                "status": session.status,
                "message": "Required interview questions answered. Call /api/interview/{session_id}/complete for structured feedback.",
                "questionsAsked": session.questions_asked,
                "answersRecorded": session.answered_questions,
                "requiredQuestions": REQUIRED_QUESTION_COUNT,
            }

        try:
            next_question = generate_next_question(_session_context(session))
        except LlmConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except LlmGenerationError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

        try:
            session.add_question(
                question=next_question["question"],
                day_number=next_question["curriculum_day"],
                question_type=next_question["question_type"],
                reasoning=next_question["reasoning"],
            )
        except ValueError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return {
            "sessionId": session.session_id,
            "status": session.status,
            **next_question,
            "questionsAsked": session.questions_asked,
            "requiredQuestions": REQUIRED_QUESTION_COUNT,
        }

    raise HTTPException(
        status_code=400,
        detail="Provide candidate when starting or message when answering",
    )


@app.post("/api/interview/{session_id}/complete")
async def complete_interview(session_id: str) -> dict[str, Any]:
    """Complete an interview and return structured feedback."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if not session.is_ready_for_feedback:
        raise HTTPException(
            status_code=409,
            detail=f"Interview requires {REQUIRED_QUESTION_COUNT} answered questions before feedback.",
        )

    feedback = _generate_and_complete(session)
    return {
        "sessionId": session.session_id,
        "status": session.status,
        "questionsAsked": session.questions_asked,
        "answersRecorded": session.answered_questions,
        "feedback": feedback,
    }
