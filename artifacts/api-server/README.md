# ABTalks Interview Agent API

This FastAPI service runs a short, conversational technical interview for an ABTalks candidate.

## Runtime configuration

Set these environment variables for live integrations:

- `GEMINI_API_KEY` enables Gemini question and feedback generation.
- `BREETH_API_KEY` enables Breeth interview memory writes.

Unit tests mock both services and do not require live keys.

## Interview flow

1. Start an interview:

   ```http
   POST /api/interview
   {
     "sessionId": "session-123",
     "candidate": { ...candidate profile with missions... }
   }
   ```

   The response includes the first question. The first question is selected only from curriculum days the candidate has completed.

2. Submit each answer:

   ```http
   POST /api/interview
   {
     "sessionId": "session-123",
     "message": "Candidate answer text"
   }
   ```

   The service stores the answer, writes the question/answer memory to Breeth, and asks Gemini for the next adaptive question until the interview reaches eight answered questions. Gemini is instructed and validated to avoid repeated questions and to ask only about completed curriculum days.

3. Complete the interview after the eighth answer:

   ```http
   POST /api/interview/session-123/complete
   ```

   The response contains structured feedback based on the candidate profile, covered curriculum, asked questions, and actual answers. Feedback includes an overall assessment, strengths, gaps, topic assessments, and actionable recommendations.

## Existing endpoints

- `GET /api/healthz` returns `{"status": "ok"}`.
- `GET /api/test/candidate/{candidate_id}` returns a candidate from local JSON data.
