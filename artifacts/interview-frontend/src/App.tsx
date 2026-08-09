import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  API_BASE_URL,
  ApiError,
  Candidate,
  CompleteInterviewResponse,
  InterviewResponse,
  getCandidate,
  getHealth,
  isReadyForFeedback,
  startInterview,
  submitAnswer,
  completeInterview,
} from "./api";

type AppStep = "landing" | "candidate" | "interview" | "results";
type LoadingAction = "health" | "candidate" | "start" | "answer" | "complete" | null;

interface InterviewState {
  sessionId: string;
  currentQuestion: string;
  status: string;
  questionsAsked: number;
  requiredQuestions: number;
  questionType?: string;
  curriculumDay?: number;
  answersRecorded: number;
}

function createSessionId(candidateId: string): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${candidateId}-${random}`;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Candidate or interview session was not found.";
    if (error.status === 409) return error.detail || "This interview state cannot be changed right now.";
    if (error.status >= 500) return error.detail || "The Interview Agent service is temporarily unavailable.";
    return error.detail;
  }

  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

function completedMissions(candidate: Candidate) {
  return candidate.missions.filter((mission) => mission.passed === true);
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="error-banner">{message}</div>;
}

function CandidateSummary({ candidate }: { candidate: Candidate }) {
  const member = candidate.member;
  const completed = completedMissions(candidate);

  return (
    <section className="card candidate-card">
      <div className="section-heading">
        <p className="eyebrow">Candidate loaded</p>
        <h2>{member.name ?? member.id}</h2>
      </div>

      <div className="stats-grid">
        <Stat label="Candidate ID" value={member.id} />
        <Stat label="Role" value={member.jobRole ?? "Not provided"} />
        <Stat label="Experience" value={member.yearsExperience ?? "N/A"} />
        <Stat label="Completed days" value={completed.length} />
      </div>

      <div className="profile-row">
        <span>Education</span>
        <strong>{member.education ?? "Not provided"}</strong>
      </div>

      <div className="missions-panel">
        <h3>Completed curriculum available for interview</h3>
        {completed.length > 0 ? (
          <div className="mission-list">
            {completed.slice(0, 10).map((mission) => (
              <span key={`${mission.day}-${mission.title}`} className="mission-pill">
                Day {mission.day}: {mission.title ?? "Untitled topic"}
              </span>
            ))}
            {completed.length > 10 && (
              <span className="mission-pill muted">+{completed.length - 10} more</span>
            )}
          </div>
        ) : (
          <p className="muted-text">This candidate has no completed curriculum days.</p>
        )}
      </div>
    </section>
  );
}

function Progress({ current, total }: { current: number; total: number }) {
  const percent = Math.min(100, Math.max(0, (current / total) * 100));
  return (
    <div className="progress-wrap" aria-label={`Question ${current} of ${total}`}>
      <div className="progress-meta">
        <span>Progress</span>
        <strong>
          Question {current} of {total}
        </strong>
      </div>
      <div className="progress-track">
        <div className="progress-bar" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function FeedbackList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section className="feedback-section">
      <h3>{title}</h3>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export default function App() {
  const [step, setStep] = useState<AppStep>("landing");
  const [candidateId, setCandidateId] = useState("CAND-001");
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [interview, setInterview] = useState<InterviewState | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<CompleteInterviewResponse | null>(null);
  const [loading, setLoading] = useState<LoadingAction>("health");
  const [error, setError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    let active = true;
    getHealth()
      .then(() => {
        if (active) setApiStatus("online");
      })
      .catch(() => {
        if (active) setApiStatus("offline");
      })
      .finally(() => {
        if (active) setLoading(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const canStart = useMemo(() => {
    return candidate !== null && completedMissions(candidate).length > 0;
  }, [candidate]);

  async function handleLoadCandidate(event: FormEvent) {
    event.preventDefault();
    const id = candidateId.trim();
    if (!id) {
      setError("Enter a candidate ID such as CAND-001.");
      return;
    }

    setLoading("candidate");
    setError(null);
    setCandidate(null);
    setFeedback(null);
    setInterview(null);

    try {
      const loadedCandidate = await getCandidate(id);
      if (!loadedCandidate.member?.id || !Array.isArray(loadedCandidate.missions)) {
        throw new Error("The candidate response is missing required profile fields.");
      }
      setCandidate(loadedCandidate);
      setStep("candidate");
    } catch (err) {
      setError(errorMessage(err));
      setStep("landing");
    } finally {
      setLoading(null);
    }
  }

  async function handleStartInterview() {
    if (!candidate) return;
    if (!canStart) {
      setError("This candidate has no completed curriculum days available for interview.");
      return;
    }

    const sessionId = createSessionId(candidate.member.id);
    setLoading("start");
    setError(null);

    try {
      const response = await startInterview({ sessionId, candidate });
      setInterview({
        sessionId: response.sessionId,
        currentQuestion: response.question,
        status: response.status,
        questionsAsked: response.questionsAsked,
        requiredQuestions: response.requiredQuestions,
        answersRecorded: 0,
      });
      setAnswer("");
      setStep("interview");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  }

  function updateInterviewFromResponse(response: InterviewResponse) {
    setInterview((current) => {
      if (!current) return current;

      if (isReadyForFeedback(response)) {
        return {
          ...current,
          status: response.status,
          questionsAsked: response.questionsAsked,
          requiredQuestions: response.requiredQuestions,
          answersRecorded: response.answersRecorded,
        };
      }

      return {
        ...current,
        status: response.status,
        currentQuestion: response.question,
        questionsAsked: response.questionsAsked,
        requiredQuestions: response.requiredQuestions,
        questionType: response.question_type,
        curriculumDay: response.curriculum_day,
        answersRecorded: Math.min(current.answersRecorded + 1, response.requiredQuestions),
      };
    });
  }

  async function handleSubmitAnswer(event: FormEvent) {
    event.preventDefault();
    if (!interview) return;
    const message = answer.trim();
    if (!message) {
      setError("Please enter an answer before submitting.");
      return;
    }

    setLoading("answer");
    setError(null);

    try {
      const response = await submitAnswer({ sessionId: interview.sessionId, message });
      updateInterviewFromResponse(response);
      setAnswer("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleCompleteInterview() {
    if (!interview) return;
    setLoading("complete");
    setError(null);

    try {
      const response = await completeInterview(interview.sessionId);
      setFeedback(response);
      setStep("results");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(null);
    }
  }

  const isBusy = loading !== null;
  const readyForFeedback = interview?.status === "ready_for_feedback";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <span className="brand-mark">KW</span>
          <span className="brand-text">KeyboardWarriors</span>
        </div>
        <div className={`api-status ${apiStatus}`}>
          <span />
          API {apiStatus === "checking" ? "checking" : apiStatus}
        </div>
      </header>

      <section className="hero-grid">
        <div className="hero-copy">
          <p className="eyebrow">AI-powered technical interviews</p>
          <h1>KeyboardWarriors Interview Agent</h1>
          <p>
            Run a focused technical interview based on the candidate's completed ABTalks curriculum,
            then receive structured feedback from the Interview Agent.
          </p>
          <div className="api-base">Backend: {API_BASE_URL}</div>
        </div>

        <div className="card action-card">
          <ErrorBanner message={error} />

          {(step === "landing" || step === "candidate") && (
            <>
              <form onSubmit={handleLoadCandidate} className="candidate-form">
                <label htmlFor="candidateId">Candidate ID</label>
                <div className="input-row">
                  <input
                    id="candidateId"
                    value={candidateId}
                    onChange={(event) => setCandidateId(event.target.value)}
                    placeholder="CAND-001"
                    disabled={isBusy}
                  />
                  <button type="submit" disabled={isBusy}>
                    {loading === "candidate" ? "Loading..." : "Load Candidate"}
                  </button>
                </div>
              </form>

              <p className="helper-text">
                Candidate IDs are matched against <code>member.id</code> in the backend candidate data.
              </p>
            </>
          )}

          {step === "candidate" && candidate && (
            <div className="start-panel">
              <CandidateSummary candidate={candidate} />
              <button className="primary wide" onClick={handleStartInterview} disabled={isBusy || !canStart}>
                {loading === "start" ? "Starting interview..." : "Start Interview"}
              </button>
            </div>
          )}

          {step === "interview" && interview && (
            <section className="interview-panel">
              <div className="section-heading">
                <p className="eyebrow">AI Technical Interview</p>
                <h2>{readyForFeedback ? "All questions answered" : "Current question"}</h2>
              </div>

              <Progress current={interview.questionsAsked} total={interview.requiredQuestions} />

              {!readyForFeedback ? (
                <>
                  <article className="question-card">
                    <div className="question-meta">
                      {interview.curriculumDay && <span>Day {interview.curriculumDay}</span>}
                      {interview.questionType && <span>{interview.questionType}</span>}
                    </div>
                    <p>{interview.currentQuestion}</p>
                  </article>

                  <form onSubmit={handleSubmitAnswer} className="answer-form">
                    <label htmlFor="answer">Your answer</label>
                    <textarea
                      id="answer"
                      value={answer}
                      onChange={(event) => setAnswer(event.target.value)}
                      placeholder="Explain your thinking clearly and concisely..."
                      disabled={isBusy}
                      rows={8}
                    />
                    <button className="primary wide" type="submit" disabled={isBusy || !answer.trim()}>
                      {loading === "answer" ? "Generating next question..." : "Submit Answer"}
                    </button>
                  </form>
                </>
              ) : (
                <div className="complete-panel">
                  <p>
                    The required {interview.requiredQuestions} questions have been answered. Finish the
                    interview to generate structured feedback.
                  </p>
                  <button className="primary wide" onClick={handleCompleteInterview} disabled={isBusy}>
                    {loading === "complete" ? "Generating feedback..." : "Finish Interview"}
                  </button>
                </div>
              )}
            </section>
          )}

          {step === "results" && feedback && (
            <section className="results-panel">
              <div className="section-heading">
                <p className="eyebrow">Interview complete</p>
                <h2>Structured Feedback</h2>
              </div>

              <div className="result-summary">
                <Stat label="Status" value={feedback.status} />
                <Stat label="Questions" value={feedback.questionsAsked} />
                <Stat label="Answers" value={feedback.answersRecorded} />
              </div>

              <section className="feedback-section highlight">
                <h3>Overall assessment</h3>
                <p>{feedback.feedback.overall_assessment}</p>
              </section>

              <FeedbackList title="Strengths" items={feedback.feedback.strengths} />
              <FeedbackList title="Weaknesses / gaps" items={feedback.feedback.weaknesses_or_gaps} />
              <FeedbackList
                title="Actionable recommendations"
                items={feedback.feedback.actionable_recommendations}
              />

              {feedback.feedback.topic_assessments.length > 0 && (
                <section className="feedback-section">
                  <h3>Topic-wise assessment</h3>
                  <div className="topic-list">
                    {feedback.feedback.topic_assessments.map((topic) => (
                      <article key={`${topic.curriculum_day}-${topic.topic}`} className="topic-card">
                        <span>Day {topic.curriculum_day}</span>
                        <h4>{topic.topic}</h4>
                        <p>{topic.assessment}</p>
                        {topic.evidence.length > 0 && (
                          <ul>
                            {topic.evidence.map((evidence) => (
                              <li key={evidence}>{evidence}</li>
                            ))}
                          </ul>
                        )}
                      </article>
                    ))}
                  </div>
                </section>
              )}

              <button
                className="secondary wide"
                onClick={() => {
                  setStep("landing");
                  setCandidate(null);
                  setInterview(null);
                  setFeedback(null);
                  setAnswer("");
                  setError(null);
                }}
              >
                Start another interview
              </button>
            </section>
          )}
        </div>
      </section>
    </main>
  );
}
