"""Tests for the interview route with external services mocked."""

import os
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import llm_interviewer
import main
from interview_session import sessions


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
                {
                    "day": 12,
                    "title": "Prompt Engineering Fundamentals",
                    "passed": True,
                },
            ],
        }

    @patch("main.add_interview_memory")
    def test_start_and_answer_uses_mocked_llm(self, add_memory) -> None:
        start_response = self.client.post(
            "/api/interview",
            json={"sessionId": "test-session", "candidate": self.candidate},
        )
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(
            start_response.json()["question"],
            "What is an embedding in the context of AI?",
        )

        generated_question = {
            "question": "How would you choose a vector database for production?",
            "question_type": "practical",
            "curriculum_day": 8,
            "reasoning": "The answer was strong, so increase practical difficulty.",
        }
        with patch("main.generate_next_question", return_value=generated_question) as llm:
            answer_response = self.client.post(
                "/api/interview",
                json={
                    "sessionId": "test-session",
                    "message": "An embedding represents meaning as a vector.",
                },
            )

        self.assertEqual(answer_response.status_code, 200)
        self.assertEqual(answer_response.json()["question"], generated_question["question"])
        self.assertEqual(answer_response.json()["curriculum_day"], 8)
        llm.assert_called_once()
        context = llm.call_args.args[0]
        self.assertEqual(
            context["previous_answers"],
            ["An embedding represents meaning as a vector."],
        )
        self.assertEqual(
            sessions["test-session"].answers,
            ["An embedding represents meaning as a vector."],
        )
        add_memory.assert_called_once()

    def test_unknown_session_returns_not_found(self) -> None:
        response = self.client.post(
            "/api/interview",
            json={"sessionId": "missing-session", "message": "answer"},
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_gemini_key_is_clear(self) -> None:
        context = {"candidate": self.candidate, "previous_questions": [], "previous_answers": [], "questions_asked": 0}
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(llm_interviewer.LlmConfigurationError) as error:
                llm_interviewer.generate_next_question(context)

        self.assertIn("GEMINI_API_KEY is not configured", str(error.exception))


if __name__ == "__main__":
    unittest.main()