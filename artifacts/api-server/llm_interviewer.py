"""Gemini-powered interview question generation."""

import json
import os
from typing import Any

from google import genai
from pydantic import BaseModel, Field

from data_loader import get_curriculum_by_day


MODEL_NAME = "gemini-2.5-flash"


class LlmConfigurationError(RuntimeError):
    """Raised when Gemini is not configured."""


class LlmGenerationError(RuntimeError):
    """Raised when Gemini cannot produce a valid interview question."""


class GeneratedQuestion(BaseModel):
    """The structured question returned by Gemini."""

    question: str = Field(description="The next interview question.")
    question_type: str = Field(
        description="One of: conceptual, practical, troubleshooting, behavioral, or follow-up."
    )
    curriculum_day: int = Field(
        description="The completed curriculum day this question tests."
    )
    reasoning: str = Field(
        description="Brief explanation of why this question is the right next question."
    )


def _api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LlmConfigurationError(
            "GEMINI_API_KEY is not configured. Add it to the environment before generating interview questions."
        )
    return api_key


def _completed_curriculum(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only curriculum days whose candidate mission was passed."""
    completed_days: list[dict[str, Any]] = []
    for mission in candidate.get("missions", []):
        if mission.get("passed") is not True:
            continue

        day_number = mission.get("day")
        if not isinstance(day_number, int):
            continue

        curriculum_day = get_curriculum_by_day(day_number)
        if curriculum_day is not None:
            completed_days.append(curriculum_day)

    return completed_days


def _prompt(context: dict[str, Any]) -> str:
    completed_topics = _completed_curriculum(context["candidate"])
    completed_topic_summary = json.dumps(
        [
            {
                "day": day["day"],
                "title": day["title"],
                "objectives": day["objectives"],
            }
            for day in completed_topics
        ],
        ensure_ascii=False,
    )

    return f"""
You are the interviewer for the ABTalks AI curriculum.

Generate the next single interview question using this current context:

Candidate profile and progress:
{json.dumps(context["candidate"], ensure_ascii=False)}

Curriculum topics the candidate has completed (passed missions only):
{completed_topic_summary}

Previous questions:
{json.dumps(context["previous_questions"], ensure_ascii=False)}

Previous answers:
{json.dumps(context["previous_answers"], ensure_ascii=False)}

Current question count:
{context["questions_asked"]}

Interview rules:
- Ask only about a topic in the completed curriculum list.
- Analyze the latest previous answer.
- Ask a targeted follow-up when the answer is incomplete, incorrect, shallow, or ambiguous.
- If the answer demonstrates strong understanding, increase difficulty or move to another completed topic.
- Never repeat a previous question.
- Keep the interview conversational rather than following a fixed questionnaire.
- Work toward at least 8 questions across at least 4 different completed curriculum days.
- Return only the requested structured fields.
""".strip()


def generate_next_question(context: dict[str, Any]) -> dict[str, Any]:
    """Generate and validate one structured interview question with Gemini."""
    client = genai.Client(api_key=_api_key())

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=_prompt(context),
            config={
                "response_mime_type": "application/json",
                "response_schema": GeneratedQuestion,
                "temperature": 0.4,
            },
        )
    except Exception as error:
        raise LlmGenerationError(
            "Gemini could not generate the next interview question."
        ) from error

    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, GeneratedQuestion):
        result = parsed
    elif isinstance(parsed, dict):
        result = GeneratedQuestion.model_validate(parsed)
    else:
        raw_text = getattr(response, "text", None)
        if not raw_text:
            raise LlmGenerationError(
                "Gemini returned no structured interview question."
            )
        try:
            result = GeneratedQuestion.model_validate(json.loads(raw_text))
        except (json.JSONDecodeError, ValueError) as error:
            raise LlmGenerationError(
                "Gemini returned an invalid interview question."
            ) from error

    completed_days = {
        day["day"] for day in _completed_curriculum(context["candidate"])
    }
    if result.curriculum_day not in completed_days:
        raise LlmGenerationError(
            "Gemini selected a curriculum day the candidate has not completed."
        )
    if result.question in context["previous_questions"]:
        raise LlmGenerationError("Gemini repeated a previous interview question.")

    return result.model_dump()