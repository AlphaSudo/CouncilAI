import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Columns3, Maximize2, Minus, Plus, X } from "lucide-react";
import { CouncilBody } from "./CouncilBody";
import { CopyTextButton } from "./CouncilCopy";
import { ActiveResponseTiming } from "./ResponseTiming";
import { ReplyUsage } from "./CouncilResearch";
import { ReplySearch } from "./CouncilSearch";
import { CollectiveResearch } from "./CollectiveResearch";
import { publicAnswerPreview } from "./AnswerDelivery";
import { SavedModelReply } from "./OriginalModelReply";
import type { Dict } from "./types";
import "./council-compare.css";

// Visual thesis: a quiet, full-window reading table with aligned model columns.
// Content: bounded question, chronological stage rows, then the shared synthesis.
// Interaction: scroll through stages, inspect one reply, return to the same draft.
const phaseLabels: Record<string, string> = {
  opening: "Independent answers",
  extraction: "Key claims",
  scrutiny: "Challenges",
  repair: "Responses & revisions",
  recheck: "Checks",
  debate: "Discussion",
  synthesis: "Final answer",
  protocol_transition: "Review transition",
  participation_change: "Participation update",
  prompt: "Earlier question",
  intervention: "Your request",
};
const phaseOrder = [
  "opening",
  "extraction",
  "scrutiny",
  "repair",
  "recheck",
  "synthesis",
];
type FlowRow = {
  id: string;
  phase: string;
  cycle: number;
  round?: number;
  messages: Dict[];
  state?: string;
};
const cycleOf = (item: Dict) => item.review_cycle ?? 1;
const rowLabel = (row: FlowRow) =>
  `${phaseLabels[row.phase] || row.phase}${row.phase === "debate" && row.round ? ` · round ${row.round}` : ""}`;

function flowRows(data: Dict, questionId?: string): FlowRow[] {
  const rows: FlowRow[] = [];
  for (const message of data.messages || []) {
    if (message.id === questionId) continue;
    const previous = rows.at(-1);
    const cycle = cycleOf(message);
    if (
      message.role === "assistant" &&
      previous &&
      previous.phase === message.phase &&
      previous.cycle === cycle &&
      previous.round === message.round &&
      previous.messages.every((m) => m.role === "assistant")
    )
      previous.messages.push(message);
    else
      rows.push({
        id: message.id,
        phase: message.phase,
        cycle,
        round: message.round,
        messages: [message],
      });
  }
  const active = data.chat?.active_turn;
  if (active && ["running", "paused", "waiting"].includes(data.chat.status)) {
    const cycle = data.review?.cycle ?? cycleOf(active);
    const last = rows.at(-1);
    if (
      !last ||
      last.phase !== active.phase ||
      last.cycle !== cycle ||
      last.round !== active.round
    )
      rows.push({
        id: `active-${cycle}-${active.phase}`,
        phase: active.phase,
        cycle,
        round: active.round,
        messages: [],
      });
    const preview = publicAnswerPreview(data);
    if (preview)
      rows.at(-1)!.messages.push({ ...preview, review_cycle: cycle });
  }
  // A skipped stage is a recorded outcome, never an invented model response.
  for (const stage of data.stage_results || []) {
    if (
      stage.state !== "skipped" ||
      rows.some((r) => r.cycle === cycleOf(stage) && r.phase === stage.phase)
    )
      continue;
    const rank = phaseOrder.indexOf(stage.phase);
    if (rank < 0) continue;
    const at = rows.findIndex(
      (r) => r.cycle === cycleOf(stage) && phaseOrder.indexOf(r.phase) > rank,
    );
    const row = {
      id: `skipped-${cycleOf(stage)}-${stage.phase}`,
      phase: stage.phase,
      cycle: cycleOf(stage),
      messages: [],
      state: "skipped",
    };
    if (at >= 0) rows.splice(at, 0, row);
    else rows.push(row);
  }
  return rows;
}

function memberFor(message: Dict, members: Dict[]): string | undefined {
  return (
    members.find((p) => p.id === message.participant_id)?.id ||
    members.find((p) => p.model === (message.actual_model || message.model))?.id
  );
}

