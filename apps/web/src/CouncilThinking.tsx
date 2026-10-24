import React, { useState } from "react";
import { api } from "./api";
import type { Dict } from "./types";
import "./council-thinking.css";

export type ThinkingLevel = "quick" | "balanced" | "deep" | "maximum";
const fallbackLevels = [
  { id: "quick", label: "Quick", reasoning_tokens: 2000 },
  { id: "balanced", label: "Balanced", reasoning_tokens: 4000 },
  { id: "deep", label: "Deep", reasoning_tokens: 8000 },
  { id: "maximum", label: "Maximum", reasoning_tokens: 16000 },
];

export function CouncilThinking({
  level,
  settings,
  chatId,
  onSelect,
  onChange,
}: {
  level: ThinkingLevel;
  settings?: Dict;
  chatId?: string;
  onSelect: (level: ThinkingLevel) => void;
  onChange: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const levels = settings?.levels || fallbackLevels;
  async function select(value: ThinkingLevel) {
    setError("");
    setNotice("");
    if (!chatId) {
      onSelect(value);
      return;
    }
    setBusy(true);
    try {
      await api(`/chats/${chatId}/thinking`, { level: value });
      await onChange();
      setNotice("Thinking level saved for upcoming requests.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="council-thinking-picker">
      <label>
        <span className="thinking-label">Thinking</span>
        <select
          aria-label="Thinking level"
          title="Thinking level · advisory reasoning target; models may exceed it"
          value={level}
          disabled={busy}
          onChange={(event) => select(event.target.value as ThinkingLevel)}
        >
          {levels.map((option: Dict) => (
            <option key={option.id} value={option.id}>
              {option.label} · ≈{option.reasoning_tokens / 1000}K
            </option>
          ))}
        </select>
      </label>
      {notice && (
        <span className="thinking-notice" role="status">
          {notice}
        </span>
      )}
      {error && (
        <span className="thinking-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

export function CouncilThinkingDetails({
  settings,
  models,
  activeLevel,
}: {
  settings?: Dict;
  models: string[];
  activeLevel?: string;
}) {
  return (
    <details className="thinking-mappings">
      <summary>Model controls</summary>
      <p>
        Reasoning targets guide the model; they are not hard provider caps.
        Answer length keeps its existing context and credit limits.
      </p>
      {activeLevel && (
        <p>In progress: {activeLevel}. Its saved settings remain in effect.</p>
      )}
      {(settings?.models || [])
        .filter((model: Dict) => models.includes(model.model))
        .map((model: Dict) => (
          <div className="thinking-model" key={model.model}>
            <strong>{model.model.split("/").pop()}</strong>
            <span>
              {model.reasoning}
              {!model.native_effort_available
                ? " · token target only; no native effort levels"
                : ""}
            </span>
            {model.model_reasoning_override && (
              <span>
                {model.reasoning_budget_tokens.toLocaleString()} reasoning tokens requested;
                model override. Overruns continue without a client-side cutoff.
              </span>
            )}
          </div>
        ))}
    </details>
  );
}

export function ConversationAllowance({
  value,
  budget,
  chatId,
  onChange,
}: {
  value: Dict;
  budget?: Dict;
  chatId: string;
  onChange: () => Promise<void>;
}) {
  const [amount, setAmount] = useState("0.25");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function add() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/chats/${chatId}/allowance`, { add_usd: Number(amount) });
      await onChange();
      setNotice("Allowance updated. No model request was started.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const valid =
    Number(amount) > 0 && Number(amount) <= value.maximum_addition_usd;
  const dollars = (value: number) =>
    `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 6 })}`;
  const recorded = budget?.settled_usd;
  const reserved = budget?.reserved_usd;
  const unknown = budget?.unknown_usd;
  return (
    <details className="conversation-allowance">
      <summary>Spending details</summary>
      <p>
        {value.scope === "shared_existing_credit"
          ? "This chat shares the $24 total application cap with all other chats."
          : `This earlier chat has a ${dollars(value.cap_usd)} local limit within the $24 total cap.`}
      </p>
      <dl className="allowance-breakdown">
        <div>
          <dt>Recorded request cost</dt>
          <dd>{recorded == null ? "Not reported" : dollars(recorded)}</dd>
        </div>
        <div>
          <dt>Pending request reservations</dt>
          <dd>{reserved == null ? "Not reported" : dollars(reserved)}</dd>
        </div>
        <div>
          <dt>Unknown charges · maximum held</dt>
          <dd>{unknown == null ? "Not reported" : dollars(unknown)}</dd>
        </div>
        <div>
          <dt>Available for new requests</dt>
          <dd>{dollars(value.remaining_usd)}</dd>
        </div>
      </dl>
      {value.scope !== "shared_existing_credit" && (
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await api(`/chats/${chatId}/spending`, {
                scope: "shared_existing_credit",
              });
              await onChange();
            } catch (cause) {
              setError((cause as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          Use shared $24 total cap
        </button>
      )}
      {unknown > 0 && (
        <p className="allowance-held-note">
          The held amount is not confirmed spending. Requests interrupted before
          final usage keep their maximum reservation until their charge can be
          confirmed.
        </p>
      )}
      <p>
        {value.scope !== "shared_existing_credit" &&
          "Add existing-credit allowance below to continue in this chat. "}
        Recorded costs use returned token usage and verified rates. All chats
        share the $24 application cap.
      </p>
      {value.scope !== "shared_existing_credit" && (
        <div className="allowance-add">
          <label>
            Add existing-credit allowance ($)
            <input
              aria-label="Add existing-credit allowance ($)"
              type="number"
              min="0.01"
              max={value.maximum_addition_usd}
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
          </label>
          <button type="button" disabled={busy || !valid} onClick={add}>
            {busy ? "Updating…" : "Increase allowance"}
          </button>
        </div>
      )}
      <p role="status">
        {notice ||
          (value.scope !== "shared_existing_credit" &&
            `Up to ${dollars(value.maximum_addition_usd)} can be added within the remaining total application allowance. No model request starts when you change this.`)}
      </p>
      {error && <p role="alert">{error}</p>}
    </details>
  );
}
