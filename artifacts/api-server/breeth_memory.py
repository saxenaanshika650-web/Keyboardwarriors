"""Small direct REST client for Breeth interview memory."""

import os
from typing import Any

import httpx


BREETH_BASE_URL = "https://api.thebreeth.com"


class BreethConfigurationError(RuntimeError):
    """Raised when the Breeth API key is not configured."""


class BreethApiError(RuntimeError):
    """Raised when Breeth returns an unsuccessful response."""


def _api_key() -> str:
    """Read the Breeth API key without exposing it."""
    api_key = os.getenv("BREETH_API_KEY")
    if not api_key:
        raise BreethConfigurationError(
            "BREETH_API_KEY is not configured. Add it to the environment before using Breeth memory."
        )

    return api_key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send one authenticated JSON request to Breeth."""
    try:
        response = httpx.post(
            f"{BREETH_BASE_URL}{path}",
            headers=_headers(),
            json=payload,
            timeout=20.0,
        )
    except httpx.RequestError as error:
        raise BreethApiError("Could not connect to Breeth.") from error

    if response.is_error:
        raise BreethApiError(
            f"Breeth returned HTTP {response.status_code} for {path}."
        )

    try:
        result = response.json()
    except ValueError as error:
        raise BreethApiError(f"Breeth returned invalid JSON for {path}.") from error

    if not isinstance(result, dict):
        raise BreethApiError(f"Breeth returned an unexpected response for {path}.")

    return result


def _group_id(session_id: str) -> str:
    """Keep all memories for one interview in one Breeth group."""
    return f"interview-{session_id}"


def add_interview_memory(
    session_id: str,
    candidate: dict[str, Any],
    question: str,
    answer: str,
) -> dict[str, Any]:
    """Write one interview question and answer to Breeth."""
    candidate_member = candidate.get("member", {})
    candidate_id = candidate_member.get("id", "unknown")
    candidate_name = candidate_member.get("name", "unknown")
    content = (
        f"Interview session {session_id}. "
        f"Candidate {candidate_id} ({candidate_name}) was asked: {question} "
        f"Candidate answered: {answer}"
    )

    payload = {
        "content": content,
        "group_id": _group_id(session_id),
        "source_description": "ABTalks Interview Agent",
        "extract_intent": True,
    }
    return _post("/v1/episodes", payload)


def search_interview_memory(
    session_id: str,
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Search Breeth memories for one interview session."""
    payload = {
        "query": query,
        "group_id": _group_id(session_id),
        "limit": limit,
    }
    return _post("/v1/search", payload)