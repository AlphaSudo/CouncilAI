import { useState, useEffect, useRef } from "react";
import { X, Download, ChevronRight } from "lucide-react";
import { api } from "./api";
import type { Dict } from "./types";
import type { ReviewOptions } from "./contracts.generated";
import { ScopedClaimDetails, ScopedReviewLedger } from "./ScopedReviewDetails";

export const defaultReviewOptions: ReviewOptions = {
  deliverable: "A useful answer with explicit assumptions and evidence limits.",
  constraints: [],
  baseline: "Unspecified",
  success_criteria: [],
  evidence_requirement: "model_review",
};

export function ReviewSetup({
  value,
  onChange,
}: {
  value: ReviewOptions;
  onChange: (v: ReviewOptions) => void;
}) {
  return (
    <details className="review-setup-details">
      <summary>
        Answer requirements <small>optional</small>
      </summary>
      <label>
        Deliverable
        <input
          value={value.deliverable}
          maxLength={2000}
          onChange={(e) => onChange({ ...value, deliverable: e.target.value })}
        />
      </label>
      <label>
        Hard constraints, one per line
        <textarea
          aria-label="Review hard constraints"
          rows={2}
          value={value.constraints
            ?.filter((c) => c.kind === "hard")
            .map((c) => c.text)
            .join("\n")}
          onChange={(e) =>
            onChange({
              ...value,
              constraints: [
                ...(value.constraints || []).filter((c) => c.kind === "soft"),
                ...e.target.value
                  .split("\n")
                  .filter((s) => s.trim())
                  .slice(0, 20)
                  .map((text) => ({ kind: "hard" as const, text })),
              ],
            })
          }
        />
      </label>
      <label>
        Preferences, one per line
        <textarea
          rows={2}
          value={value.constraints
            ?.filter((c) => c.kind === "soft")
            .map((c) => c.text)
            .join("\n")}
          onChange={(e) =>
            onChange({
              ...value,
              constraints: [
                ...(value.constraints || []).filter((c) => c.kind === "hard"),
                ...e.target.value
                  .split("\n")
                  .filter((s) => s.trim())
                  .slice(0, 20)
                  .map((text) => ({ kind: "soft" as const, text })),
              ],
            })
          }
        />
      </label>
      <label>
        Reference baseline
        <input
          value={value.baseline}
          maxLength={2000}
          onChange={(e) => onChange({ ...value, baseline: e.target.value })}
        />
      </label>
      <label>
        Success criteria, one per line
        <textarea
          rows={2}
          value={value.success_criteria?.join("\n")}
          onChange={(e) =>
            onChange({
              ...value,
              success_criteria: e.target.value
                .split("\n")
                .filter((s) => s.trim())
                .slice(0, 12),
            })
          }
        />
      </label>
      <label>
        Required evidence
        <select
          value={value.evidence_requirement}
          onChange={(e) =>
            onChange({
              ...value,
              evidence_requirement: e.target
                .value as ReviewOptions["evidence_requirement"],
            })
          }
        >
          <option value="model_review">
            Model review; external support remains unverified
          </option>
          <option value="supplied_sources">
            Human-assessed supplied sources
          </option>
          <option value="scoped_tool_result">
            Human-assessed, scoped tool result
          </option>
        </select>
      </label>
      <label>
        Supplied context or source excerpt
        <textarea
          aria-label="Supplied council context"
          rows={3}
          maxLength={8000}
          value={value.sources?.[0]?.text || ""}
          onChange={(e) =>
            onChange({
              ...value,
              sources: e.target.value
                ? [
                    {
                      id: value.sources?.[0]?.id || "council-context",
                      text: e.target.value,
                      provenance:
                        value.sources?.[0]?.provenance ||
                        "Director-supplied context; support not assessed",
                    },
                    ...(value.sources?.slice(1) || []),
                  ]
                : value.sources?.slice(1) || [],
            })
          }
        />
      </label>
      <label>
        Source attribution
        <input
          aria-label="Supplied context attribution"
          maxLength={2000}
          value={value.sources?.[0]?.provenance || ""}
          onChange={(e) =>
            onChange({
              ...value,
              sources:
                value.sources?.map((s, index) =>
                  index === 0
                    ? {
                        ...s,
                        provenance:
                          e.target.value ||
                          "Director-supplied context; support not assessed",
                      }
                    : s,
                ) || [],
            })
          }
        />
      </label>
      <p>
        Sources are shared with the independent answers. Supplying text does not
        establish that it supports a claim.
      </p>
    </details>
  );
}

