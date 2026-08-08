---
name: Gemini interviewer
description: Interview question generation uses the official Python Google GenAI SDK with structured Pydantic output.
---

The interviewer uses the user-managed `GEMINI_API_KEY` with `google-genai`, and asks Gemini for JSON matching the question, type, curriculum day, and reasoning fields.

**Why:** The implementation brief explicitly requires the official Python SDK and a user-provided Gemini key, while the available Replit Gemini integration is a TypeScript proxy with different environment variables.

**How to apply:** Keep the Gemini service separate from FastAPI routes, pass only completed curriculum topics plus session history, reject uncompleted days and repeated questions, and mock the service in tests.