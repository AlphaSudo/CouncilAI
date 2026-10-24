import React, { useEffect, useId, useRef, useState } from "react";
import { Minimize2, RotateCcw } from "lucide-react";
import { api } from "./api";
import type { Dict } from "./types";
import "./council-context.css";

const tokens = (value: number) => value.toLocaleString("en-US");

export function CouncilContext({
  status,
  chatId,
  explain,
  onChange,
}: {
  status: Dict;
  chatId?: string;
  explain: boolean;
  onChange: () => Promise<void>;
}) {
  const id = useId();
  const panel = useRef<HTMLElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState<React.CSSProperties>({
    right: 20,
    bottom: 60,
  });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  function positionPanel() {
    if (!trigger.current) return;
    const bounds = trigger.current.getBoundingClientRect();
    const above = Math.max(0, bounds.top - 28);
    const below = Math.max(0, innerHeight - bounds.bottom - 28);
    const width = Math.min(360, innerWidth - 40);
    setPosition({
      right: Math.min(
        Math.max(20, innerWidth - bounds.right),
        innerWidth - width - 20,
      ),
      ...(above >= below
        ? {
            bottom: innerHeight - bounds.top + 8,
            maxHeight: Math.min(560, above),
          }
        : { top: bounds.bottom + 8, maxHeight: Math.min(560, below) }),
    });
  }
  useEffect(() => {
    const reposition = () => {
      if (panel.current?.matches(":popover-open")) positionPanel();
    };
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, []);
  if (!status?.supported) return null;
  const latest = status.latest;
  const percent = latest?.percent;
  const capacity = latest?.capacity_tokens || status.capacity_tokens;
  const checkpoint = status.last_compaction;
  const compactMode = status.mode === "compact";
  const ring = 2 * Math.PI * 12;
  const pressure =
    percent == null
      ? "unknown"
      : percent >= 90
        ? "high"
        : percent >= 80
          ? "near"
          : "normal";

  async function compact(mode: "compact" | "adaptive") {
    if (!chatId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/chats/${chatId}/context/compact`, { mode });
      await onChange();
      setNotice(
        mode === "compact"
          ? "Ready for the next request. No extra model call was made."
          : "Automatic compaction restored.",
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="council-context" data-pressure={pressure}>
      <button
        type="button"
        className="context-trigger"
        ref={trigger}
        popoverTarget={id}
        onClick={positionPanel}
        aria-controls={id}
        title="Context usage"
        aria-label={
          percent == null
            ? "Context usage, not measured yet"
            : `Context usage, ${percent}% of ${tokens(capacity)} tokens in the last request`
        }
      >
        <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
          <circle className="context-ring-track" cx="16" cy="16" r="12" />
          <circle
            className="context-ring-fill"
            cx="16"
            cy="16"
            r="12"
            strokeDasharray={ring}
            strokeDashoffset={ring * (1 - Math.min(100, percent || 0) / 100)}
            transform="rotate(-90 16 16)"
          />
        </svg>
        <span>
          <span className="context-trigger-label">Context </span>
          <strong>{percent == null ? "—" : `${Math.round(percent)}%`}</strong>
        </span>
      </button>
      <section
        className="context-popover"
        id={id}
        aria-label="Context details"
        popover="auto"
        ref={panel}
        style={position}
      >
        <div className="context-heading">
          <strong>Context window</strong>
          <span>{tokens(capacity)} tokens</span>
        </div>
        {latest ? (
          <>
            <p className="context-count">
              <strong>
                {tokens(latest.used_tokens ?? latest.input_tokens)}
              </strong>{" "}
              / {tokens(capacity)} tokens
            </p>
            <p>
              {tokens(latest.input_tokens)} estimated input tokens
              {latest.output_tokens != null
                ? ` + ${tokens(latest.output_tokens)} reported output tokens, including reasoning.`
                : "; output token usage is not reported yet."}
            </p>
            <p>
              Last request · {latest.model.split("/").pop()}.{" "}
              {tokens(latest.remaining_tokens)} tokens remain for output and
              further input.
            </p>
            {latest.reserved_output_tokens != null && (
              <p>
                {tokens(latest.reserved_output_tokens)} tokens were reserved for
                that response.
              </p>
            )}
            <p className="context-measurement">
              Input uses the local model tokenizer with a framing allowance.
              Reported output is added once. This is one request, not your
              conversation's accumulated token bill.
            </p>
          </>
        ) : (
          <p>
            Usage will appear when the first request is prepared. Your full
            conversation stays saved.
          </p>
        )}
        <div className="context-compaction-status">
          <strong>
            {compactMode ? "Compaction ready" : "Automatic compaction"}
          </strong>
          <p>
            {compactMode
              ? "The next review request will compact repeated text when it saves space."
              : `Repeated text is compacted near ${status.automatic_threshold_percent}% input usage, with room reserved for the answer.`}
          </p>
          <p>
            Exact text stays available through shared references. No summary
            call or conversation deletion.
          </p>
          {checkpoint && (
            <p className="context-saved">
              Last compaction saved {tokens(checkpoint.saved_input_tokens)}{" "}
              input tokens for {checkpoint.model.split("/").pop()}.
            </p>
          )}
        </div>
        {explain && latest && (
          <details className="context-model-detail">
            <summary>Per-model measurements</summary>
            {(status.models || []).map((model: Dict) => (
              <div key={model.model} className="context-model-row">
                <span>{model.model.split("/").pop()}</span>
                <strong>
                  {tokens(model.input_tokens)} · {model.percent}%
                </strong>
                <small>
                  Latest local input estimate
                  {model.provider_reported_input_tokens != null
                    ? ` · provider reported ${tokens(model.provider_reported_input_tokens)}`
                    : " · provider input not reported"}
                </small>
              </div>
            ))}
            <p>
              Compaction checkpoints: {status.compactions}.{" "}
              {checkpoint
                ? "Lossless reconstruction verified before dispatch."
                : "No compacted request has been sent yet."}
            </p>
          </details>
        )}
        {chatId && (
          <div className="context-actions">
            <button
              type="button"
              disabled={busy || compactMode}
              onClick={() => compact("compact")}
            >
              <Minimize2 size={14} />
              {busy
                ? "Preparing…"
                : compactMode
                  ? "Ready for next request"
                  : "Compact context"}
            </button>
            {compactMode && explain && (
              <button
                type="button"
                disabled={busy}
                onClick={() => compact("adaptive")}
                aria-label="Restore automatic compaction"
              >
                <RotateCcw size={14} />
              </button>
            )}
          </div>
        )}
        <p className="context-action-notice" role="status">
          {notice}
        </p>
        {error && <p role="alert">{error}</p>}
      </section>
    </div>
  );
}
