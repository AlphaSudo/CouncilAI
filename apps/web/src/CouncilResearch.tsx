import { useEffect, useRef, useState } from "react";
import { BookOpen, X, Upload } from "lucide-react";
import { api } from "./api";
import type { Dict } from "./types";
import "./council-research.css";
import {
  AttemptTiming,
  ReplyTimingSummary,
  secondsLabel,
} from "./ResponseTiming";

const count = (value: number | null | undefined) =>
  value == null ? "Unknown" : value.toLocaleString();
const money = (value: string | null | undefined) =>
  value == null
    ? "Unknown"
    : Number(value) > 0 && Number(value) < 0.000000001
      ? "<$0.000000001"
      : `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 9 })}`;
const labels: Dict = {
  input_total_reported: "Input total",
  input_uncached: "Ordinary input",
  cache_read_input: "Cache read",
  cache_write_input: "Cache write",
  cache_write_long_retention: "Long-retention write",
  output_total_reported: "Output total",
  output_visible: "Visible output",
  output_reasoning: "Reasoning",
  billable_output: "Billable output",
  provider_total_reported: "Provider total",
};

export async function uploadCouncilSource(chatId: string, file: File) {
  if (file.size > 2097152)
    throw new Error("Choose a file no larger than 2 MiB.");
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 8192)
    binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  const mime = file.name.endsWith(".md")
    ? "text/markdown"
    : file.name.endsWith(".docx")
      ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      : file.type || "text/plain";
  return api(`/chats/${chatId}/library/import`, {
    title: file.name,
    mime,
    base64_content: btoa(binary),
  });
}

