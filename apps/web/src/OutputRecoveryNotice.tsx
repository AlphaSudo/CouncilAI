import { CouncilBody } from "./CouncilBody";
import type { Dict } from "./types";
import "./output-recovery.css";

const tokens = (value: number | null) =>
  value == null ? "Unknown" : value.toLocaleString();

export function OutputRecoveryNotice({
  value,
  busy,
  needsAcknowledgement,
  onRecover,
  modelRecovery,
  onContinueWithoutModel,
}: {
  value: Dict;
  busy: boolean;
  needsAcknowledgement: boolean;
  onRecover: () => void;
  modelRecovery?: Dict;
  onContinueWithoutModel?: () => void;
}) {
  return (
    <section
      className="output-recovery"
      aria-label="Saved response recovery"
      role="alert"
    >
      <strong>{value.name} reached its output limit</strong>
      {value.attempts_used != null && (
        <p>
          {value.attempts_used} of {value.attempt_limit} request attempts used.{" "}
          ${Number(value.global_remaining_usd).toFixed(4)} remains under the
          shared $24 total cap.
        </p>
      )}
      <dl className="output-recovery-tokens">
        <div>
          <dt>Reasoning tokens</dt>
          <dd>{tokens(value.reasoning_tokens)}</dd>
        </div>
        <div>
          <dt>Answer tokens</dt>
          <dd>{tokens(value.answer_tokens)}</dd>
        </div>
        <div>
          <dt>Total output</dt>
          <dd>{tokens(value.output_tokens)}</dd>
        </div>
      </dl>
      {value.limited_by_local_allowance && (
        <p>
          This saved attempt was restricted by the earlier local chat limit to{" "}
          {tokens(value.generation?.effective_output_tokens)} combined reasoning
          and answer tokens.
        </p>
      )}
      {value.has_saved_answer ? (
        <details>
          <summary>View saved partial answer</summary>
          <div className="council-message-body output-recovery-draft">
            <CouncilBody text={value.partial_answer} />
          </div>
          {value.preview_truncated && (
            <p>Preview shortened. The full saved draft is used for recovery.</p>
          )}
        </details>
      ) : (
        <p>No public answer text was saved.</p>
      )}
      <p>
        {value.has_saved_answer
          ? "Reuse the saved draft and context with an instruction to finish the answer now. "
          : "Use the saved question and context with an instruction to answer now. "}
        Internal reasoning cannot be resumed. This starts a new billed request
        within your remaining allowance.
      </p>
      {value.mode === "complete_stage" && value.has_saved_answer && (
        <p>
          This review step requires a complete result; the saved draft is reused
          as context.
        </p>
      )}
      {value.reason && <p>{value.reason}</p>}
      {needsAcknowledgement && (
        <p>
          Acknowledge the earlier unknown charge below before starting another
          request.
        </p>
      )}
      <button
        type="button"
        disabled={busy || !value.available || needsAcknowledgement}
        onClick={onRecover}
      >
        {value.action_label}
      </button>
      {modelRecovery && onContinueWithoutModel && (
        <>
          <button
            type="button"
            disabled={busy || needsAcknowledgement || !modelRecovery.allowed}
            onClick={onContinueWithoutModel}
          >
            {modelRecovery.action_label}
          </button>
          <p>
            Continue this chat with the other models and preserve completed
            answers. {modelRecovery.name} will stay excluded from later turns in
            this chat; its recorded cost remains counted.
          </p>
          {modelRecovery.reason && <p>{modelRecovery.reason}</p>}
        </>
      )}
    </section>
  );
}
