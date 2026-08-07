"""In-memory interview session state for the temporary interview flow."""

from dataclasses import dataclass, field
from typing import Any

from data_loader import get_curriculum_by_day


@dataclass
class InterviewSession:
    session_id: str
    candidate: dict[str, Any]
    questions: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    questions_asked: int = 0
    curriculum_days_covered: list[int] = field(default_factory=list)
    topics_covered: list[str] = field(default_factory=list)
    status: str = "ongoing"

    def add_question(self, question: str, day_number: int) -> None:
        """Record a question and its curriculum topic."""
        self.questions.append(question)
        self.questions_asked += 1

        if day_number not in self.curriculum_days_covered:
            self.curriculum_days_covered.append(day_number)

        curriculum_day = get_curriculum_by_day(day_number)
        if curriculum_day is not None:
            topic = curriculum_day["title"]
            if topic not in self.topics_covered:
                self.topics_covered.append(topic)


sessions: dict[str, InterviewSession] = {}

FIRST_QUESTION = "What is an embedding in the context of AI?"
FOLLOW_UP_QUESTION = "What is a vector database, and why is it useful?"


def create_session(session_id: str, candidate: dict[str, Any]) -> InterviewSession:
    """Create and store a new ongoing interview session."""
    session = InterviewSession(session_id=session_id, candidate=candidate)
    session.add_question(FIRST_QUESTION, day_number=7)
    sessions[session_id] = session
    return session


def get_session(session_id: str) -> InterviewSession | None:
    """Return a session by ID, if it exists."""
    return sessions.get(session_id)


def record_answer(session: InterviewSession, answer: str) -> str:
    """Store an answer and return the next temporary question."""
    session.answers.append(answer)
    session.add_question(FOLLOW_UP_QUESTION, day_number=8)
    return FOLLOW_UP_QUESTION