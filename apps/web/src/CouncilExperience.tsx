import { useEffect, useState } from "react";
import { ArrowDown, CircleHelp, SlidersHorizontal } from "lucide-react";
import type { Dict } from "./types";

export type CouncilView = "simple" | "explain";
const preferenceKey = "zerowall.council.view";

export function useCouncilView() {
  const [view, setView] = useState<CouncilView>(() => {
    try {
      return localStorage.getItem(preferenceKey) === "explain"
        ? "explain"
        : "simple";
    } catch {
      return "simple";
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(preferenceKey, view);
    } catch {
      // The current view still works when browser storage is unavailable.
    }
  }, [view]);
  return [view, setView] as const;
}

export function CouncilViewSwitch({
  view,
  onChange,
}: {
  view: CouncilView;
  onChange: (view: CouncilView) => void;
}) {
  return (
    <div
      className="council-view-switch"
      role="group"
      aria-label="Interface view"
    >
      <button
        type="button"
        aria-pressed={view === "simple"}
        onClick={() => onChange("simple")}
        title="A quiet view of your question and the answer"
      >
        Simple
      </button>
      <button
        type="button"
        aria-pressed={view === "explain"}
        onClick={() => onChange("explain")}
        title="Follow the discussion, inspect checks and debug execution"
      >
        Explain
      </button>
    </div>
  );
}

export function CouncilProcessIntro() {
  return (
    <div className="council-process-intro">
      <span className="council-eyebrow">How the council works</span>
      <ol>
        <li>
          <span>01</span>
          <div>
            <strong>Think independently</strong>
            <p>Each model answers before seeing the others.</p>
          </div>
        </li>
        <li>
          <span>02</span>
          <div>
            <strong>Challenge & revise</strong>
            <p>They question claims and respond to objections.</p>
          </div>
        </li>
        <li>
          <span>03</span>
          <div>
            <strong>Bring it together</strong>
            <p>The lead writes an answer with its limits intact.</p>
          </div>
        </li>
      </ol>
    </div>
  );
}

export function CouncilDiagnostics({
  data,
  preview,
  provider,
  selectedCount,
  planned,
}: {
  data: Dict | null;
  preview: Dict | null;
  provider: string;
  selectedCount: number;
  planned: number;
}) {
  const review = data?.review;
  const roles = review?.roles || preview?.role_names || {};
  const attempts = data?.budget?.attempts;
  const roleLabels: Record<string, string> = {
    extraction: "Key claims",
    scrutiny: "Challenges",
    repair: "Author responses",
    recheck: "Checks",
    synthesis: "Final answer",
  };
  const snapshot = {
    chat_id: data?.chat?.id || null,
    protocol: data?.chat?.protocol?.version || preview?.review_protocol || null,
    provider: data?.chat?.provider || provider,
    status: data?.chat?.status || "not_started",
    cycle: review?.cycle || null,
    next_phase: data?.next_turn?.phase || null,
    attempts: attempts ?? null,
    remaining_daily_attempts: data?.direct_capacity?.daily_remaining ?? null,
    retry_wait: data?.chat?.retry_wait || null,
    partial_reasons: review?.partial_reasons || [],
    plan_hash: review?.plan_hash || null,
    decision_hash: review?.decision_hash || null,
    execution_plan: review?.execution_plan || null,
    roles,
  };
  return (
    <aside className="council-diagnostics" aria-label="Council diagnostics">
      <header>
        <SlidersHorizontal size={16} aria-hidden="true" />
        <strong>Behind the answer</strong>
        <span>Explain view</span>
      </header>
      <p>
        This view shows the same council, with the process and execution details
        visible.
      </p>
      <dl className="council-diagnostic-metrics">
        <div>
          <dt>Participants</dt>
          <dd>{data?.chat?.participants?.length ?? selectedCount}</dd>
        </div>
        <div>
          <dt>{data ? "Attempts so far" : "Planned calls"}</dt>
          <dd>{attempts ?? planned}</dd>
        </div>
        {review && (
          <>
            <div>
              <dt>Claims mapped</dt>
              <dd>{review.claims?.length ?? 0}</dd>
            </div>
            <div>
              <dt>Local checks</dt>
              <dd>{review.audit_results?.length ?? 0}</dd>
            </div>
          </>
        )}
      </dl>
      <section>
        <h3>{data ? "Current execution" : "Before you start"}</h3>
        <p>
          {data
            ? "A finished reply does not mean every claim is verified. Open Claims & evidence to inspect its status and source."
            : "Calls are reserved before starting. Provider limits can still pause the council; replies already received stay saved."}
        </p>
        {Object.keys(roles).length > 0 && (
          <details>
            <summary>Role assignments</summary>
            <dl className="council-role-summary">
              {Object.entries(roles).map(([role, value]) => (
                <div key={role}>
                  <dt>{roleLabels[role] || role.replaceAll("_", " ")}</dt>
                  <dd>
                    {data?.chat?.participants?.find(
                      (participant: Dict) => participant.id === value,
                    )?.name ||
                      (typeof value === "string"
                        ? value
                        : JSON.stringify(value))}
                  </dd>
                </div>
              ))}
            </dl>
          </details>
        )}
      </section>
      <section className="council-diagnostic-boundary">
        <CircleHelp size={16} aria-hidden="true" />
        <p>
          Model agreement is not evidence. Checks apply only to their stated
          inputs and scope.
        </p>
      </section>
      <details className="council-execution-snapshot">
        <summary>Execution snapshot</summary>
        <pre>{JSON.stringify(snapshot, null, 2)}</pre>
      </details>
    </aside>
  );
}

export function CouncilAnswerJump({ finalId }: { finalId: string }) {
  return (
    <button
      className="council-answer-jump"
      onClick={() =>
        document.getElementById(finalId)?.scrollIntoView({
          block: "start",
          behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto"
            : "smooth",
        })
      }
    >
      <ArrowDown size={14} aria-hidden="true" /> Go to answer
    </button>
  );
}

export function groupCouncilMessages(messages: Dict[]) {
  const groups: { id: string; messages: Dict[]; discussion: boolean }[] = [];
  for (const message of messages) {
    const discussion =
      message.role === "assistant" && message.phase !== "synthesis";
    const previous = groups.at(-1);
    if (discussion && previous?.discussion) previous.messages.push(message);
    else groups.push({ id: message.id, messages: [message], discussion });
  }
  return groups;
}
