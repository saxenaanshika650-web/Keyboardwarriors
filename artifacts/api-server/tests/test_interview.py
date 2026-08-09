"""Tests for the interview route with external services mocked."""

import os
import sys
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import llm_interviewer
import main
from interview_session import REQUIRED_QUESTION_COUNT, create_session, sessions


class InterviewApiTests(unittest.TestCase):
    def setUp(self) -> None:
        sessions.clear()
        self.client = TestClient(main.app)
        self.candidate = {
            "member": {"id": "CAND-TEST", "name": "Test Candidate"},
            "missions": [
                {"day": 7, "title": "Embeddings Explained", "passed": True},
                {"day": 8, "title": "Vector Databases Overview", "passed": True},
                {"day": 10, "title": "Retrieval & Matching Engine", "passed": True},
                {"day": 12, "title": "Prompt Engineering Fundamentals", "passed": True},
                {"day": 13, "title": "Agentic Workflows", "passed": False},
            ],
        }

    def _start(self, session_id: str = "test-session") -> dict:
        response = self.client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": self.candidate},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    @patch("main.add_interview_memory")
    def test_interview_creation(self, add_memory) -> None:
        body = self._start()
        self.assertEqual(body["question"], "What is an embedding in the context of AI?")
        self.assertEqual(body["questionsAsked"], 1)
        self.assertEqual(body["requiredQuestions"], REQUIRED_QUESTION_COUNT)
        self.assertEqual(sessions["test-session"].curriculum_days_covered, [7])
        add_memory.assert_not_called()

    @patch("main.add_interview_memory")
    def test_recording_answers_and_adaptive_next_question(self, add_memory) -> None:
        self._start()
        generated_question = {
            "question": "How would you choose a vector database for production?",
            "question_type": "practical",
            "curriculum_day": 8,
            "reasoning": "The answer was strong, so increase practical difficulty.",
        }
        with patch("main.generate_next_question", return_value=generated_question) as llm:
            response = self.client.post(
                "/api/interview",
                json={"sessionId": "test-session", "message": "An embedding represents meaning as a vector."},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["question"], generated_question["question"])
        self.assertEqual(response.json()["curriculum_day"], 8)
        llm.assert_called_once()
        context = llm.call_args.args[0]
        self.assertEqual(context["previous_answers"], ["An embedding represents meaning as a vector."])
        self.assertEqual(sessions["test-session"].answers, ["An embedding represents meaning as a vector."])
        add_memory.assert_called_once()

    def test_unknown_session_returns_not_found(self) -> None:
        response = self.client.post(
            "/api/interview",
            json={"sessionId": "missing-session", "message": "answer"},
        )
        self.assertEqual(response.status_code, 404)

    def test_initial_question_uses_completed_curriculum_only(self) -> None:
        candidate = {
            "member": {"id": "CAND-ONE", "name": "One"},
            "missions": [
                {"day": 7, "passed": False},
                {"day": 8, "passed": True},
            ],
        }
        session = create_session("completed-only", candidate)
        self.assertEqual(session.question_details[0]["curriculum_day"], 8)

    def test_no_repeated_questions_in_session(self) -> None:
        session = create_session("repeat-check", self.candidate)
        with self.assertRaises(ValueError):
            session.add_question(session.questions[0], day_number=7)

    def test_llm_rejects_repeated_questions(self) -> None:
        response = Mock(parsed={
            "question": "What is an embedding in the context of AI?",
            "question_type": "follow-up",
            "curriculum_day": 7,
            "reasoning": "Repeat check.",
        })
        fake_client = Mock()
        fake_client.models.generate_content.return_value = response
        context = {
            "candidate": self.candidate,
            "previous_questions": ["What is an embedding in the context of AI?"],
            "previous_answers": ["A vector representation."],
            "questions_asked": 1,
        }
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch("llm_interviewer.genai.Client", return_value=fake_client):
            with self.assertRaises(llm_interviewer.LlmGenerationError):
                llm_interviewer.generate_next_question(context)

    def test_llm_rejects_uncompleted_curriculum_day(self) -> None:
        response = Mock(parsed={
            "question": "Explain an uncompleted agent topic.",
            "question_type": "conceptual",
            "curriculum_day": 13,
            "reasoning": "Invalid day.",
        })
        fake_client = Mock()
        fake_client.models.generate_content.return_value = response
        context = {"candidate": self.candidate, "previous_questions": [], "previous_answers": [], "questions_asked": 0}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch("llm_interviewer.genai.Client", return_value=fake_client):
            with self.assertRaises(llm_interviewer.LlmGenerationError):
                llm_interviewer.generate_next_question(context)

    @patch("main.add_interview_memory")
    def test_reaching_required_question_count_does_not_generate_extra_question(self, add_memory) -> None:
        self._start()
        generated = [
            {"question": f"Question {i}", "question_type": "conceptual", "curriculum_day": day, "reasoning": "coverage"}
            for i, day in enumerate([8, 10, 12, 7, 8, 10, 12], start=2)
        ]
        with patch("main.generate_next_question", side_effect=generated) as next_question:
            for i in range(REQUIRED_QUESTION_COUNT - 1):
                response = self.client.post("/api/interview", json={"sessionId": "test-session", "message": f"answer {i}"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "ongoing")
            final_response = self.client.post("/api/interview", json={"sessionId": "test-session", "message": "final answer"})

        self.assertEqual(final_response.status_code, 200)
        self.assertEqual(final_response.json()["status"], "ready_for_feedback")
        self.assertEqual(sessions["test-session"].questions_asked, REQUIRED_QUESTION_COUNT)
        self.assertEqual(sessions["test-session"].answered_questions, REQUIRED_QUESTION_COUNT)
        self.assertEqual(next_question.call_count, REQUIRED_QUESTION_COUNT - 1)
        self.assertEqual(add_memory.call_count, REQUIRED_QUESTION_COUNT)

    @patch("main.add_interview_memory")
    def test_interview_completion_returns_feedback(self, add_memory) -> None:
        self.test_reaching_required_question_count_does_not_generate_extra_question()
        feedback = {
            "overall_assessment": "Good grounding with some shallow answers.",
            "strengths": ["Explained embeddings clearly."],
            "weaknesses_or_gaps": ["Needs more retrieval detail."],
            "topic_assessments": [{"curriculum_day": 7, "topic": "Embeddings Explained", "assessment": "Solid", "evidence": ["vector"]}],
            "actionable_recommendations": ["Practice explaining retrieval tradeoffs."],
        }
        with patch("main.generate_feedback", return_value=feedback):
            response = self.client.post("/api/interview/test-session/complete")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["feedback"], feedback)

    def test_missing_gemini_key_is_clear(self) -> None:
        context = {"candidate": self.candidate, "previous_questions": [], "previous_answers": [], "questions_asked": 0}
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(llm_interviewer.LlmConfigurationError) as error:
                llm_interviewer.generate_next_question(context)
        self.assertIn("GEMINI_API_KEY is not configured", str(error.exception))

    def test_gemini_failure_handling(self) -> None:
        fake_client = Mock()
        fake_client.models.generate_content.side_effect = RuntimeError("boom")
        context = {"candidate": self.candidate, "previous_questions": [], "previous_answers": [], "questions_asked": 0}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch("llm_interviewer.genai.Client", return_value=fake_client):
            with self.assertRaises(llm_interviewer.LlmGenerationError):
                llm_interviewer.generate_next_question(context)

    @patch("main.add_interview_memory", side_effect=main.BreethApiError("down"))
    def test_breeth_failure_handling(self, add_memory) -> None:
        self._start()
        response = self.client.post(
            "/api/interview",
            json={"sessionId": "test-session", "message": "answer"},
        )
        self.assertEqual(response.status_code, 502)
        self.assertIn("Breeth memory could not be updated", response.json()["detail"])
        self.assertEqual(sessions["test-session"].answers, ["answer"])


if __name__ == "__main__":
    unittest.main()