export function ReplyUsage({
  value,
  demo = false,
  explain = false,
}: {
  value?: Dict;
  demo?: boolean;
  explain?: boolean;
}) {
  const total = value?.total;
  return (
    <details className="reply-usage">
      <summary>
        Usage{" "}
        <span>
          {demo
            ? "Synthetic · no API call"
            : !total
              ? "Unavailable"
              : `${total.tokens?.input_total_reported?.reported_attempts ? count(total.tokens.input_total_reported.known_subtotal) + " input · " : ""}${total.tokens?.billable_output?.reported_attempts ? count(total.tokens.billable_output.known_subtotal) + " output · " : ""}${total.attempts} ${total.attempts === 1 ? "attempt" : "attempts"} · ${total.usage_reported_attempts}/${total.attempts} reported${total.known_reference_subtotal_usd != null ? " · " + money(total.known_reference_subtotal_usd) + " known rate estimate" : ""}${total.cost_state && total.cost_state !== "complete_estimate" ? " · Partial" : ""}`}
        </span>
        {!demo && <ReplyTimingSummary attempts={value?.attempts} />}
      </summary>
      {value?.attempts.map((attempt: Dict) => (
        <section key={attempt.call_id} className="usage-attempt">
          <p>
            <strong>{attempt.provider}</strong> · {attempt.model} ·{" "}
            {attempt.state}
          </p>
          <AttemptTiming attempt={attempt} />
          {attempt.generation && (
            <p className="research-muted">
              {attempt.generation.profile === "raw_opening"
                ? "Independent opening · open answer length"
                : attempt.generation.profile === "answer_now"
                  ? "Answer-now recovery"
                  : "Controlled review"}
              {" · "}Reasoning requested:{" "}
              {attempt.generation.reasoning.replaceAll("_", " ")}
              {attempt.generation.reasoning_budget_tokens != null && (
                <>
                  {" · "}Reasoning budget requested:{" "}
                  {count(attempt.generation.reasoning_budget_tokens)} tokens{" "}
                  (system instruction; not a hard provider limit)
                </>
              )}
              {" · "}Completion allowance:{" "}
              {count(attempt.generation.effective_output_tokens)} tokens
              (reasoning + answer).
              {attempt.generation.native_reasoning_budget_tokens != null && (
                <>
                  {" "}
                  Native thinking budget requested:{" "}
                  {count(
                    attempt.generation.native_reasoning_budget_tokens,
                  )}{" "}
                  tokens; enforcement unverified. Reasoning overruns do not
                  trigger a client-side cutoff.
                </>
              )}
              {attempt.generation.limiting_factors?.length > 0 && (
                <>
                  {" "}
                  Limited by{" "}
                  {attempt.generation.limiting_factors
                    .map((x: string) => x.replaceAll("_", " "))
                    .join(" and ")}
                  .
                </>
              )}
              {attempt.generation.control_status ===
                "requested_not_live_verified" &&
                " Hosted control effectiveness is unverified; token usage is the measured observation."}
            </p>
          )}
          {attempt.generation?.thinking_level && (
            <p className="research-muted">
              Thinking preset: {attempt.generation.thinking_level}.{" "}
              {attempt.generation.model_reasoning_override
                ? "The model-specific reasoning override was used."
                : attempt.generation.thinking_level_applied === false
                  ? "The saved Answer now recovery controls were used."
                  : "Settings recorded for this request."}
            </p>
          )}
          {attempt.reasoning_budget_observation && (
            <p className="research-muted">
              Reported reasoning:{" "}
              {count(attempt.reasoning_budget_observation.reported_tokens)}{" "}
              tokens.
              {attempt.reasoning_budget_observation.status ===
              "above_requested_budget"
                ? ` Exceeded the requested budget by ${count(attempt.reasoning_budget_observation.over_requested_tokens)} tokens.`
                : attempt.reasoning_budget_observation.status ===
                    "within_requested_budget"
                  ? " Within the requested budget."
                  : " Budget compliance is unknown until reasoning usage is reported."}
            </p>
          )}
          {explain && attempt.generation?.reasoning_budget_instruction && (
            <details>
              <summary>Reasoning instruction sent</summary>
              <p>{attempt.generation.reasoning_budget_instruction}</p>
            </details>
          )}
          {explain && attempt.generation?.stage_token_instruction && (
            <details>
              <summary>Stage input/output token guidance</summary>
              <p>
                Public-output target:{" "}
                {count(attempt.generation.stage_output_target_tokens)} tokens.
                Required coverage takes priority.
              </p>
              <p>{attempt.generation.stage_token_instruction}</p>
            </details>
          )}
          <div
            className="research-table-scroll"
            tabIndex={0}
            aria-label="Token and price breakdown"
          >
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Tokens</th>
                  <th>USD / 1M tokens</th>
                  <th>Estimate (USD)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(attempt.usage.categories).map(
                  ([key, number]) => {
                    const line = attempt.cost.lines.find(
                      (item: Dict) => item.category === key,
                    );
                    const state = attempt.usage.states[key];
                    return (
                      <tr key={key}>
                        <th>{labels[key] || key}</th>
                        <td>
                          {state === "not_applicable"
                            ? "N/A"
                            : count(number as number | null)}
                        </td>
                        <td>
                          {line
                            ? (line.rate ?? "Unknown")
                            : "Included / no separate rate"}
                        </td>
                        <td>{line ? money(line.amount_usd) : "—"}</td>
                      </tr>
                    );
                  },
                )}
              </tbody>
            </table>
          </div>
          <p className="research-muted">
            {attempt.usage.inclusion_rules} These rows overlap as described;
            they are not summed together.
          </p>
          <dl className="usage-money">
            <div>
              <dt>Provider-reported amount</dt>
              <dd>{money(attempt.cost.provider_reported_amount_usd)}</dd>
            </div>
            <div>
              <dt>
                {attempt.cost.view === "published_price_equivalent"
                  ? "Published-price equivalent"
                  : "Applicable tariff estimate"}
              </dt>
              <dd>
                {money(attempt.cost.known_subtotal_usd)} ·{" "}
                {attempt.cost.status.replaceAll("_", " ")}
              </dd>
            </div>
          </dl>
          <p className="research-muted">
            Invoice not verified.{" "}
            {attempt.historical_enrichment
              ? "Historical enrichment from saved usage; dispatch-time rate was not saved. "
              : ""}
            Rate checked {attempt.price_card.checked_at}.{" "}
            <a
              href={attempt.price_card.source_url}
              target="_blank"
              rel="noreferrer"
            >
              Price source
            </a>
          </p>
          {explain && (
            <details>
              <summary>Accounting record</summary>
              <pre>
                {JSON.stringify(
                  {
                    call_id: attempt.call_id,
                    logical_turn_id: attempt.logical_turn_id,
                    card_id: attempt.price_card.id,
                    context_pack_id: attempt.context_pack_id,
                    raw_fields: attempt.usage.raw_field_map,
                    missing: attempt.cost.missing,
                    errors: attempt.cost.errors,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          )}
        </section>
      ))}
      {!value && (
        <p className="research-muted">
          {demo
            ? "This reply uses scripted data. No measured model tokens or charge."
            : "This reply has no attributable provider usage. Missing counts are not zero."}
        </p>
      )}
      {value?.cumulative_through_reply && (
        <p className="research-muted">
          Cumulative through this reply:{" "}
          {value.cumulative_through_reply.attempts} attempts · known
          price-equivalent subtotal{" "}
          {money(value.cumulative_through_reply.known_reference_subtotal_usd)} ·{" "}
          {value.cumulative_through_reply.cost_state.replaceAll("_", " ")}.
          Current ledger projection.
        </p>
      )}
    </details>
  );
}

export function ConversationUsage({
  data,
  explain,
}: {
  data: Dict;
  explain: boolean;
}) {
  const accounting = data.accounting;
  if (!accounting) return null;
  const total = accounting.total;
  const unfinished = accounting.attempts.filter((a: Dict) =>
    ["unknown", "failed", "http_error"].includes(a.state),
  );
  return (
    <details className="conversation-usage">
      <summary>
        Conversation usage{" "}
        {explain && (
          <span>
            {total.attempts} attempts · {total.usage_reported_attempts}/
            {total.attempts} with token data
            {total.cost_state !== "complete_estimate" ? " · Partial" : ""}
          </span>
        )}
      </summary>
      <p>
        All attempts are included, including retries, rejected responses and
        research continuations.
      </p>
      <dl className="usage-money">
        <div>
          <dt>Provider-reported subtotal</dt>
          <dd>
            {money(total.provider_reported_subtotal_usd)} ·{" "}
            {total.provider_reported_attempts}/{total.attempts} reported
          </dd>
        </div>
        <div>
          <dt>Known published-price subtotal</dt>
          <dd>
            {money(total.known_reference_subtotal_usd)} ·{" "}
            {total.complete_estimates}/{total.attempts} complete estimates
          </dd>
        </div>
        <div>
          <dt>Shared search credits reserved</dt>
          <dd>{accounting.shared_research.external_credit_reservations}</dd>
        </div>
        <div>
          <dt>Unknown model outcomes</dt>
          <dd>{total.unknown_outcomes}</dd>
        </div>
        {total.timed_attempts > 0 && (
          <div>
            <dt>Request time across attempts</dt>
            <dd>
              {secondsLabel(total.known_request_seconds)} ·{" "}
              {total.timed_attempts}/{total.attempts} timed
            </dd>
          </div>
        )}
      </dl>
      {unfinished.length > 0 && (
        <details className="unfinished-requests">
          <summary>Unfinished requests ({unfinished.length})</summary>
          {unfinished.map((attempt: Dict) => (
            <section key={attempt.call_id} className="usage-attempt">
              <p>
                <strong>{attempt.model}</strong> ·{" "}
                {attempt.state === "unknown"
                  ? "Outcome unknown"
                  : attempt.state}
              </p>
              <AttemptTiming attempt={attempt} />
            </section>
          ))}
        </details>
      )}
      <p className="research-muted">
        Published rates are a comparison, not your account invoice. Unknown
        charges and missing token categories remain unknown. Shared research is
        counted once.
      </p>
      {explain && (
        <>
          <div className="research-table-scroll" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Known tokens</th>
                  <th>Coverage</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(total.tokens).map(([key, raw]) => {
                  const item = raw as Dict;
                  return (
                    <tr key={key}>
                      <th>{labels[key] || key}</th>
                      <td>{count(item.known_subtotal)}</td>
                      <td>
                        {item.reported_attempts}/{item.total_attempts}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <details>
            <summary>All physical attempts</summary>
            {accounting.attempts.map((attempt: Dict) => (
              <ReplyUsage
                key={attempt.call_id}
                explain
                value={{
                  attempts: [attempt],
                  total: {
                    attempts: 1,
                    usage_reported_attempts:
                      attempt.usage.status === "reported" ? 1 : 0,
                  },
                }}
              />
            ))}
          </details>
          <details>
            <summary>Tools and context</summary>
            <pre>
              {JSON.stringify(
                {
                  as_of_sequence: accounting.as_of_sequence,
                  tools: data.research_tools,
                  resource_policy: data.resource_policy,
                  context_packs: data.context_packs?.map((p: Dict) => ({
                    ...p,
                    passages: p.passages.map((r: Dict) => ({
                      ...r,
                      text: undefined,
                    })),
                  })),
                },
                null,
                2,
              )}
            </pre>
          </details>
        </>
      )}
    </details>
  );
}

export function SourceLibrary({
  data,
  explain,
  onRefresh,
}: {
  data: Dict;
  explain: boolean;
  onRefresh: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [url, setUrl] = useState(""),
    [query, setQuery] = useState(""),
    [results, setResults] = useState<Dict[]>([]);
  const [passage, setPassage] = useState<Dict | null>(null),
    [versionId, setVersionId] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const chat = data.chat,
    library = data.library;
  useEffect(() => {
    const listener = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (detail.chat_id !== chat.id) return;
      setOpen(true);
      void read(detail.version_id, 0, detail.start, detail.end);
    };
    window.addEventListener("council:open-source", listener);
    return () => window.removeEventListener("council:open-source", listener);
  }, [chat.id]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
    return () => {
      if (open) {
        dialog.current?.close();
        previous?.focus();
      }
    };
  }, [open]);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function tool(name: string, arguments_: Dict) {
    return api(`/chats/${chat.id}/research/tools`, {
      name,
      arguments: arguments_,
    });
  }
  async function read(id: string, offset = 0, start?: number, end?: number) {
    await run(async () => {
      setPassage(
        await tool("library_read", {
          version_id: id,
          char_start: offset,
          ...(start ? { line_start: start, line_end: end } : {}),
        }),
      );
      setVersionId(id);
      await onRefresh();
    });
  }
  async function upload(file: File) {
    if (file.size > 2097152) {
      setError("Choose a file no larger than 2 MiB.");
      return;
    }
    await run(async () => {
      await uploadCouncilSource(chat.id, file);
      await onRefresh();
    });
  }
  const versions = library?.versions || [];
  return (
    <>
      <button
        type="button"
        className="council-sources-trigger"
        onClick={() => setOpen(true)}
      >
        <BookOpen size={15} /> Sources <span>{versions.length}</span>
      </button>
      <dialog
        ref={dialog}
        className="research-panel"
        onCancel={() => setOpen(false)}
        onClose={() => setOpen(false)}
        aria-labelledby="source-library-title"
      >
        <header>
          <div>
            <small>Conversation library</small>
            <h2 id="source-library-title">Sources</h2>
          </div>
          <button
            type="button"
            aria-label="Close sources"
            onClick={() => setOpen(false)}
          >
            <X size={20} />
          </button>
        </header>
        <p className="research-muted">
          Saved for this conversation. Models can reuse passages; a retrieved
          source is not automatically verified.
        </p>
        {["direct_council", "nebius_token_factory"].includes(chat.provider) && (
          <label className="research-setting">
            <input
              type="checkbox"
              checked={
                chat.next_turn_research_enabled ??
                chat.next_research_enabled ??
                chat.research_enabled ??
                false
              }
              disabled={busy}
              onChange={(e) => {
                const enabled = e.target.checked;
                void run(async () => {
                  await api(`/chats/${chat.id}/research/settings`, { enabled });
                  await onRefresh();
                });
              }}
            />
            Search the web before upcoming model replies
          </label>
        )}
        {error && (
          <p role="alert" className="research-error">
            {error}
          </p>
        )}
        {(data.research_tools || [])
          .filter((item: Dict) => item.state === "unknown")
          .map((item: Dict) => (
            <section key={item.id} className="research-error">
              <p>
                An earlier{" "}
                {item.name === "web_search" ? "search" : "source operation"} has
                an unconfirmed outcome and remains counted.
              </p>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await api(
                      `/chats/${chat.id}/research/tools?authorize_unknown_retry=true`,
                      { name: item.name, arguments: item.arguments },
                    );
                    await onRefresh();
                  })
                }
              >
                Retry this operation once
              </button>
            </section>
          ))}
        <section className="source-import">
          <label className="source-upload">
            <Upload size={15} /> Add a document
            <input
              type="file"
              accept=".txt,.md,.html,.pdf,.docx"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void upload(file);
                e.target.value = "";
              }}
            />
          </label>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                await tool("web_fetch", { url });
                setUrl("");
                await onRefresh();
              });
            }}
          >
            <label htmlFor="source-url">Save a public link</label>
            <div>
              <input
                id="source-url"
                type="url"
                value={url}
                placeholder="https://…"
                onChange={(e) => setUrl(e.target.value)}
                required
              />
              <button disabled={busy || !url}>Save</button>
            </div>
          </form>
        </section>
        <form
          className="source-search"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              setResults((await tool("library_search", { query })).results);
              await onRefresh();
            });
          }}
        >
          <label htmlFor="source-query">Find saved passages</label>
          <div>
            <input
              id="source-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
            <button disabled={busy || !query.trim()}>Find</button>
          </div>
        </form>
        {busy && <p role="status">Working with sources…</p>}
        {results.map((result) => (
          <button
            type="button"
            className="source-result"
            key={result.id}
            onClick={() => void read(result.version_id)}
          >
            <strong>{result.title}</strong>
            <span>{result.snippet}</span>
          </button>
        ))}
        <ul className="source-list">
          {versions.map((version: Dict) => (
            <li key={version.id}>
              <button type="button" onClick={() => void read(version.id)}>
                <strong>{version.title}</strong>
                <span>
                  {version.mime} · {version.coverage.replaceAll("_", " ")}
                  {library?.sources?.some(
                    (source: Dict) =>
                      source.current_version_id === version.id &&
                      !source.removed,
                  )
                    ? " · Current"
                    : " · Earlier version"}
                </span>
              </button>
              {version.url && (
                <a href={version.url} target="_blank" rel="noreferrer">
                  Open original
                </a>
              )}
              {explain && (
                <details>
                  <summary>Version details</summary>
                  <pre>{JSON.stringify(version, null, 2)}</pre>
                </details>
              )}
            </li>
          ))}
        </ul>
        {versions.length === 0 && (
          <p>No sources saved yet. Add a document or a public link.</p>
        )}
        {passage && (
          <section className="source-passage">
            <h3>{passage.title}</h3>
            <p className="research-muted">
              Saved passage · {passage.receipt.bytes} bytes
              {passage.receipt.truncated ? " · More text available" : ""}.{" "}
              {passage.limitations.join(". ")}
            </p>
            <pre>{passage.text}</pre>
            {passage.receipt.next_char_start != null && (
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  void read(versionId, passage.receipt.next_char_start)
                }
              >
                Read next passage
              </button>
            )}
            {explain && <pre>{JSON.stringify(passage.receipt, null, 2)}</pre>}
          </section>
        )}
        {explain && (
          <details>
            <summary>Research activity and exposure</summary>
            <pre>
              {JSON.stringify(
                {
                  snapshots: library?.snapshots,
                  citations: library?.citations,
                  receipts: library?.receipts,
                  tools: data.research_tools,
                },
                null,
                2,
              )}
            </pre>
          </details>
        )}
      </dialog>
    </>
  );
}