function useModal(
  open: boolean,
  dialog: React.RefObject<HTMLDialogElement | null>,
) {
  useEffect(() => {
    if (!open) return;
    const panel = dialog.current;
    const previous = document.activeElement as HTMLElement | null;
    panel?.showModal();
    return () => {
      panel?.close();
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [open, dialog]);
}

function Reader({
  cid,
  message,
  usage,
  onClose,
  onSource,
}: {
  cid: string;
  message: Dict | null;
  usage?: Dict;
  onClose: () => void;
  onSource: (version: string, start: number, end: number) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [zoom, setZoom] = useState(100);
  const [copyText, setCopyText] = useState<string | null>(null);
  useModal(!!message, dialog);
  useEffect(() => setZoom(100), [message?.call_id || message?.id]);
  useEffect(() => setCopyText(null), [message?.id]);
  if (!message) return null;
  const question = message.role === "user";
  return (
    <dialog
      ref={dialog}
      className="compare-reader"
      aria-labelledby="compare-reader-title"
      onCancel={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onClose();
      }}
    >
      <header>
        <div>
          <h2 id="compare-reader-title">
            {question ? "Your question" : message.name || "Council response"}
          </h2>
          <p>
            {question
              ? "Full question"
              : `${phaseLabels[message.phase] || "Response"} · ${message.actual_model || message.model || "Saved response"}`}
            {message.isLive ? " · Arriving" : ""}
          </p>
        </div>
        <div className="compare-reader-tools">
          <button
            type="button"
            className="council-icon"
            aria-label="Decrease text size"
            disabled={zoom <= 80}
            onClick={() => setZoom((value) => value - 10)}
          >
            <Minus size={16} />
          </button>
          <output aria-label="Text size">{zoom}%</output>
          <button
            type="button"
            className="council-icon"
            aria-label="Increase text size"
            disabled={zoom >= 160}
            onClick={() => setZoom((value) => value + 10)}
          >
            <Plus size={16} />
          </button>
          <CopyTextButton
            text={copyText ?? message.content}
            label={
              question
                ? "Copy question"
                : `Copy inspected response from ${message.name || "model"}`
            }
          />
          <button
            type="button"
            className="council-icon"
            aria-label="Close expanded reading"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>
      </header>
      <div
        className="compare-reader-content council-message-content"
        style={{ fontSize: `${zoom}%` }}
      >
        {message.explanation_only && (
          <p className="message-review-state">
            Explanation of the saved review. No new checks were performed.
          </p>
        )}
        {!question &&
        message.presentation_changed &&
        message.original_response_available ? (
          <SavedModelReply
            key={message.id}
            cid={cid}
            message={message}
            onSource={onSource}
            onText={setCopyText}
          />
        ) : (
          <CouncilBody
            text={message.content || "No public answer text was saved."}
            onSource={onSource}
          />
        )}
        {!question && !message.isLive && (
          <>
            <ReplySearch value={message.web_search} explain />
            <ReplyUsage value={usage} demo={message.source === "fixture"} />
          </>
        )}
      </div>
    </dialog>
  );
}

const ResponsePreview = memo(function ResponsePreview({
  message,
  onInspect,
  onSource,
}: {
  message: Dict;
  onInspect: (id: string) => void;
  onSource: (version: string, start: number, end: number) => void;
}) {
  return (
    <article
      className="compare-response"
      data-response-id={message.id}
      data-model={message.actual_model || message.model || "human"}
    >
      <header>
        <div>
          <strong>
            {message.role === "user" ? "You" : message.name || "Council"}
          </strong>
          {message.isLive && <span>Answer arriving</span>}
          {message.superseded && <span>Earlier version</span>}
          {message.edited_from_message_id && <span>Edited request</span>}
          {message.partial && message.generation_state !== "complete" && (
            <span>Partial answer</span>
          )}
        </div>
        <button
          type="button"
          className="compare-inspect"
          aria-label={`Inspect response from ${message.name || "council"}, ${message.sequence || "live"}`}
          onClick={() => onInspect(message.id)}
        >
          <Maximize2 size={13} />
          <span>Inspect</span>
        </button>
      </header>
      <div className="compare-response-body council-message-content">
        {message.explanation_only && (
          <p className="message-review-state">Explanation of saved checks.</p>
        )}
        <CouncilBody
          text={message.content || "No public answer text was saved."}
          onSource={onSource}
        />
        <ReplySearch value={message.web_search} explain={false} />
      </div>
    </article>
  );
});

export function CouncilCompareButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="council-compare-button"
      onClick={onClick}
      title="Read the saved council side by side"
    >
      <Columns3 size={15} />
      <span>Compare</span>
    </button>
  );
}