export function ReviewPanel({
  data,
  onClose,
  onData,
}: {
  data: Dict;
  onClose: () => void;
  onData: (data: Dict) => void;
}) {
  const review = data.review,
    chat = data.chat;
  const inspector = useRef<HTMLElement>(null);
  useEffect(() => {
    const element = inspector.current;
    if (!element) return;
    const trap = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const controls = Array.from(
        element.querySelectorAll<HTMLElement>(
          "button:not(:disabled),a[href],input:not(:disabled),textarea:not(:disabled),select:not(:disabled),summary",
        ),
      ).filter((e) => e.offsetParent !== null);
      const first = controls[0],
        last = controls[controls.length - 1];
      if (!element.contains(document.activeElement)) {
        event.preventDefault();
        first?.focus();
        return;
      }
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => document.removeEventListener("keydown", trap);
  }, []);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState("");
  const [provenance, setProvenance] = useState("");
  const [assessment, setAssessment] = useState("");
  const [supportedScope, setSupportedScope] = useState("");
  const [scopeCoverage, setScopeCoverage] = useState("unknown");
  const [directness, setDirectness] = useState("unknown");
  const [reproduction, setReproduction] = useState("Unknown");
  const [toolEvidence, setToolEvidence] = useState("");
  const [relation, setRelation] = useState("supports");
  const [disposition, setDisposition] = useState("unresolved");
  const [reason, setReason] = useState("");
  const [challenge, setChallenge] = useState("");
  const [evidenceIds, setEvidenceIds] = useState<string[]>([]);
  const [member, setMember] = useState("");
  const [question, setQuestion] = useState(review.contract.question);
  const [options, setOptions] = useState<ReviewOptions>(
    review.contract.options,
  );
  const claim =
    review.claims.find((c: Dict) => c.claim_id === selected) ||
    review.claims[0];
  const decision = review.decisions.find(
    (d: Dict) => d.claim_id === claim?.claim_id,
  );
  const findings = review.findings.filter(
    (f: Dict) => f.claim_id === claim?.claim_id,
  );
  const sources = review.evidence.filter(
    (e: Dict) =>
      e.claim_id === claim?.claim_id && e.claim_revision === claim?.revision,
  );
  const history = review.claim_history.filter(
    (c: Dict) => c.claim_id === claim?.claim_id,
  );
  const author = chat.participants.find((p: Dict) => p.id === claim?.author_id);
  const next = data.next_turn;
  async function act(fn: () => Promise<any>) {
    setBusy(true);
    setError("");
    try {
      const result = await fn();
      if (result?.chat) onData(result);
      return result;
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setBusy(false);
    }
  }
  const mutate = (path: string, body: Dict) =>
    api(`/chats/${chat.id}/review/${path}`, {
      expected_revision: review.revision,
      ...body,
    });
  async function download() {
    await act(async () => {
      const item = await api(`/chats/${chat.id}/review/exports`, {});
      const link = document.createElement("a");
      link.href = item.download;
      link.download = "review.zip";
      link.click();
    });
  }
  return (
    <div className="review-backdrop" onClick={onClose}>
      <aside
        ref={inspector}
        className="review-inspector"
        role="dialog"
        aria-modal="true"
        aria-label="Council claim inspector"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <div>
            <p className="council-mini">COUNCIL · CYCLE {review.cycle}</p>
            <h2>Claims & evidence</h2>
          </div>
          <button
            autoFocus
            className="council-icon"
            aria-label="Close claim inspector"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </header>
        <p className="review-limit">
          Model assessments, source evidence and your decisions remain distinct.
          The labels below are computed by the application.
        </p>
        {error && (
          <p role="alert" className="council-error">
            {error}
          </p>
        )}
        {review.synthesis_stale && (
          <div className="council-state-note">
            The published answer predates review changes.{" "}
            {chat.status === "completed" && (
              <button
                disabled={busy}
                onClick={() => act(() => mutate("resynthesize", {}))}
              >
                Update final answer · 1 call
              </button>
            )}
          </div>
        )}
        <details>
          <summary>Scope, constraints & review roles</summary>
          <p>{review.contract.question}</p>
          <p>Baseline: {review.contract.options.baseline}</p>
          <ul>
            {review.contract.options.constraints.map((c: Dict, i: number) => (
              <li key={i}>
                {c.kind}: {c.text}
              </li>
            ))}
          </ul>
          <p>
            Required evidence: {review.contract.options.evidence_requirement}
          </p>
          <dl className="review-role-list">
            {Object.entries(review.roles).map(([phase, id]) => (
              <div key={phase}>
                <dt>{phase}</dt>
                <dd>
                  {chat.participants.find((p: Dict) => p.id === id)?.name}
                </dd>
              </div>
            ))}
          </dl>
          <p>
            Models may review their own earlier claims. Reusing a model is
            disclosed, not independent external verification.
          </p>
        </details>
        <div className="review-claim-list">
          {review.claims.length ? (
            review.claims.map((c: Dict) => (
              <button
                key={c.claim_id}
                className={claim?.claim_id === c.claim_id ? "selected" : ""}
                onClick={() => {
                  setSelected(c.claim_id);
                  setEvidenceIds([]);
                }}
              >
                <span>
                  {c.text}
                  <small>
                    {
                      review.decisions.find(
                        (d: Dict) => d.claim_id === c.claim_id,
                      )?.label
                    }
                  </small>
                </span>
                <ChevronRight size={15} />
              </button>
            ))
          ) : (
            <p>
              Claims appear after the independent answers and extraction turn.
            </p>
          )}
        </div>
        {claim && (
          <section className="review-claim-detail">
            <p className="review-state">{decision?.label}</p>
            <h3>{claim.text}</h3>
            <ScopedClaimDetails
              review={review}
              claim={claim}
              decision={decision}
            />
            <small>
              {claim.claim_id} · revision {claim.revision} · {author?.name}
            </small>
            <p>
              <b>Scope:</b> {claim.scope}
            </p>
            <p>
              <b>Assumptions:</b>{" "}
              {claim.assumptions.join("; ") || "None stated"}
            </p>
            <p>
              <b>Dependencies:</b>{" "}
              {claim.dependencies.join(", ") || "None declared"}
            </p>
            <a href={`#${claim.source_message_id}`} onClick={onClose}>
              Inspect original answer
            </a>
            {["reviewed_v3", "reviewed_v4"].includes(review.contract.protocol_version) &&
              chat.status === "completed" && (
                <details>
                  <summary>Challenge this claim</summary>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      act(async () => {
                        const result = await api(`/chats/${chat.id}/messages`, {
                          text: challenge,
                          action: "challenge",
                          claim_ids: [claim.claim_id],
                        });
                        onData(result);
                        onClose();
                        return result;
                      });
                    }}
                  >
                    <label>
                      Your objection
                      <textarea
                        aria-label="Challenge to selected claim"
                        value={challenge}
                        maxLength={8000}
                        onChange={(e) => setChallenge(e.target.value)}
                      />
                    </label>
                    <button disabled={busy || !challenge.trim()} type="submit">
                      Review this challenge
                    </button>
                    <p>
                      The council revisits this assertion and its dependencies
                      in the same chat.
                    </p>
                  </form>
                </details>
              )}
            {!!decision?.blockers.length && (
              <ul>
                {decision.blockers.map((s: string, i: number) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            )}
            {findings.map((f: Dict) => {
              const recheck = review.rechecks.find(
                (r: Dict) => r.finding_id === f.id,
              );
              const dispositions = review.dispositions.filter(
                (d: Dict) => d.finding_id === f.id,
              );
              return (
                <div key={f.id} className="review-finding">
                  <h4>Objection · model assessment</h4>
                  <p>
                    <b>Strongest reading:</b> {f.steelman}
                  </p>
                  <p>{f.objection}</p>
                  <p>
                    <b>Candidate test:</b> {f.candidate_test}
                  </p>
                  <p>
                    <b>Resolution needed:</b> {f.minimum_resolution}
                  </p>
                  <ul>
                    {f.checks.map((c: Dict, i: number) => (
                      <li key={i}>
                        {c.category}: {c.status} — {c.reason}
                      </li>
                    ))}
                  </ul>
                  {recheck && (
                    <p>
                      <b>Model recheck:</b> {recheck.proposed_disposition} —{" "}
                      {recheck.reason}
                    </p>
                  )}
                  {f.test && (
                    <details>
                      <summary>Candidate test validity</summary>
                      <p>
                        <b>Method:</b> {f.test.method}
                      </p>
                      <p>
                        <b>Could disconfirm:</b> {f.test.disconfirming_outcome}
                      </p>
                      <p>
                        <b>Baseline:</b> {f.test.baseline}
                      </p>
                      <p>
                        <b>Threshold basis:</b> {f.test.threshold_basis}
                      </p>
                      <p>
                        <b>Limits:</b> {f.test.limitations}
                      </p>
                      <p>
                        <b>Model assessment:</b>{" "}
                        {recheck?.test_assessment || "Not rechecked"} —{" "}
                        {recheck?.test_reason}
                      </p>
                      <p>
                        This is a proposed test; it has not been executed by
                        this review.
                      </p>
                    </details>
                  )}
                  {dispositions.map((d: Dict) => (
                    <p key={d.id}>
                      <b>Human disposition:</b> {d.status} — {d.reason}
                    </p>
                  ))}
                  <details>
                    <summary>Record your disposition</summary>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        act(() =>
                          mutate("dispositions", {
                            finding_id: f.id,
                            status: disposition,
                            reason,
                            evidence_ids: evidenceIds,
                          }),
                        );
                      }}
                    >
                      <label>
                        Disposition
                        <select
                          value={disposition}
                          onChange={(e) => setDisposition(e.target.value)}
                        >
                          <option value="unresolved">Unresolved</option>
                          <option value="rebutted">
                            Rebutted within my assessment
                          </option>
                          <option value="confirmed_defect">
                            Confirmed defect with attached evidence
                          </option>
                          <option value="accepted_risk">
                            Accept bounded risk
                          </option>
                        </select>
                      </label>
                      <label>
                        Reason
                        <textarea
                          required
                          minLength={10}
                          maxLength={2000}
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                        />
                      </label>
                      {sources.map((s: Dict) => (
                        <label key={s.id} className="review-check">
                          <input
                            type="checkbox"
                            checked={evidenceIds.includes(s.id)}
                            onChange={(e) =>
                              setEvidenceIds(
                                e.target.checked
                                  ? [...evidenceIds, s.id]
                                  : evidenceIds.filter((id) => id !== s.id),
                              )
                            }
                          />
                          {s.provenance}
                        </label>
                      ))}
                      <button disabled={busy}>Save human disposition</button>
                    </form>
                  </details>
                </div>
              );
            })}
            <details>
              <summary>Replies, repairs & earlier revisions</summary>
              {review.repairs
                .filter((r: Dict) => r.claim_id === claim.claim_id)
                .map((r: Dict) => (
                  <div key={r.id}>
                    <b>
                      {r.action} · {r.responder.name}
                    </b>
                    <p>{r.response}</p>
                    <p>{r.remaining_uncertainty}</p>
                    {r.replacement_response && (
                      <p>
                        Replacement response; the original author has not
                        agreed.
                      </p>
                    )}
                  </div>
                ))}
              {history.map((c: Dict) => (
                <blockquote key={c.id}>
                  <b>Revision {c.revision}</b>
                  <p>{c.text}</p>
                  <p>{c.change_reason}</p>
                </blockquote>
              ))}
            </details>
            <h4>Attached evidence</h4>
            {sources.length ? (
              sources.map((s: Dict) => (
                <details key={s.id}>
                  <summary>
                    {s.provenance} · {s.origin} · {s.integrity}
                  </summary>
                  <p>{s.content}</p>
                  <p>
                    Relation: {s.relation}.{" "}
                    {s.assessment_reason
                      ? `Human assessment: ${s.assessment_reason}`
                      : "Relevance has not been assessed."}
                  </p>
                </details>
              ))
            ) : (
              <p>No evidence is attached to this revision.</p>
            )}
            <details>
              <summary>Attach a source or existing tool result</summary>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  act(() =>
                    mutate("evidence", {
                      claim_id: claim.claim_id,
                      claim_revision: claim.revision,
                      content: source,
                      provenance,
                      relation,
                      evidence_id: toolEvidence || null,
                      assessment_reason: assessment,
                      supported_scope: supportedScope,
                      scope_coverage: scopeCoverage,
                      directness,
                      reproduction,
                    }),
                  );
                }}
              >
                <label>
                  Source excerpt
                  <textarea
                    aria-label="Source excerpt"
                    maxLength={16000}
                    rows={4}
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                  />
                </label>
                <label>
                  Provenance
                  <input
                    aria-label="Source provenance"
                    required
                    minLength={3}
                    value={provenance}
                    onChange={(e) => setProvenance(e.target.value)}
                  />
                </label>
                <label>
                  Existing tool evidence ID, if applicable
                  <input
                    value={toolEvidence}
                    onChange={(e) => setToolEvidence(e.target.value)}
                  />
                </label>
                <label>
                  Relation
                  <select
                    value={relation}
                    onChange={(e) => setRelation(e.target.value)}
                  >
                    <option value="supports">Supports this scoped claim</option>
                    <option value="challenges">
                      Challenges this scoped claim
                    </option>
                  </select>
                </label>
                <label>
                  Your relevance and scope assessment, if checked
                  <textarea
                    aria-label="Source assessment"
                    value={assessment}
                    maxLength={2000}
                    onChange={(e) => setAssessment(e.target.value)}
                  />
                </label>
                <p>
                  Leaving the assessment blank attaches the source without
                  marking its relevance checked. A URL alone is not verified
                  evidence.
                </p>
                {["reviewed_v2", "reviewed_v3", "reviewed_v4"].includes(
                  review.contract.protocol_version,
                ) && (
                  <>
                    <label>
                      Scope supported by this source
                      <input
                        aria-label="Supported evidence scope"
                        value={supportedScope}
                        maxLength={500}
                        onChange={(e) => setSupportedScope(e.target.value)}
                      />
                    </label>
                    <label>
                      Scope coverage
                      <select
                        aria-label="Evidence scope coverage"
                        value={scopeCoverage}
                        onChange={(e) => setScopeCoverage(e.target.value)}
                      >
                        <option value="unknown">Not assessed</option>
                        <option value="partial">Only part of the claim</option>
                        <option value="whole_claim_as_assessed">
                          Whole current claim, within assessed scope
                        </option>
                      </select>
                    </label>
                    <label>
                      Evidence relation
                      <select
                        value={directness}
                        onChange={(e) => setDirectness(e.target.value)}
                      >
                        <option value="unknown">Unknown</option>
                        <option value="direct">
                          Direct within stated scope
                        </option>
                        <option value="indirect">Indirect</option>
                      </select>
                    </label>
                    <label>
                      Reproduction material or limitations
                      <textarea
                        value={reproduction}
                        maxLength={1000}
                        onChange={(e) => setReproduction(e.target.value)}
                      />
                    </label>
                    <p>
                      A supplied source supports only the scope you explicitly
                      assess. Its origin is preserved.
                    </p>
                  </>
                )}
                <button disabled={busy}>Attach evidence</button>
              </form>
            </details>
          </section>
        )}
        <ScopedReviewLedger review={review} />
        <details>
          <summary>Coverage & unreviewed material</summary>
          <p>
            Extraction coverage is a model opinion. Material outside the listed
            claims remains unreviewed.
          </p>
          {review.coverage.map((c: Dict) => (
            <p key={c.message_id}>
              {c.assessment}: {c.omitted_material}
            </p>
          ))}
          {review.partial_reasons.map((s: string, i: number) => (
            <p key={i}>{s}</p>
          ))}
          {review.stale && <p>The recheck is stale after a context change.</p>}
        </details>
        {next &&
          ["extraction", "scrutiny", "repair", "recheck", "synthesis"].includes(
            next.phase,
          ) &&
          ["paused", "failed", "unavailable", "interrupted"].includes(
            chat.status,
          ) && (
            <details>
              <summary>Reassign the next incomplete phase</summary>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  act(() =>
                    mutate("reassignments", {
                      phase: next.phase,
                      participant_id: member,
                      original_author_id: next.author_id || null,
                      reason,
                    }),
                  );
                }}
              >
                <p>
                  Next: {next.phase}. Reassignment stays within the selected
                  models and does not reset attempt limits.
                </p>
                <label>
                  Available member
                  <select
                    required
                    value={member}
                    onChange={(e) => setMember(e.target.value)}
                  >
                    <option value="">Choose a member</option>
                    {data.active_members.map((p: Dict) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Reason
                  <input
                    required
                    minLength={5}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <button disabled={busy}>Record reassignment</button>
                <p>Resume the council after the assignment is recorded.</p>
              </form>
            </details>
          )}
        <details>
          <summary>Change the question or contract · new cycle</summary>
          <p>
            Pause and wait for the current request first. Existing claims and
            answers remain in history. A new complete cycle must fit the
            remaining allowance.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(() => mutate("contracts", { question, options }));
            }}
          >
            <label>
              Question
              <textarea
                required
                minLength={3}
                maxLength={8000}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
            </label>
            <ReviewSetup value={options} onChange={setOptions} />
            <button
              disabled={
                busy ||
                !!chat.active_turn ||
                ["running", "waiting"].includes(chat.status)
              }
            >
              Start revised cycle
            </button>
          </form>
        </details>
        <footer>
          <button disabled={busy} onClick={download}>
            <Download size={15} /> Download review pack
          </button>
          <small>
            Includes claims, revisions, source artifacts and offline label
            reconstruction.
          </small>
        </footer>
      </aside>
    </div>
  );
}
