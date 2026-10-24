import type { Dict } from "./types";

export function ModelRecoveryNotice({
  value,
  busy,
  needsAcknowledgement,
  onContinue,
}: {
  value: Dict;
  busy: boolean;
  needsAcknowledgement: boolean;
  onContinue: () => void;
}) {
  const extra = Number(value.additional_allowance_usd || 0);
  return (
    <section
      className="council-method-note"
      aria-label="Continue saved council"
    >
      <div>
        <strong>Continue this chat with the other models</strong>
        <p>
          Skip {value.name || "Lightning"}'s unfinished opening and keep the
          completed answers.
          {value.unknown_charge_retained !== false
            ? " Its earlier unknown charge stays counted."
            : " Its recorded token cost stays counted."}{" "}
          {value.name || "Lightning"} will stay excluded from later turns in
          this chat.
        </p>
        {extra > 0 && (
          <p>
            This action adds ${extra.toFixed(2)} to this conversation's
            existing-credit allowance, within the same $24 total cap. It does
            not release the earlier reservation.
          </p>
        )}
        {!value.allowed && <p role="status">{value.reason}</p>}
        <button
          type="button"
          disabled={busy || needsAcknowledgement || !value.allowed}
          onClick={onContinue}
        >
          {value.action_label}
          {extra > 0 ? ` · add $${extra.toFixed(2)} allowance` : ""}
        </button>
      </div>
    </section>
  );
}
