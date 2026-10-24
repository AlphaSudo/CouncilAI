import type { Dict } from "./types";

export function ConversationTotals({ accounting }: { accounting?: Dict }) {
  if (!accounting) return null;
  const total = accounting.total;
  const attempts = total.attempts || 0;
  const tokens = (key: string) => {
    if (!attempts) return "0";
    const item = total.tokens?.[key];
    if (!item?.reported_attempts) return "Unknown";
    return `${item.reported_attempts < attempts ? "≥" : ""}${item.known_subtotal.toLocaleString("en-US")}`;
  };
  const subtotal = total.known_reference_subtotal_usd;
  const cost = !attempts
    ? "$0.00"
    : subtotal == null
      ? "Unknown"
      : `${total.complete_estimates < attempts ? "≥" : ""}$${Number(subtotal).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 6 })}`;
  return (
    <div
      className="council-conversation-totals"
      role="group"
      aria-label="Conversation totals"
    >
      <span>
        Input <strong>{tokens("input_total_reported")}</strong>
      </span>
      <span title="Total output includes reasoning tokens once.">
        Output <strong>{tokens("output_total_reported")}</strong>
      </span>
      <span title="Known token usage at published rates. Unreported requests remain unknown.">
        Estimated cost <strong>{cost}</strong>
      </span>
      {attempts > 0 && total.usage_reported_attempts < attempts && (
        <small>
          Partial · {total.usage_reported_attempts}/{attempts} requests reported
        </small>
      )}
    </div>
  );
}
