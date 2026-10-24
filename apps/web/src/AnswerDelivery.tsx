import { useState } from "react";
import { CouncilBody } from "./CouncilBody";
import { CopyTextButton } from "./CouncilCopy";
import type { Dict } from "./types";
import "./answer-delivery.css";

// Visual thesis: a quiet dark reading surface with one muted status accent.
// Content: public response first, one consequence note, optional detailed inspection.
// Interaction: stable streamed text, native detail disclosure, reduced-motion support.
export function publicAnswerPreview(data: Dict): Dict | null {
  const active = data.chat?.active_turn;
  if (!active || !["opening", "synthesis"].includes(active.phase)) return null;
  const callId = data.active_request?.call_id;
  const stream = data.public_streams?.find(
    (item: Dict) => item.call_id === callId,
  );
  if (!stream || data.messages?.some((m: Dict) => m.call_id === callId))
    return null;
  const text = stream.chunks.map((chunk: Dict) => chunk.text).join("");
  // Review metadata and research actions are never a public answer preview.
  if (!text.trim() || /^(\s*[\[{]|\s*```json)/.test(text)) return null;
  return {
    ...active,
    id: `live-${callId}`,
    call_id: callId,
    role: "assistant",
    content: text,
    isLive: true,
  };
}

export function LivePublicAnswer({ data }: { data: Dict }) {
  const preview = publicAnswerPreview(data);
  if (!preview) return null;
  const active = data.chat.active_turn;
  const text = preview.content;
  return (
    <article
      className="council-message live-public-answer"
      aria-label={`Live answer from ${active.name}`}
    >
      <div className="council-message-main">
        <div className="council-message-heading">
          <strong>{active.name}</strong>
          <span>Answer arriving</span>
          <CopyTextButton
            text={text}
            label={`Copy current answer from ${active.name}`}
          />
        </div>
        <div className="council-message-content">
          <CouncilBody text={text} />
        </div>
      </div>
    </article>
  );
}

export function ReviewDeliveryNote({
  data,
  explain,
}: {
  data: Dict;
  explain: boolean;
}) {
  const [open, setOpen] = useState(false);
  const incomplete =
    data.chat?.review_state === "incomplete" || data.review?.delivery_degraded;
  if (!incomplete) return null;
  const details = {
    states: data.stage_results || [],
    warnings: [
      ...(data.review?.warnings || []),
      ...(data.review?.delivery_warnings || []),
    ],
    quarantined: data.review?.quarantine || [],
    admissions: data.review?.admission_records || [],
    decision_brief: data.review?.decision_brief || null,
    discussion_continuity: data.review?.discussion_continuity || null,
  };
  return (
    <div className="review-delivery-note">
      <span role="status">
        {data.review?.discussion_continuity
          ? "Formal review labels are incomplete. The council continued with a discussion."
          : "Some review details are unavailable. Received answers are saved."}
      </span>
      {explain && (
        <>
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            Review details
          </button>
          {open && (
            <pre aria-label="Review delivery diagnostics">
              {JSON.stringify(details, null, 2)}
            </pre>
          )}
        </>
      )}
    </div>
  );
}