export function CouncilCompare({
  data,
  open,
  onClose,
  onSource,
}: {
  data: Dict;
  open: boolean;
  onClose: () => void;
  onSource: (version: string, start: number, end: number) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [inspecting, setInspecting] = useState<string | null>(null);
  useModal(open, dialog);
  const question =
    data.messages?.find(
      (m: Dict) => m.role === "user" && m.phase === "prompt" && !m.superseded,
    ) || data.messages?.find((m: Dict) => m.role === "user");
  const members = data.effective_members || data.chat.participants;
  const rows = useMemo(
    () => flowRows(data, question?.id),
    [data, question?.id],
  );
  const inspect = useCallback((id: string) => setInspecting(id), []);
  const source = useCallback(
    (version: string, start: number, end: number) => {
      setInspecting(null);
      onClose();
      // Sources is the existing inspector outside the modal reading surface.
      requestAnimationFrame(() => onSource(version, start, end));
    },
    [onClose, onSource],
  );
  const selected =
    inspecting === question?.id
      ? question
      : rows
          .flatMap((row) => row.messages)
          .find(
            (m) =>
              m.id === inspecting ||
              (inspecting?.startsWith("live-") &&
                m.call_id === inspecting.slice(5)),
          );
  const active = data.chat.active_turn;
  const activeId = active ? memberFor(active, members) : undefined;
  if (!open) return null;
  return (
    <dialog
      ref={dialog}
      className="council-compare"
      aria-labelledby="compare-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header className="compare-heading">
        <div>
          <h2 id="compare-title">
            <Columns3 size={18} />
            Compare
          </h2>
          <p>One conversation · {members.length} model perspectives</p>
        </div>
        <button type="button" className="compare-return" onClick={onClose}>
          <ArrowLeft size={15} />
          Conversation
        </button>
      </header>
      {question && (
        <section
          className="compare-question"
          aria-label={
            question.edited_from_message_id
              ? "Current question"
              : "Original question"
          }
        >
          <header>
            <strong>Your question</strong>
            <button
              type="button"
              className="compare-inspect"
              onClick={() => inspect(question.id)}
            >
              <Maximize2 size={13} />
              Expand question
            </button>
          </header>
          <div className="compare-question-body council-message-content">
            <CouncilBody text={question.content} onSource={source} />
          </div>
        </section>
      )}
      <p className="compare-swipe">
        Swipe sideways to compare models. Expand a reply to read it in full.
      </p>
      {data.collective_research && (
        <CollectiveResearch
          value={data.collective_research}
          explain={false}
          onSource={source}
        />
      )}
      <div
        className="compare-scroll"
        tabIndex={0}
        aria-label="Parallel council flow"
      >
        <div
          className="compare-matrix"
          style={{ "--compare-columns": members.length } as React.CSSProperties}
        >
          <div className="compare-models">
            {members.map((member: Dict, i: number) => (
              <div key={member.id}>
                <span className="compare-model-number">0{i + 1}</span>
                <div>
                  <strong>{member.name}</strong>
                  <span title={member.model}>{member.model}</span>
                </div>
                {data.lead?.id === member.id && <small>Lead</small>}
              </div>
            ))}
          </div>
          {rows.map((row) => {
            const shared =
              row.messages.some(
                (m) => m.role !== "assistant" || !memberFor(m, members),
              ) ||
              ["synthesis", "extraction", "scrutiny", "recheck"].includes(
                row.phase,
              );
            const current =
              active &&
              row === rows.at(-1) &&
              row.phase === active.phase &&
              row.cycle === (data.review?.cycle ?? 1);
            return (
              <section
                key={row.id}
                className="compare-stage"
                data-phase={row.phase}
                data-cycle={row.cycle}
              >
                <header>
                  <h3>
                    {row.messages[0]?.role === "user"
                      ? "Your follow-up"
                      : rowLabel(row)}
                  </h3>
                  <span>
                    Cycle {row.cycle}
                    {row.state === "skipped" ? " · Skipped" : ""}
                  </span>
                </header>
                {shared ? (
                  <div className="compare-shared compare-cell">
                    {row.state === "skipped" && !row.messages.length && (
                      <p className="compare-missing">
                        Stage skipped. No model response was requested.
                      </p>
                    )}
                    {row.messages.map((message) => (
                      <ResponsePreview
                        key={message.id}
                        message={message}
                        onInspect={inspect}
                        onSource={source}
                      />
                    ))}
                    {current &&
                      !row.messages.some(
                        (m) =>
                          m.call_id === data.active_request?.call_id &&
                          !m.isLive,
                      ) && (
                        <div className="compare-cell-status" role="status">
                          <strong>{active.name} is responding</strong>
                          <ActiveResponseTiming
                            request={data.active_request}
                            explain={false}
                          />
                        </div>
                      )}
                  </div>
                ) : (
                  <div className="compare-cells">
                    {members.map((member: Dict) => {
                      const replies = row.messages.filter(
                        (m) => memberFor(m, members) === member.id,
                      );
                      const generating =
                        current &&
                        activeId === member.id &&
                        !replies.some(
                          (m) =>
                            m.call_id === data.active_request?.call_id &&
                            !m.isLive,
                        );
                      return (
                        <div
                          className="compare-cell"
                          key={member.id}
                          data-member={member.id}
                          aria-label={`${member.name}: ${rowLabel(row)}`}
                        >
                          {replies.map((message) => (
                            <ResponsePreview
                              key={message.id}
                              message={message}
                              onInspect={inspect}
                              onSource={source}
                            />
                          ))}
                          {generating && (
                            <div className="compare-cell-status" role="status">
                              <strong>{active.name} is responding</strong>
                              <ActiveResponseTiming
                                request={data.active_request}
                                explain={false}
                              />
                            </div>
                          )}
                          {!replies.length && !generating && (
                            <p className="compare-missing">
                              {row.state === "skipped"
                                ? "Stage skipped. No model response."
                                : "No response was generated at this step."}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })}
          {!rows.length && (
            <p className="compare-missing">
              Model replies will appear here as they arrive.
            </p>
          )}
        </div>
      </div>
      <Reader
        cid={data.chat.id}
        message={selected || null}
        usage={selected && data.accounting?.replies?.[selected.id]}
        onClose={() => setInspecting(null)}
        onSource={source}
      />
    </dialog>
  );
}
