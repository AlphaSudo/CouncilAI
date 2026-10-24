import type { Dict } from "./types";

const label = (s: string) => s?.replaceAll("_", " ") || "Unknown";

export function ObservationWarnings({
  observations,
  messageId,
  onInspect,
}: {
  observations: Dict[];
  messageId: string;
  onInspect: () => void;
}) {
  const items = observations.filter((o) => o.source_message_id === messageId);
  if (!items.length) return null;
  return (
    <aside
      className="review-observation-warning"
      aria-label="Reported observation warning"
    >
      <b>Reported observation · unverified</b>
      <p>
        {items.some((o) => o.classification === "unsupported_self_report")
          ? "This answer includes a reported test or measurement without established execution evidence."
          : "A source passage may describe an observation. Its origin and relevance require assessment."}
      </p>
      <button onClick={onInspect}>Inspect provenance</button>
    </aside>
  );
}

export function ScopedClaimDetails({
  review,
  claim,
  decision,
}: {
  review: Dict;
  claim: Dict;
  decision: Dict;
}) {
  if (!decision?.review_state) return null;
  return (
    <div className="review-scoped-detail">
      {["reviewed_v3", "reviewed_v4"].includes(review.contract.protocol_version) && (
        <details className="council-audit-details">
          <summary>
            Scoped checks ·{" "}
            {review.audit_results?.filter(
              (a: Dict) => a.claim_id === claim.claim_id,
            ).length || 0}
          </summary>
          <p>
            Checks apply to their declared inputs and scope. They do not certify
            the whole assertion.
          </p>
          {review.audit_results
            ?.filter((a: Dict) => a.claim_id === claim.claim_id)
            .map((a: Dict) => (
              <section key={a.audit_id}>
                <b>{label(a.state)}</b>
                <p>{a.reason}</p>
                {a.value !== undefined && (
                  <p>
                    Calculated value: {a.value} {a.unit}
                  </p>
                )}
                <p>{a.scope}</p>
                <small>{a.limitations}</small>
                {a.inputs?.descriptor?.expression && (
                  <p>
                    Expression: <code>{a.inputs.descriptor.expression}</code>
                  </p>
                )}
                {a.inputs?.descriptor?.quantities?.map((q: Dict) => (
                  <p key={q.name}>
                    {q.name}: {q.value ?? "Unknown"} {q.unit} ·{" "}
                    {label(q.quantity_kind)}. Basis: {q.basis}
                  </p>
                ))}
              </section>
            ))}
          {!review.audit_results?.some(
            (a: Dict) => a.claim_id === claim.claim_id,
          ) && <p>No typed local check was admitted for this assertion.</p>}
        </details>
      )}
      <dl className="review-role-list">
        <div>
          <dt>Objection review</dt>
          <dd>{label(decision.review_state)}</dd>
        </div>
        <div>
          <dt>Evidence</dt>
          <dd>{label(decision.evidence_state)}</dd>
        </div>
        <div>
          <dt>Decision use</dt>
          <dd>{label(decision.decision_suitability)}</dd>
        </div>
        <div>
          <dt>Claim kind</dt>
          <dd>
            {label(claim.reasoning_kind)}
            {claim.properties?.length
              ? ` · ${claim.properties.map(label).join(", ")}`
              : ""}
          </dd>
        </div>
      </dl>
      <p>
        <b>Evidence needed:</b> {claim.evidence_obligation}
      </p>
      <p>
        <b>Extraction fidelity:</b> {label(claim.fidelity)} — model assessment.
      </p>
      <details>
        <summary>Original passages & normalized assertion</summary>
        <p>
          <b>Current assertion:</b> {claim.text}
        </p>
        <p>
          The assertion is a model interpretation. Original text and qualifiers
          remain below.
        </p>
        {claim.source_spans?.map((s: Dict) => (
          <blockquote key={s.id}>
            <p>{s.text}</p>
            <small>
              Original characters {s.start}–{s.end} · {s.hash}
            </small>
          </blockquote>
        ))}
      </details>
      {!!decision.required_caveats?.length && (
        <ul>
          {decision.required_caveats.map((s: string, i: number) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      )}
      {!!decision.residual_risks?.length && (
        <details open>
          <summary>Ordinary residual risks</summary>
          {decision.residual_risks.map((r: Dict, i: number) => (
            <p key={i}>
              {r.detail} <small>Model assessment; {r.affected_scope}</small>
            </p>
          ))}
        </details>
      )}
      {review.concerns
        ?.filter(
          (c: Dict) => c.claim_id === claim.claim_id && c.kind === "new_issue",
        )
        .map((c: Dict) => (
          <p className="review-observation-warning" key={c.id}>
            <b>New concern · {label(c.review_state)}</b>
            <br />
            {c.detail}
          </p>
        ))}
    </div>
  );
}

export function ScopedReviewLedger({ review }: { review: Dict }) {
  if (
    !["reviewed_v2", "reviewed_v3", "reviewed_v4"].includes(review.contract.protocol_version)
  )
    return null;
  return (
    <>
      {["reviewed_v3", "reviewed_v4"].includes(review.contract.protocol_version) && (
        <>
          <details>
            <summary>Review coverage</summary>
            <p>
              {label(review.inventory_status)}: {review.inventory_limitations}
            </p>
            {review.inventory?.map((item: Dict, index: number) => (
              <p key={index}>
                <b>{label(item.category)}</b>: {item.description}
              </p>
            ))}
            <p>Material outside this batch remains unreviewed.</p>
          </details>
          <details>
            <summary>
              Approach families · {review.families?.length || 0}
            </summary>
            {review.families?.map((family: Dict) => (
              <section key={family.id}>
                <b>
                  {family.name}
                  {family.stale ? " · needs recheck" : ""}
                </b>
                <p>{family.mechanism}</p>
                <p>Assumptions: {family.assumptions}</p>
                <p>Resources: {family.resources}</p>
                <p>Distinguishing test: {family.distinguishing_test}</p>
                <small>Grouping is a model assessment.</small>
              </section>
            ))}
          </details>
          {review.focus_decision && (
            <p className="review-audit-note">{review.focus_decision.reason}</p>
          )}
        </>
      )}
      <details>
        <summary>Claim groups · {review.groups?.length || 0}</summary>
        <p>
          Grouping is a model assessment. Each author, revision, objection and
          evidence record remains separate.
        </p>
        {review.groups?.map((g: Dict) => (
          <section className="review-group" key={g.id}>
            <b>
              {label(g.relation)}
              {g.stale ? " · split or stale after revision" : ""}
            </b>
            <p>{g.reason}</p>
            <ul>
              {g.members.map((m: Dict) => (
                <li key={m.claim_id}>
                  {m.claim_id} v{m.revision}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </details>
      <details>
        <summary>
          Reported observations & provenance ·{" "}
          {review.observations?.length || 0}
        </summary>
        <p>
          {review.observation_coverage ||
            "Cue detection is incomplete and may miss or misclassify observations."}
        </p>
        {review.observations?.map((o: Dict) => (
          <section key={o.id} className="review-group">
            <b>{label(o.classification)}</b>
            <blockquote>{o.text}</blockquote>
            <p>{o.reason}</p>
            <small>
              {label(o.origin)} · {o.source_message_id}
            </small>
          </section>
        ))}
      </details>
    </>
  );
}
