const DEFAULT_API_BASE_URL = "https://keyboardwarriors-phqy.onrender.com";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

export interface HealthStatus {
  status: string;
}

export interface CandidateMember {
  id: string;
  name?: string;
  jobRole?: string;
  yearsExperience?: number;
  education?: string;
  status?: string;
  [key: string]: unknown;
}

export interface CandidateMission {
  day?: number;
  title?: string;
  passed?: boolean;
  skipped?: boolean;
  attempts?: number;
  [key: string]: unknown;
}

export interface Candidate {
  member: CandidateMember;
  missions: CandidateMission[];
  [key: string]: unknown;
}

export interface StartInterviewRequest {
  sessionId: string;
  candidate: Candidate;
}

export interface SubmitAnswerRequest {
  sessionId: string;
  message: string;
}

export interface StartInterviewResponse {
  sessionId: string;
  status: string;
  question: string;
  questionsAsked: number;
  requiredQuestions: number;
}

export interface NextQuestionResponse extends StartInterviewResponse {
  question_type?: string;
  curriculum_day?: number;
  reasoning?: string;
}

export interface ReadyForFeedbackResponse {
  sessionId: string;
  status: "ready_for_feedback" | string;
  message: string;
  questionsAsked: number;
  answersRecorded: number;
  requiredQuestions: number;
}

export type InterviewResponse = NextQuestionResponse | ReadyForFeedbackResponse;

export interface TopicAssessment {
  curriculum_day: number;
  topic: string;
  assessment: string;
  evidence: string[];
}

export interface InterviewFeedback {
  overall_assessment: string;
  strengths: string[];
  weaknesses_or_gaps: string[];
  topic_assessments: TopicAssessment[];
  actionable_recommendations: string[];
}

export interface CompleteInterviewResponse {
  sessionId: string;
  status: string;
  questionsAsked: number;
  answersRecorded: number;
  feedback: InterviewFeedback;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as unknown;
    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return body.detail;
    }
  } catch {
    // Fall back to status text below.
  }

  return response.statusText || `Request failed with HTTP ${response.status}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    throw new Error(
      error instanceof TypeError
        ? "Could not reach the Interview Agent API. Check your connection and API URL."
        : "The Interview Agent API request failed.",
    );
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }

  return (await response.json()) as T;
}

export async function getHealth(): Promise<HealthStatus> {
  return requestJson<HealthStatus>("/api/healthz");
}

export async function getCandidate(candidateId: string): Promise<Candidate> {
  return requestJson<Candidate>(
    `/api/test/candidate/${encodeURIComponent(candidateId)}`,
  );
}

export async function startInterview(
  payload: StartInterviewRequest,
): Promise<StartInterviewResponse> {
  return requestJson<StartInterviewResponse>("/api/interview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function submitAnswer(
  payload: SubmitAnswerRequest,
): Promise<InterviewResponse> {
  return requestJson<InterviewResponse>("/api/interview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function completeInterview(
  sessionId: string,
): Promise<CompleteInterviewResponse> {
  return requestJson<CompleteInterviewResponse>(
    `/api/interview/${encodeURIComponent(sessionId)}/complete`,
    { method: "POST" },
  );
}

export function isReadyForFeedback(
  response: InterviewResponse,
): response is ReadyForFeedbackResponse {
  return "answersRecorded" in response && response.status === "ready_for_feedback";
}
