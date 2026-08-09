"""Gemini-powered interview question and feedback generation."""

import json
import os
from typing import Any

from google import genai
from pydantic import BaseModel, Field, ValidationError

from data_loader import get_curriculum_by_day
from interview_session import MINIMUM_CURRICULUM_DAYS, REQUIRED_QUESTION_COUNT


MODEL_NAME = "gemini-2.5-flash"


class LlmConfigurationError(RuntimeError):
    """Raised when Gemini is not configured."""


class LlmGenerationError(RuntimeError):
    """Raised when Gemini cannot produce valid structured output."""


class GeneratedQuestion(BaseModel):
    """The structured question returned by Gemini."""

    question: str = Field(description="The next interview question.", min_length=1)
    question_type: str = Field(
        description="One of: conceptual, practical, troubleshooting, behavioral, or follow-up."
    )
    curriculum_day: int = Field(
        description="The completed curriculum day this question tests."
    )
    reasoning: str = Field(
        description="Brief explanation of why this question is the right next question.",
        min_length=1,
    )


class TopicAssessment(BaseModel):
    curriculum_day: int
    topic: str
    assessment: str
    evidence: list[str] = Field(default_factory=list)


class InterviewFeedback(BaseModel):
    overall_assessment: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses_or_gaps: list[str] = Field(default_factory=list)
    topic_assessments: list[TopicAssessment] = Field(default_factory=list)
    actionable_recommendations: list[str] = Field(default_factory=list)


def _api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LlmConfigurationError(
            "GEMINI_API_KEY is not configured. Add it to the environment before using Gemini."
        )
    return api_key


def _completed_curriculum(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only curriculum days whose candidate mission was passed."""
    completed_days: list[dict[str, Any]] = []
    seen_days: set[int] = set()
    for mission in candidate.get("missions", []):
        if mission.get("passed") is not True:
            continue

        day_number = mission.get("day")
        if not isinstance(day_number, int) or day_number in seen_days:
            continue

        curriculum_day = get_curriculum_by_day(day_number)
        if curriculum_day is not None:
            completed_days.append(curriculum_day)
            seen_days.add(day_number)

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
    remaining_questions = REQUIRED_QUESTION_COUNT - int(context["questions_asked"])

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

Curriculum days already covered:
{json.dumps(context.get("curriculum_days_covered", []), ensure_ascii=False)}

Current question count: {context["questions_asked"]}
Remaining questions before completion: {remaining_questions}

Interview rules:
- Ask only about a topic in the completed curriculum list.
- Analyze the latest previous answer.
- Ask a targeted follow-up when the answer is incomplete, incorrect, shallow, or ambiguous.
- If the answer demonstrates strong understanding, increase difficulty or move to another completed topic.
- Never repeat a previous question.
- Keep the interview conversational rather than following a fixed questionnaire.
- The full interview must contain exactly {REQUIRED_QUESTION_COUNT} questions.
- Work toward at least {MINIMUM_CURRICULUM_DAYS} different completed curriculum days by the end.
- If coverage is behind, prefer an uncovered completed curriculum day unless a follow-up is clearly needed.
- Return only the requested structured fields.
""".strip()


def _parse_response(response: Any, model: type[BaseModel], error_message: str) -> BaseModel:
    parsed = getattr(response, "parsed", None)
    try:
        if isinstance(parsed, model):
            return parsed
        if isinstance(parsed, dict):
            return model.model_validate(parsed)
        raw_text = getattr(response, "text", None)
        if not raw_text:
            raise LlmGenerationError(error_message)
        return model.model_validate(json.loads(raw_text))
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise LlmGenerationError(error_message) from error


def generate_next_question(context: dict[str, Any]) -> dict[str, Any]:
    """Generate and validate one structured interview question with Gemini."""
    if context["questions_asked"] >= REQUIRED_QUESTION_COUNT:
        raise LlmGenerationError("Interview already has the required number of questions.")

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

    result = _parse_response(
        response,
        GeneratedQuestion,
        "Gemini returned an invalid interview question.",
    )
    completed_days = {day["day"] for day in _completed_curriculum(context["candidate"])}
    if result.curriculum_day not in completed_days:
        raise LlmGenerationError(
            "Gemini selected a curriculum day the candidate has not completed."
        )
    if result.question in context["previous_questions"]:
        raise LlmGenerationError("Gemini repeated a previous interview question.")

    return result.model_dump()


def _feedback_prompt(context: dict[str, Any]) -> str:
    return f"""
You are evaluating an ABTalks technical interview.

Use only the evidence in this interview transcript. Do not fabricate performance or claim the candidate did something not shown.

Candidate profile:
{json.dumps(context["candidate"], ensure_ascii=False)}

Completed curriculum topics eligible for assessment:
{json.dumps(context["completed_curriculum"], ensure_ascii=False)}

Questions asked with curriculum metadata:
{json.dumps(context["question_details"], ensure_ascii=False)}

Candidate answers in order:
{json.dumps(context["answers"], ensure_ascii=False)}

Return structured, actionable feedback. Include evidence snippets from the actual answers where useful. If evidence is missing, say so.
""".strip()


def generate_feedback(context: dict[str, Any]) -> dict[str, Any]:
    """Generate structured final interview feedback with Gemini."""
    client = genai.Client(api_key=_api_key())
    feedback_context = {
        **context,
        "completed_curriculum": _completed_curriculum(context["candidate"]),
    }
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=_feedback_prompt(feedback_context),
            config={
                "response_mime_type": "application/json",
                "response_schema": InterviewFeedback,
                "temperature": 0.2,
            },
        )
    except Exception as error:
        raise LlmGenerationError("Gemini could not generate interview feedback.") from error

    result = _parse_response(
        response,
        InterviewFeedback,
        "Gemini returned invalid interview feedback.",
    )
    return result.model_dump()
