"""In-memory interview session state for the temporary interview flow."""

from dataclasses import dataclass, field
from typing import Any

from data_loader import get_curriculum_by_day


REQUIRED_QUESTION_COUNT = 8
MINIMUM_CURRICULUM_DAYS = 4


@dataclass
class InterviewSession:
    session_id: str
    candidate: dict[str, Any]
    questions: list[str] = field(default_factory=list)
    question_details: list[dict[str, Any]] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    questions_asked: int = 0
    curriculum_days_covered: list[int] = field(default_factory=list)
    topics_covered: list[str] = field(default_factory=list)
    status: str = "ongoing"
    feedback: dict[str, Any] | None = None

    @property
    def answered_questions(self) -> int:
        """Return how many asked questions have been answered."""
        return len(self.answers)

    @property
    def is_ready_for_feedback(self) -> bool:
        """Return True once the required interview answers have been recorded."""
        return self.answered_questions >= REQUIRED_QUESTION_COUNT

    def add_question(
        self,
        question: str,
        day_number: int,
        question_type: str = "conceptual",
        reasoning: str = "Initial interview question.",
    ) -> None:
        """Record a question and its curriculum topic."""
        if self.questions_asked >= REQUIRED_QUESTION_COUNT:
            raise ValueError("Interview already has the required number of questions.")
        if question in self.questions:
            raise ValueError("Interview questions must not repeat.")

        self.questions.append(question)
        self.question_details.append(
            {
                "question": question,
                "question_type": question_type,
                "curriculum_day": day_number,
                "reasoning": reasoning,
            }
        )
        self.questions_asked += 1

        if day_number not in self.curriculum_days_covered:
            self.curriculum_days_covered.append(day_number)

        curriculum_day = get_curriculum_by_day(day_number)
        if curriculum_day is not None:
            topic = curriculum_day["title"]
            if topic not in self.topics_covered:
                self.topics_covered.append(topic)

    def complete(self, feedback: dict[str, Any]) -> None:
        """Mark the interview complete and attach generated feedback."""
        self.status = "completed"
        self.feedback = feedback


sessions: dict[str, InterviewSession] = {}


DEFAULT_INITIAL_QUESTIONS = {
    7: "What is an embedding in the context of AI?",
    8: "What is a vector database, and why is it useful?",
}


def completed_curriculum_days(candidate: dict[str, Any]) -> list[int]:
    """Return completed curriculum day numbers in candidate mission order."""
    completed_days: list[int] = []
    for mission in candidate.get("missions", []):
        if mission.get("passed") is not True:
            continue
        day_number = mission.get("day")
        if isinstance(day_number, int) and get_curriculum_by_day(day_number) is not None:
            completed_days.append(day_number)
    return completed_days


def initial_question_for_candidate(candidate: dict[str, Any]) -> tuple[str, int]:
    """Choose a deterministic first question from completed curriculum only."""
    completed_days = completed_curriculum_days(candidate)
    if not completed_days:
        raise ValueError("Candidate has no completed curriculum days to interview on.")

    for day_number in completed_days:
        if day_number in DEFAULT_INITIAL_QUESTIONS:
            return DEFAULT_INITIAL_QUESTIONS[day_number], day_number

    day_number = completed_days[0]
    curriculum_day = get_curriculum_by_day(day_number)
    title = curriculum_day["title"] if curriculum_day else f"Day {day_number}"
    return f"Can you explain the most important concept you learned in {title}?", day_number


def create_session(session_id: str, candidate: dict[str, Any]) -> InterviewSession:
    """Create and store a new ongoing interview session."""
    session = InterviewSession(session_id=session_id, candidate=candidate)
    first_question, day_number = initial_question_for_candidate(candidate)
    session.add_question(first_question, day_number=day_number)
    sessions[session_id] = session
    return session


def get_session(session_id: str) -> InterviewSession | None:
    """Return a session by ID, if it exists."""
    return sessions.get(session_id)


def record_answer(session: InterviewSession, answer: str) -> None:
    """Store an answer in the current session."""
    if session.status == "completed":
        raise ValueError("Interview session is already completed.")
    if len(session.answers) >= len(session.questions):
        raise ValueError("There is no unanswered interview question.")
    session.answers.append(answer)
    if session.is_ready_for_feedback:
        session.status = "ready_for_feedback"
