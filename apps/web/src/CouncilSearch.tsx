import { useState } from "react";
import { Globe2, LoaderCircle } from "lucide-react";
import { api } from "./api";
import type { Dict } from "./types";
import "./council-search.css";

// A quiet composer switch; search status stays attached to the actual reply.
// One control, one state, no modal. In-flight replies keep their own setting.
export function CouncilSearch({
  chat,
  configured,
  selected,
  onSelect,
  onData,
}: {
  chat: Dict | null;
  configured: boolean;
  selected: boolean;
  onSelect: (value: boolean) => void;
  onData: (value: Dict) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const enabled =
    configured &&
    (chat
      ? (chat.next_turn_research_enabled ??
        chat.next_research_enabled ??
        chat.research_enabled)
      : selected);
  return (
    <div className="council-search-control">
      <button
        type="button"
        role="switch"
        aria-label="Web search"
        aria-checked={!!enabled}
        className={`council-search-toggle ${enabled ? "is-on" : ""}`}
        disabled={busy || !configured}
        title={
          !configured
            ? "Web search is not configured"
            : enabled
              ? "Models research together before opening answers, then search as they discuss. Click to turn off for upcoming replies."
              : "Turn on web search for upcoming model replies"
        }
        onClick={async () => {
          if (!chat) {
            onSelect(!enabled);
            return;
          }
          setBusy(true);
          setError("");
          try {
            onData(
              await api(`/chats/${chat.id}/research/settings`, {
                enabled: !enabled,
              }),
            );
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? (
          <LoaderCircle size={15} className="council-spin" />
        ) : (
          <Globe2 size={15} />
        )}
        <span className="council-search-label">Search</span>
        <span className="council-search-state">{enabled ? "On" : "Off"}</span>
      </button>
      {error && (
        <span role="alert" className="council-search-error">
          {error}
        </span>
      )}
    </div>
  );
}

export function ReplySearch({
  value,
  explain,
}: {
  value?: Dict;
  explain: boolean;
}) {
  if (!value) return null;
  const label =
    value.status === "completed"
      ? value.collective_research_id
        ? `Shared research · ${value.shared_source_count || 0} sources · ${value.extracted_pages || 0} pages saved`
        : `${value.reused ? "Cached search" : "Web searched"} · ${value.result_count || 0} results`
      : "Web search unavailable";
  return (
    <div className="council-reply-search" title={value.reason || value.query}>
      <Globe2 size={13} />
      <span>{label}</span>
      {explain && (
        <details>
          <summary>Search details</summary>
          <p>{value.query}</p>
          {value.reason && <p>{value.reason}</p>}
          <p>
            Retrieved passages are saved in Sources. Retrieval does not verify a
            claim.
          </p>
        </details>
      )}
    </div>
  );
}
