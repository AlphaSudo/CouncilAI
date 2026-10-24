import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { CouncilBody as Body } from "./CouncilBody";
import { OutputRecoveryNotice } from "./OutputRecoveryNotice";
import { ActiveResponseTiming, RetryCountdown } from "./ResponseTiming";
import { CopyTextButton } from "./CouncilCopy";
import { OriginalReplyDetails } from "./OriginalModelReply";
import { CouncilContext } from "./CouncilContext";
import {
  CouncilThinking,
  CouncilThinkingDetails,
  ConversationAllowance,
  type ThinkingLevel,
} from "./CouncilThinking";
import { ModelRecoveryNotice } from "./ModelRecoveryNotice";
import {
  defaultCouncilModels,
  preferredCouncilProvider,
} from "./CouncilModelSelection";
import {
  ReplyUsage,
  ConversationUsage,
  SourceLibrary,
  uploadCouncilSource,
} from "./CouncilResearch";
import {
  ArrowUp,
  ArrowUpRight,
  Check,
  ChevronDown,
  Download,
  FlaskConical,
  Layers3,
  LoaderCircle,
  Menu,
  MessageSquare,
  Pause,
  Pencil,
  Play,
  Plus,
  ShieldCheck,
  Square,
  X,
} from "lucide-react";
import { api, openLocalSession, HostedAccessRequired } from "./api";
import type { Dict } from "./types";
import { CouncilSetupSurface } from "./CouncilSetupSurface";
import { CouncilMessageEditor } from "./CouncilMessageEditor";
import { CouncilSearch, ReplySearch } from "./CouncilSearch";
import { CollectiveResearch } from "./CollectiveResearch";
import { ConversationTotals } from "./ConversationTotals";
import { LivePublicAnswer, ReviewDeliveryNote } from "./AnswerDelivery";
import { CouncilCompare, CouncilCompareButton } from "./CouncilCompare";
import "./council-chat.css";
import "./council-message-edit.css";
import "./council-review.css";
import "./council-design.css";
import {
  CouncilViewSwitch,
  CouncilProcessIntro,
  CouncilDiagnostics,
  CouncilAnswerJump,
  groupCouncilMessages,
  useCouncilView,
} from "./CouncilExperience";
import type { CouncilView } from "./CouncilExperience";
import { ObservationWarnings } from "./ScopedReviewDetails";
import { ReviewPanel, ReviewSetup, defaultReviewOptions } from "./ReviewPanel";
import type { ReviewOptions } from "./contracts.generated";

const providerName: Dict = {
  direct_council: "Direct models · 4 providers",
  openrouter_free: "OpenRouter · free only",
  nebius_token_factory: "Token Factory",
  fixture: "Synthetic demo",
};
const phaseName = (message: Dict) =>
  message.phase === "opening"
    ? "Independent answer"
    : message.phase === "debate"
      ? `Discussion · round ${message.round}`
      : message.phase === "synthesis"
        ? "Final synthesis"
        : (
            {
              extraction: "Key claims",
              scrutiny: "Challenges",
              repair: "Response and revision",
              recheck: "Checks",
              protocol_transition: "Review transition",
              participation_change: "Council participation",
            } as Dict
          )[message.phase] || "You";
const initials = (name: string) =>
  name
    .split(" ")
    .map((word) => word[0])
    .slice(0, 2)
    .join("");

export default function CouncilChat() {
  const [view, setView] = useCouncilView();
  const explain = view === "explain";
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [searchWeb, setSearchWeb] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [pendingSources, setPendingSources] = useState<File[]>([]);
  const [reviewOptions, setReviewOptions] =
    useState<ReviewOptions>(defaultReviewOptions);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [editing, setEditing] = useState<Dict | null>(null);
  const [editError, setEditError] = useState("");
  const closeCompare = useCallback(() => setCompareOpen(false), []);
  const [setupPreview, setSetupPreview] = useState<Dict | null>(null);
  const [boot, setBoot] = useState<Dict | null>(null);
  const [data, setData] = useState<Dict | null>(null);
  const [cid, setCid] = useState(
    new URLSearchParams(location.search).get("chat") || "",
  );
  const [loading, setLoading] = useState(true),
    [authenticated, setAuthenticated] = useState(false);
  const [hostedLogin, setHostedLogin] = useState(false);
  const [accessCode, setAccessCode] = useState("");
  const [text, setText] = useState("");
  const [provider, setProvider] = useState("fixture"),
    [models, setModels] = useState<string[]>([]);
  const [thinkingLevel, setThinkingLevel] = useState<ThinkingLevel>("balanced");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [membersOpen, setMembersOpen] = useState(false),
    [mobileOpen, setMobileOpen] = useState(false);
  const [retryUnknown, setRetryUnknown] = useState(false);
  const [availability, setAvailability] = useState<Dict | null>(null);
  const feed = useRef<HTMLDivElement>(null),
    input = useRef<HTMLTextAreaElement>(null);
  const stayAtBottom = useRef(true);
  const chat = data?.chat.id === cid ? data.chat : null;
  const liveChat = useRef(chat);
  liveChat.current = chat;
  const tokenFactory = (chat?.provider || provider) === "nebius_token_factory";
  const researchingTogether =
    !!data?.collective_research &&
    !["ready", "limited"].includes(data.collective_research.state);
  const researchAnchorId = data?.collective_research
    ? data?.messages.find(
        (message: Dict) =>
          message.role === "user" &&
          !message.superseded &&
          (message.review_cycle ?? 1) === (data.collective_research.cycle ?? 1),
      )?.id
    : null;
  const searchEnabled =
    searchWeb &&
    !!boot?.research?.configured &&
    ["direct_council", "nebius_token_factory"].includes(provider);
  const thinkingSettings = chat
    ? data?.thinking
    : boot?.providers?.nebius_token_factory?.thinking_profiles?.[thinkingLevel];
  const displayTitle = chat
    ? chat.title
        .replace(/^\s*#{1,6}\s+/, "")
        .replace(/\s+/g, " ")
        .trim()
    : "New council";
  const previewSignature = [
    provider,
    models.join(","),
    String(searchEnabled),
    String(pendingSources.length),
  ].join("|");
  useEffect(() => {
    if (!authenticated || cid || models.length < 2) return;
    let cancelled = false;
    const query = new URLSearchParams({
      provider,
      models: models.join(","),
      max_rounds: "1",
      search_web: String(searchEnabled),
      research_tools: String(pendingSources.length > 0),
    });
    api(`/chats/preview?${query}`)
      .then((result) => {
        if (!cancelled)
          setSetupPreview({ ...result, signature: previewSignature });
      })
      .catch(() => {
        if (!cancelled) setSetupPreview(null);
      });
    return () => {
      cancelled = true;
    };
  }, [
    authenticated,
    cid,
    provider,
    models.join(","),
    searchEnabled,
    pendingSources.length,
    boot?.providers.nebius_token_factory.ready,
  ]);

  const loadBoot = useCallback(async () => {
    const result = await api("/chats/bootstrap");
    setBoot(result);
    setAuthenticated(true);
    return result;
  }, []);
  useEffect(() => {
    (async () => {
      try {
        await openLocalSession();
        const result = await loadBoot();
        api("/chats/availability")
          .then(setAvailability)
          .catch(() => setAvailability({ known: false }));
        const choice = preferredCouncilProvider(result);
        setProvider(choice);
        setModels(defaultCouncilModels(result, choice));
      } catch (e) {
        setAuthenticated(false);
        setHostedLogin(e instanceof HostedAccessRequired);
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    })();
  }, [loadBoot]);
  useEffect(() => {
    if (!loading && authenticated && !cid) input.current?.focus();
  }, [authenticated, cid, loading]);
  useLayoutEffect(() => {
    const resize = () => {
      const field = input.current;
      if (!field) return;
      field.style.height = "auto";
      field.style.height = `${Math.min(field.scrollHeight, 180)}px`;
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [text, cid, authenticated, loading]);
  const refresh = useCallback(async () => {
    if (!cid) return;
    const result = await api(`/chats/${cid}`);
    setData(result);
    setBoot((old) =>
      old
        ? {
            ...old,
            chats: [
              result.chat,
              ...old.chats.filter((c: Dict) => c.id !== cid),
            ],
          }
        : old,
    );
  }, [cid]);
  useEffect(() => {
    if (authenticated && cid) refresh().catch((e) => setError(e.message));
  }, [authenticated, cid, refresh]);
  useEffect(() => {
    if (!chat?.mission_id || !authenticated) return;
    const stream = new EventSource(`/api/missions/${chat.mission_id}/events`);
    let timer: number | undefined;
    let disposed = false;
    let refreshing = false;
    let refreshAgain = false;
    const synchronize = async () => {
      if (disposed) return;
      if (refreshing) {
        refreshAgain = true;
        return;
      }
      refreshing = true;
      try {
        await refresh();
      } catch (error) {
        if (!disposed) setError((error as Error).message);
      } finally {
        refreshing = false;
        if (refreshAgain && !disposed) {
          refreshAgain = false;
          scheduleRefresh();
        }
      }
    };
    const scheduleRefresh = () => {
      // Coalesce bursts without postponing indefinitely on a busy event stream.
      if (timer === undefined)
        timer = window.setTimeout(() => {
          timer = undefined;
          void synchronize();
        }, 250);
    };
    stream.addEventListener("research", scheduleRefresh);
    // Events are the fast path. Read-only polling keeps a missed/disconnected
    // event stream from leaving an active or completed model status stale.
    const fallback = window.setInterval(() => {
      const current = liveChat.current;
      if (
        document.visibilityState === "visible" &&
        (current?.status === "running" ||
          current?.status === "waiting" ||
          (current?.status === "paused" && current.active_turn))
      )
        synchronize();
    }, 2000);
    return () => {
      disposed = true;
      stream.close();
      window.clearTimeout(timer);
      window.clearInterval(fallback);
    };
  }, [chat?.mission_id, authenticated, refresh]);
  useEffect(() => {
    if (stayAtBottom.current && feed.current)
      feed.current.scrollTop = feed.current.scrollHeight;
  }, [data?.messages.length, chat?.active_turn?.name, chat?.status]);

  function changeView(next: CouncilView) {
    if (next === view) return;
    const container = feed.current;
    const edge = container?.getBoundingClientRect().top ?? 0;
    const visible = container
      ? Array.from(
          container.querySelectorAll<HTMLElement>(".council-message"),
        ).find(
          (element) =>
            element.getBoundingClientRect().bottom > edge + 20 &&
            element.getClientRects().length > 0,
        )?.id
      : undefined;
    const followLatest = stayAtBottom.current;
    setView(next);
    requestAnimationFrame(() => {
      if (!feed.current || !cid) return;
      if (followLatest) feed.current.scrollTop = feed.current.scrollHeight;
      else if (visible) {
        const target = document.getElementById(visible);
        const disclosure = target?.closest<HTMLDetailsElement>(
          "details.council-process-group",
        );
        (disclosure && !disclosure.open ? disclosure : target)?.scrollIntoView({
          block: "start",
          behavior: "auto",
        });
      }
    });
  }

  function select(id: string) {
    setEditing(null);
    setCustomizeOpen(false);
    setPendingSources([]);
    setSearchQuery("");
    setSearchWeb(true);
    setCid(id);
    setData(null);
    setError("");
    setText("");
    setMobileOpen(false);
    stayAtBottom.current = true;
    history.replaceState(
      null,
      "",
      id ? `/?chat=${encodeURIComponent(id)}` : "/",
    );
    input.current?.focus();
  }
  async function act(action: () => Promise<any>) {
    setBusy(true);
    setError("");
    try {
      return await action();
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setBusy(false);
    }
  }
  async function send() {
    if (!text.trim()) return;
    stayAtBottom.current = true;
    const result = await act(async () =>
      cid
        ? api(`/chats/${cid}/messages`, {
            text,
            ...(data?.review_adoption?.available
              ? { review_protocol: "reviewed_v4" }
              : {}),
          })
        : (async () => {
            let created = await api("/chats", {
              prompt: text,
              defer_start: pendingSources.length > 0,
              research_tools: pendingSources.length > 0,
              search_web: searchEnabled,
              search_query: searchEnabled ? searchQuery : "",
              provider,
              models,
              review_options: reviewOptions,
              max_rounds: 1,
              budget_usd: provider === "nebius_token_factory" ? 24 : 0,
              spending_scope:
                provider === "nebius_token_factory"
                  ? "shared_existing_credit"
                  : "conversation",
              thinking_level: thinkingLevel,
            });
            if (pendingSources.length) {
              setData(created);
              setCid(created.chat.id);
              history.replaceState(null, "", `/?chat=${created.chat.id}`);
              for (const file of pendingSources)
                await uploadCouncilSource(created.chat.id, file);
              setPendingSources([]);
              created = await api(`/chats/${created.chat.id}/control`, {
                action: "resume",
              });
            }
            return created;
          })(),
    );
    if (result) {
      setText("");
      setData(result);
      setCid(result.chat.id);
      setMembersOpen(false);
      setBoot((old) =>
        old
          ? {
              ...old,
              chats: [
                result.chat,
                ...old.chats.filter((c: Dict) => c.id !== result.chat.id),
              ],
            }
          : old,
      );
      history.replaceState(null, "", `/?chat=${result.chat.id}`);
      if (input.current) input.current.style.height = "auto";
    }
  }
  async function control(
    action: string,
    recoveryCallId?: string,
    additionalAllowance = 0,
  ) {
    const result = await act(() =>
      api(`/chats/${cid}/control`, {
        action,
        authorize_retry_with_unknown_charge: retryUnknown,
        recovery_call_id: recoveryCallId,
        ...(action === "continue_without_model"
          ? { additional_allowance_usd: additionalAllowance }
          : {}),
      }),
    );
    if (result) setData(result);
  }
  async function regenerateMessage(nextText: string) {
    if (!editing || busy) return;
    setBusy(true);
    setEditError("");
    try {
      const result = await api(
        `/chats/${cid}/messages/${editing.id}/regenerate`,
        {
          text: nextText,
          expected_revision: chat.revision,
          // Submitting explicitly retains the earlier unknown charge reservation.
          authorize_retry_with_unknown_charge: true,
        },
      );
      setData(result);
      setEditing(null);
      setError("");
      setBoot((old) =>
        old
          ? {
              ...old,
              chats: old.chats.map((saved: Dict) =>
                saved.id === result.chat.id ? result.chat : saved,
              ),
            }
          : old,
      );
      stayAtBottom.current = true;
      requestAnimationFrame(() => {
        if (feed.current) feed.current.scrollTop = feed.current.scrollHeight;
      });
    } catch (e) {
      setEditError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function download() {
    if (!data || !chat) return;
    const transcript =
      `# ${chat.title}\n\nProvider: ${chat.provider}\nProtocol: ${chat.protocol_hash}\n\n` +
      data.messages
        .map(
          (m: Dict) =>
            `## ${m.name || "You"} · ${phaseName(m)}\n${m.model ? `Model: ${m.model}\nSource: ${m.source}\n\n` : ""}${m.content}`,
        )
        .join("\n\n---\n\n");
    const url = URL.createObjectURL(
      new Blob([transcript], { type: "text/markdown;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `zerowall-council-${cid}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }
  const copyAllText =
    chat && data
      ? `# ${chat.title}\n\n` +
        data.messages
          .map(
            (message: Dict) =>
              `## ${message.name || "You"} — ${message.role === "user" ? (message.phase === "prompt" ? "Opening question" : "Director note") : phaseName(message)}\n${message.model ? `Model: ${message.actual_model || message.model}\n\n` : "\n"}${message.content}`,
          )
          .join("\n\n---\n\n")
      : "";
  const options = boot?.providers[provider]?.models || [];
  const currentPreview =
    setupPreview?.signature === previewSignature ? setupPreview : null;
  const planned = currentPreview?.planned_calls ?? 2 * models.length + 4;
  const requiredStart =
    currentPreview?.required_start ??
    planned + 3 + (searchEnabled || pendingSources.length ? 5 : 0);
  const freeSettings = boot?.providers.openrouter_free;
  const freeCap = freeSettings?.attempt_cap || 20;
  const quota = data?.account || availability || freeSettings?.account;
  const localRemaining = freeSettings?.daily_remaining;
  const availableCalls = Math.min(
    quota?.known ? quota.remaining : Infinity,
    localRemaining ?? Infinity,
  );
  const directSettings = boot?.providers.direct_council;
  const setupBlocked =
    !!currentPreview?.blocked ||
    (provider === "nebius_token_factory" &&
      !boot?.providers.nebius_token_factory.ready) ||
    (provider === "direct_council" &&
      (!directSettings?.ready ||
        requiredStart > Math.min(directSettings.daily_remaining ?? 0, 20))) ||
    (provider === "openrouter_free" &&
      (requiredStart > availableCalls || !!quota?.error));
  const planInvalid =
    models.length < 2 ||
    (provider === "openrouter_free" && planned > freeCap) ||
    setupBlocked;
  const finalWriting =
    !!chat?.active_turn && chat.active_turn.phase === "synthesis";
  const needsCalls =
    (data?.active_members?.length ?? chat?.participants.length ?? 0) + 1;
  const followupBlocked = data?.review_adoption?.available
    ? data.review_adoption.allowed === false
    : chat?.status === "completed" &&
      (["direct_council", "nebius_token_factory"].includes(chat.provider)
        ? data?.continuation?.allowed === false
        : chat.provider === "openrouter_free" &&
          data?.budget.remaining_calls <
            (chat.mode === "reviewed"
              ? 2 * chat.participants.length + 7
              : needsCalls));
  const stopped =
    chat?.status === "cancelled" &&
    !["direct_council", "nebius_token_factory"].includes(chat.provider) &&
    !data?.review_adoption?.available;
  const sendDisabled =
    busy ||
    !text.trim() ||
    (!cid && planInvalid) ||
    !!finalWriting ||
    !!followupBlocked ||
    !!stopped;

  const openSource = useCallback(
    (versionId: string, start: number, end: number) => {
      window.dispatchEvent(
        new CustomEvent("council:open-source", {
          detail: { chat_id: cid, version_id: versionId, start, end },
        }),
      );
    },
    [cid],
  );

  function renderMessage(message: Dict, index: number): React.ReactNode {
    if (!data || !chat) return null;
    const previous = data?.messages[index - 1];
    const separator =
      message.role === "assistant" &&
      (previous?.phase !== message.phase || previous?.round !== message.round);
    const memberIndex = chat.participants.findIndex(
      (p: Dict) => p.id === message.participant_id,
    );
    return (
      <React.Fragment key={message.id}>
        {explain && separator && (
          <div className="council-phase">
            <span>
              {message.phase === "opening"
                ? "01 · Independent opening answers"
                : message.phase === "debate"
                  ? `Discussion round ${message.round}`
                  : phaseName(message)}
            </span>
            <i />
          </div>
        )}
        {explain &&
          [
            "extraction",
            "scrutiny",
            "repair",
            "recheck",
            "debate",
            "synthesis",
          ].includes(message.phase) &&
          !data.messages
            .slice(0, index)
            .some((m: Dict) =>
              [
                "extraction",
                "scrutiny",
                "repair",
                "recheck",
                "debate",
                "synthesis",
              ].includes(m.phase),
            ) &&
          data.baseline.length > 0 && (
            <details className="council-baseline">
              <summary>
                <Layers3 size={16} />
                <span>
                  Shared reference baseline{" "}
                  <small>
                    {data.baseline.length} independent answers · now shared with
                    the available participants
                  </small>
                </span>
                <ChevronDown size={16} />
              </summary>
              <div>
                {data.baseline.map((m: Dict) => (
                  <a
                    key={m.id}
                    href={`#${m.id}`}
                    onClick={(e) => {
                      e.preventDefault();
                      document.getElementById(m.id)?.scrollIntoView({
                        behavior: matchMedia("(prefers-reduced-motion: reduce)")
                          .matches
                          ? "auto"
                          : "smooth",
                        block: "start",
                      });
                    }}
                  >
                    {m.name}
                    <span>{m.content.slice(0, 170)}…</span>
                  </a>
                ))}
              </div>
            </details>
          )}
        <article
          id={message.id}
          className={`council-message ${message.role === "user" ? "is-user" : ""} ${message.phase === "synthesis" ? "is-final" : ""}`}
          data-phase={message.phase}
          data-model={message.model || "human"}
        >
          <div className={`council-avatar tone-${memberIndex}`}>
            {message.role === "user" ? "YOU" : initials(message.name)}
          </div>
          <div className="council-message-main">
            <div className="council-message-heading">
              <strong>{message.name || "You"}</strong>
              <span>
                {message.partial && message.generation_state !== "complete"
                  ? "Partial synthesis"
                  : message.role === "user"
                    ? message.phase === "prompt"
                      ? "Opening question"
                      : "Director note"
                    : phaseName(message)}
              </span>
              <span className="council-message-number" hidden={!explain}>
                #{message.sequence}
              </span>
              {message.source === "fixture" && <small>DEMO</small>}
              {message.role === "user" && (
                <button
                  type="button"
                  className="council-icon council-edit-message"
                  aria-label={`Edit message ${message.sequence}`}
                  title="Edit & regenerate"
                  disabled={busy}
                  onClick={() => {
                    setEditError("");
                    setEditing(message);
                  }}
                >
                  <Pencil size={15} />
                </button>
              )}
              {message.edited_from_message_id && (
                <span className="message-version">Edited request</span>
              )}
              {message.superseded && (
                <span className="message-version">Earlier version</span>
              )}
              {(message.role === "assistant" ||
                message.source === "local_partial") && (
                <CopyTextButton
                  text={message.content}
                  label={`Copy response from ${message.name || "model"}`}
                />
              )}
              {message.review_state === "pending" && (
                <span className="message-review-state">Review pending</span>
              )}
              {message.generation_state === "unavailable" && (
                <span>No public answer received</span>
              )}
            </div>
            {explain && message.model && (
              <p className="council-model-id">
                {message.actual_model || message.model}
                {message.outdated_context ? " · Earlier context snapshot" : ""}
              </p>
            )}
            {message.replacement_for && (
              <p className="council-replacement">
                Free model replacement for{" "}
                {message.replacement_name || message.replacement_for}. Earlier
                replies keep their original author.
              </p>
            )}
            <div className="council-message-content">
              {message.explanation_only && (
                <p className="message-review-state">
                  Explanation of the saved review. No new checks were performed.
                </p>
              )}
              <Body text={message.content} onSource={openSource} />
              {message.presentation_changed &&
                message.original_response_available && (
                  <OriginalReplyDetails
                    cid={chat.id}
                    message={message}
                    onSource={openSource}
                  />
                )}
              <ReplySearch value={message.web_search} explain={explain} />
              {message.research_citations?.some(
                (c: Dict) => !c.span_exists || !c.exposed_passage,
              ) && (
                <p className="research-error">
                  A source citation could not be traced to a passage shown in
                  this turn. Inspect Sources before relying on it.
                </p>
              )}
              <ObservationWarnings
                observations={data?.review?.observations || []}
                messageId={message.id}
                onInspect={() => setReviewOpen(true)}
              />
            </div>
            {message.role === "assistant" && (
              <ReplyUsage
                value={data?.accounting?.replies?.[message.id]}
                demo={message.source === "fixture"}
                explain={explain}
              />
            )}
            {message.phase === "synthesis" &&
              message.id === chat.final_message_id && (
                <div className="council-final-actions">
                  <span>
                    <ShieldCheck size={14} /> Generated synthesis · human
                    judgment remains yours
                  </span>
                  <button
                    disabled={busy || chat.accepted}
                    onClick={() => control("accept")}
                  >
                    <Check size={15} />
                    {chat.accepted ? "Accepted" : "Accept answer"}
                  </button>
                </div>
              )}
          </div>
        </article>
        {message.id === researchAnchorId && (
          <CollectiveResearch
            value={data?.collective_research}
            explain={explain}
            onSource={openSource}
          />
        )}
      </React.Fragment>
    );
  }

  if (loading)
    return (
      <div className="council-login">
        <LoaderCircle className="council-spin" /> Opening council…
      </div>
    );
  if (!authenticated)
    return (
      <main className="council-login">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const result = await act(async () => {
              if (hostedLogin) {
                await api("/session", { token: accessCode });
                setAccessCode("");
              } else {
                await openLocalSession();
              }
              return loadBoot();
            });
            if (result) {
              const p = preferredCouncilProvider(result);
              setProvider(p);
              setModels(defaultCouncilModels(result, p));
            }
          }}
        >
          <a className="council-brand" href="/">
            Ⱬ{" "}
            <strong>
              ZeroWall<span>.</span>
            </strong>
          </a>
          <h1>
            {hostedLogin
              ? "Open your council."
              : "Your council is one click away."}
          </h1>
          <p>
            {hostedLogin
              ? "Enter the access code shared with you."
              : "Ask a question and let the models work through it together."}
          </p>
          {hostedLogin && (
            <label>
              Access code
              <input
                type="password"
                autoComplete="current-password"
                required
                autoFocus
                value={accessCode}
                onChange={(e) => setAccessCode(e.target.value)}
              />
            </label>
          )}
          {error && <p role="alert">{error}</p>}
          <button disabled={busy} className="council-primary">
            {busy
              ? "Opening council…"
              : hostedLogin
                ? "Open council"
                : "Go to prompt"}{" "}
            <ArrowUpRight size={17} />
          </button>
        </form>
      </main>
    );

  return (
    <div
      className={`council-app council-view-${view} ${chat ? "has-conversation" : "is-home"}`}
      data-view={view}
    >
      <a className="council-skip" href="#council-question">
        Skip to question
      </a>
      {mobileOpen && (
        <button
          className="council-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside className={`council-sidebar ${mobileOpen ? "is-open" : ""}`}>
        <a
          className="council-brand"
          href="/"
          aria-label="ZeroWall Council home"
        >
          <span className="council-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <strong>
            ZeroWall<span>.</span>
          </strong>
        </a>
        <button className="council-new" onClick={() => select("")}>
          <Plus size={17} aria-hidden="true" /> New council
        </button>
        <p className="council-mini">Conversations</p>
        <nav aria-label="Council conversations">
          {boot?.chats.length ? (
            boot.chats.map((room: Dict) => (
              <button
                key={room.id}
                onClick={() => select(room.id)}
                className={cid === room.id ? "selected" : ""}
              >
                <MessageSquare size={14} />
                <span>{room.title}</span>
                <i className={room.status === "running" ? "running" : ""} />
              </button>
            ))
          ) : (
            <p className="council-sidebar-note">
              Your councils will appear here.
            </p>
          )}
        </nav>
        <div className="council-sidebar-bottom">
          <div className="council-director">
            <span>YOU</span>
            <div>
              Human director<small>Guide the discussion. Decide.</small>
            </div>
          </div>
        </div>
      </aside>
      <main className="council-main">
        <header className="council-header">
          <button
            className="council-mobile-nav council-icon"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
          >
            <Menu size={20} />
          </button>
          <div>
            <h1 title={displayTitle}>{displayTitle}</h1>
          </div>
          <div className="council-header-actions">
            <CouncilViewSwitch view={view} onChange={changeView} />
            {chat && (
              <CouncilCompareButton onClick={() => setCompareOpen(true)} />
            )}
            {chat && (
              <>
                <span
                  className={`council-status ${chat.status} ${chat.requested_finish || data?.review?.partial_reasons?.length || data?.degraded ? "is-partial" : ""}`}
                >
                  <i />
                  {chat.status === "completed" ? (
                    chat.accepted ? (
                      "Accepted by you"
                    ) : chat.generation_state === "unavailable" ? (
                      "No answer received"
                    ) : chat.review_state === "incomplete" &&
                      chat.generation_state === "complete" ? (
                      "Answer ready · review partial"
                    ) : chat.requested_finish ||
                      data?.review?.partial_reasons?.length ||
                      data?.degraded ? (
                      "Partial answer"
                    ) : (
                      "Answer ready"
                    )
                  ) : chat.status === "running" ? (
                    "Council working"
                  ) : chat.status === "waiting" ? (
                    <>
                      Retrying in{" "}
                      <RetryCountdown
                        notBefore={chat.retry_wait?.not_before || ""}
                      />
                      s
                    </>
                  ) : chat.status === "cancelled" ? (
                    "Stopped"
                  ) : (
                    chat.status
                  )}
                </span>
                <button
                  className="council-icon"
                  aria-label="Download transcript"
                  title="Download transcript"
                  onClick={download}
                >
                  <Download size={17} />
                </button>
                <CopyTextButton
                  text={copyAllText}
                  label="Copy all responses"
                  disabled={
                    !data?.messages.some(
                      (message: Dict) =>
                        message.role === "assistant" ||
                        message.source === "local_partial",
                    )
                  }
                />
              </>
            )}
            <span
              className="council-local"
              title="Saved in this local workspace"
            >
              <ShieldCheck size={14} /> Local workspace
            </span>
          </div>
        </header>
        {chat && (
          <div className="council-members-bar">
            <div>
              {(data?.effective_members || chat.participants).map(
                (p: Dict, index: number) => (
                  <span
                    key={p.id}
                    className={`council-member tone-${index}`}
                    title={p.model}
                  >
                    <i>{initials(p.name)}</i>
                    {p.name}
                    {data?.lead?.id === p.id && <small>Lead</small>}
                    {chat.model_overrides?.[p.id] && (
                      <small>
                        {p.replacement_for
                          ? `Replaces ${p.replacement_name}`
                          : chat.model_overrides[p.id].name ||
                            "Free replacement active"}
                      </small>
                    )}
                    {chat.unavailable_members?.[p.id] && (
                      <small>
                        {chat.unavailable_members[p.id].kind ===
                        "director_excluded"
                          ? "Excluded"
                          : "Unavailable"}
                      </small>
                    )}
                  </span>
                ),
              )}
            </div>
            <span aria-label="Active council method">
              {["reviewed_v3", "reviewed_v4"].includes(chat.protocol?.version)
                ? "Council"
                : chat.mode === "reviewed"
                  ? "Earlier review"
                  : "Earlier discussion"}
            </span>
            <span>{providerName[chat.provider]}</span>
          </div>
        )}
        {chat && data && (
          <div
            className={`council-research-strip ${!explain && data.review ? "has-review-action" : ""}`}
          >
            <SourceLibrary
              key={chat.id}
              data={data}
              explain={explain}
              onRefresh={async () => {
                setData(await api(`/chats/${cid}`));
              }}
            />
            <ConversationUsage data={data} explain={explain} />
            {!explain && data.review && (
              <button
                type="button"
                className="council-inline-review"
                data-review-trigger
                onClick={() => setReviewOpen(true)}
              >
                <Layers3 size={15} /> Why this answer?
              </button>
            )}
          </div>
        )}
        {explain && data?.review && (
          <ol className="council-phases" aria-label="Council progress">
            {[
              ["opening", "Independent answers"],
              ["extraction", "Key claims"],
              ["scrutiny", "Challenges"],
              ["repair", "Revisions"],
              ["recheck", "Checks"],
              ["synthesis", "Final answer"],
            ].map(([phase, label]) => (
              <li
                key={phase}
                aria-current={
                  data.next_turn?.phase === phase ? "step" : undefined
                }
                data-outcome={
                  data.stage_results?.find(
                    (s: Dict) =>
                      s.phase === phase && s.review_cycle === data.review.cycle,
                  )?.state
                }
                data-complete={
                  data.stage_results?.length
                    ? data.stage_results.some(
                        (s: Dict) =>
                          s.phase === phase &&
                          s.review_cycle === data.review.cycle &&
                          s.state === "success",
                      )
                    : data.messages.some(
                        (m: Dict) =>
                          m.phase === phase &&
                          m.review_cycle === data.review.cycle,
                      )
                }
              >
                {label}
              </li>
            ))}
          </ol>
        )}
        {explain && data?.review && (
          <div className="review-toolbar">
            <span>
              {`Council · cycle ${data.review.cycle}`}
              <small>
                {`${data.review.claims.length} claims · `}
                {data.review.synthesis_stale
                  ? "Published answer needs updating"
                  : "Inspect claims, objections and evidence"}
              </small>
            </span>
            {chat?.final_message_id && (
              <CouncilAnswerJump finalId={chat.final_message_id} />
            )}
            <button data-review-trigger onClick={() => setReviewOpen(true)}>
              <Layers3 size={15} /> Claims & evidence
            </button>
          </div>
        )}
        <div className="council-workspace">
          <div
            className="council-feed"
            ref={feed}
            onClick={(event) => {
              const link = (event.target as Element).closest("a[href^='#']");
              const id = link?.getAttribute("href")?.slice(1);
              if (id) {
                const target = document.getElementById(decodeURIComponent(id));
                const disclosure = target?.closest<HTMLDetailsElement>(
                  "details.council-process-group",
                );
                if (disclosure) disclosure.open = true;
              }
            }}
            onScroll={() => {
              const el = feed.current;
              if (el)
                stayAtBottom.current =
                  el.scrollHeight - el.scrollTop - el.clientHeight < 180;
            }}
          >
            {explain && (
              <details className="council-mobile-diagnostics">
                <summary>
                  Behind the answer <ChevronDown size={15} aria-hidden="true" />
                </summary>
                <CouncilDiagnostics
                  data={data}
                  preview={currentPreview}
                  provider={provider}
                  selectedCount={models.length}
                  planned={planned}
                />
              </details>
            )}
            {!chat ? (
              <section className="council-empty">
                <div className="council-welcome-mark" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
                <h2>Ask the council.</h2>
                <p>
                  Get independent answers,
                  <br />
                  then a shared recommendation.
                </p>
                {explain && <CouncilProcessIntro />}
                <div className="council-suggestions">
                  <button
                    onClick={() =>
                      setText(
                        "How should we compare two system designs fairly when one improves latency but increases memory use? Challenge assumptions and propose a concrete evaluation plan.",
                      )
                    }
                  >
                    Compare competing approaches <ArrowUpRight size={15} />
                  </button>
                  <button
                    onClick={() =>
                      setText(
                        "Review this project idea from different perspectives. Establish a reference baseline, challenge weak assumptions, and recommend the smallest useful first version.",
                      )
                    }
                  >
                    Challenge a project plan <ArrowUpRight size={15} />
                  </button>
                </div>
              </section>
            ) : (
              <div className="council-transcript">
                {!explain && data?.review?.synthesis_stale && (
                  <div className="council-state-note" role="status">
                    Published answer needs updating
                  </div>
                )}
                {!!data?.library?.source_changes?.length && (
                  <div className="council-state-note" role="status">
                    A cited source has a newer saved version. Request an updated
                    review before accepting this answer. Earlier publications
                    keep their original source versions.
                  </div>
                )}
                {!!data?.research_limitations?.length && (
                  <div className="council-state-note" role="status">
                    Some research could not complete. Saved replies remain
                    available. Open Sources to inspect limitations or explicitly
                    retry an unconfirmed operation.
                  </div>
                )}
                {data?.degraded && (
                  <div className="council-state-note" role="status">
                    {Object.values(chat.unavailable_members || {})
                      .map((p: any) => p.name)
                      .join(", ")}{" "}
                    unavailable. {data.active_members.length} of{" "}
                    {chat.participants.length} members remain available. Missing
                    replies are not agreement; they will not be invented.
                  </div>
                )}
                {chat.provider === "fixture" && (
                  <div className="council-demo-note">
                    <FlaskConical size={15} /> Synthetic demo. These are
                    scripted participants; no live models are called.
                  </div>
                )}
                {data && <ReviewDeliveryNote data={data} explain={explain} />}
                {!!data?.queued_steering?.length && (
                  <p className="council-state-note" role="status">
                    Your note is queued for the next turn. Independent answers
                    keep their shared starting context.
                  </p>
                )}
                {explain
                  ? data?.messages.map(renderMessage)
                  : groupCouncilMessages(data?.messages || []).map(
                      (group, groupIndex, groups) =>
                        group.discussion ? (
                          <details
                            className="council-process-group"
                            key={group.id}
                            open={
                              groupIndex === groups.length - 1 &&
                              ["running", "waiting"].includes(chat.status)
                            }
                          >
                            <summary>
                              <span
                                className="council-discussion-mark"
                                aria-hidden="true"
                              >
                                <MessageSquare size={16} />
                              </span>
                              <span>
                                <strong>Council discussion</strong>
                                <small>
                                  {group.messages.length}{" "}
                                  {group.messages.length === 1
                                    ? "reply"
                                    : "replies"}{" "}
                                  · Independent answers, challenges & revisions
                                </small>
                              </span>
                              <ChevronDown size={16} aria-hidden="true" />
                            </summary>
                            <div>
                              {group.messages.map((message) =>
                                renderMessage(
                                  message,
                                  data!.messages.indexOf(message),
                                ),
                              )}
                            </div>
                          </details>
                        ) : (
                          group.messages.map((message) =>
                            renderMessage(
                              message,
                              data!.messages.indexOf(message),
                            ),
                          )
                        ),
                    )}
                {data && <LivePublicAnswer data={data} />}
                {!researchingTogether &&
                  (chat.status === "running" ||
                    (chat.status === "paused" &&
                      chat.active_turn &&
                      chat.provider === "nebius_token_factory")) && (
                    <div className="council-thinking" role="status">
                      <span className="council-thinking-dots">
                        <i />
                        <i />
                        <i />
                      </span>
                      <strong>{chat.active_turn?.name || "The council"}</strong>
                      <span>
                        {chat.status === "paused"
                          ? "is finishing this reply before pausing"
                          : !chat.active_turn
                            ? "is preparing the next request"
                            : chat.active_turn?.phase === "synthesis"
                              ? "is writing the final synthesis"
                              : chat.active_turn?.phase === "opening"
                                ? "is forming an independent answer"
                                : "is responding to the discussion"}
                      </span>
                      <ActiveResponseTiming
                        request={data?.active_request}
                        explain={explain}
                      />
                    </div>
                  )}
                {chat.status === "paused" && (
                  <div className="council-state-note">
                    <Pause size={16} />{" "}
                    {chat.pending_request_recovery
                      ? `${chat.pending_request_recovery.name}'s request was interrupted. Retry this response or continue with the other models below. The earlier possible charge stays counted.`
                      : chat.active_turn &&
                          chat.provider === "nebius_token_factory"
                        ? "Pause requested. The current reply and its usage will finish saving; no further requests will start."
                        : "Discussion paused. You can add a note before resuming."}
                  </div>
                )}
                {chat.status === "waiting" && chat.retry_wait && (
                  <div className="council-state-note" role="status">
                    <LoaderCircle size={16} className="council-spin" />
                    <span>
                      {chat.retry_wait.name} is temporarily unavailable.
                      Retrying in{" "}
                      <RetryCountdown notBefore={chat.retry_wait.not_before} />s
                      (retry {chat.retry_wait.attempt} of{" "}
                      {chat.retry_wait.maximum}). Saved answers will not be
                      replayed. You can pause or stop this wait.
                    </span>
                  </div>
                )}
                {chat.status === "interrupted" && (
                  <div className="council-state-note">
                    The executor restarted. Completed replies are saved; resume
                    explicitly to continue.
                  </div>
                )}
                {chat.status === "completed" &&
                  data?.participation_notices?.map((notice: Dict) => (
                    <div
                      className="council-state-note is-error"
                      key={notice.model}
                    >
                      <span>
                        <strong>Participation record:</strong> {notice.name} did
                        not complete its {notice.phase} turn.{" "}
                        {notice.kind === "output_incomplete"
                          ? "The response reached the output token limit."
                          : notice.reason}{" "}
                        Earlier replies remain saved; absence does not imply
                        agreement.
                      </span>
                    </div>
                  ))}
                {data?.output_recovery && (
                  <OutputRecoveryNotice
                    value={data.output_recovery}
                    busy={busy}
                    needsAcknowledgement={
                      data.unknown_paid_attempts > 0 && !retryUnknown
                    }
                    onRecover={() =>
                      control("recover_output", data.output_recovery.call_id)
                    }
                    modelRecovery={data.model_recovery}
                    onContinueWithoutModel={() =>
                      control(
                        "continue_without_model",
                        data.model_recovery.call_id,
                        data.model_recovery.additional_allowance_usd,
                      )
                    }
                  />
                )}
                {chat.error &&
                  !data?.output_recovery &&
                  ["failed", "paused", "interrupted", "unavailable"].includes(
                    chat.status,
                  ) && (
                    <div className="council-state-note is-error" role="alert">
                      {chat.error} Completed replies and attempted requests are
                      saved.
                    </div>
                  )}
              </div>
            )}
          </div>
          <div className="council-composer-area">
            {data?.model_recovery && !data?.output_recovery && (
              <ModelRecoveryNotice
                value={data.model_recovery}
                busy={busy}
                needsAcknowledgement={
                  data.unknown_paid_attempts > 0 && !retryUnknown
                }
                onContinue={() =>
                  control(
                    "continue_without_model",
                    data.model_recovery.call_id,
                    data.model_recovery.additional_allowance_usd,
                  )
                }
              />
            )}
            {data?.review_adoption?.available && (
              <div className="council-method-note">
                <div>
                  <strong>Continue with the Council</strong>
                  <p>
                    Earlier answers keep their original review status. Your next
                    question starts a claim review in this chat.
                  </p>
                  {!data.review_adoption.allowed && (
                    <p>{data.review_adoption.reason}</p>
                  )}
                </div>
              </div>
            )}
            {data?.unknown_paid_attempts > 0 && (
              <label className="council-retry-ack">
                <input
                  type="checkbox"
                  checked={retryUnknown}
                  onChange={(e) => setRetryUnknown(e.target.checked)}
                />{" "}
                Allow further model requests while the earlier charge remains
                unknown and counted.
              </label>
            )}
            {error && (
              <div className="council-error" role="alert">
                <span>{error}</span>
                <button
                  className="council-icon"
                  aria-label="Dismiss error"
                  onClick={() => setError("")}
                >
                  <X size={15} />
                </button>
              </div>
            )}
            {chat && (
              <div className="council-discussion-controls">
                <span>
                  {chat.status === "running"
                    ? "You can steer the next turn."
                    : chat.status === "completed"
                      ? "Read the synthesis, accept it, or ask for a revision."
                      : "Your conversation is saved."}
                </span>
                <div>
                  {chat.status === "completed" &&
                    ["reviewed_v3", "reviewed_v4"].includes(
                      chat.protocol.version,
                    ) && (
                      <button
                        disabled={busy}
                        onClick={async () => {
                          const result = await act(() =>
                            api(`/chats/${cid}/messages`, {
                              text: "Explain the basis, conditions and limits of the saved answer.",
                              action: "explain",
                            }),
                          );
                          if (result) setData(result);
                        }}
                      >
                        Explain this answer
                      </button>
                    )}
                  {["running", "waiting"].includes(chat.status) ? (
                    <button disabled={busy} onClick={() => control("pause")}>
                      <Pause size={14} />{" "}
                      {chat.provider === "nebius_token_factory"
                        ? "Pause after reply"
                        : "Pause"}
                    </button>
                  ) : (
                    ["paused", "interrupted", "failed", "unavailable"].includes(
                      chat.status,
                    ) && (
                      <button
                        disabled={
                          busy ||
                          (!!chat.pending_request_recovery &&
                            data?.unknown_paid_attempts > 0 &&
                            !retryUnknown)
                        }
                        onClick={() => control("resume")}
                      >
                        <Play size={14} />{" "}
                        {chat.pending_request_recovery
                          ? "Retry response"
                          : "Resume"}
                      </button>
                    )
                  )}
                  {!["completed", "cancelled"].includes(chat.status) && (
                    <>
                      <button
                        disabled={
                          busy ||
                          !data?.messages.some(
                            (m: Dict) => m.role === "assistant",
                          )
                        }
                        onClick={() => control("finish")}
                      >
                        <Check size={14} /> Synthesize now
                      </button>
                      <button
                        disabled={busy}
                        onClick={() => control("stop")}
                        title="Stop following turns"
                      >
                        <Square size={12} /> Stop
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}
            {!chat && (
              <div
                className={`council-customize ${explain ? "is-expanded" : ""}`}
              >
                <div className="council-customize-heading">
                  <Layers3 size={15} aria-hidden="true" />
                  <span>{models.length} models</span>
                  {explain ? (
                    <span className="council-customize-label">
                      Council setup
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="council-customize-trigger"
                      aria-expanded={customizeOpen}
                      aria-controls="council-customize-content"
                      aria-haspopup="dialog"
                      onClick={() => setCustomizeOpen(true)}
                    >
                      Customize <ChevronDown size={14} aria-hidden="true" />
                    </button>
                  )}
                </div>
                <CouncilSetupSurface
                  explain={explain}
                  open={customizeOpen}
                  onClose={() => setCustomizeOpen(false)}
                >
                  {!chat &&
                    ["direct_council", "nebius_token_factory"].includes(
                      provider,
                    ) &&
                    searchEnabled && (
                      <label className="research-query">
                        Shared public search topic (optional)
                        <input
                          value={searchQuery}
                          maxLength={400}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          placeholder="For example: official solar efficiency limits"
                        />
                        <small>
                          Leave blank to build short search queries from your
                          question. Search runs before each reply; documents
                          stay in Sources.
                        </small>
                      </label>
                    )}
                  {!chat && provider === "openrouter_free" && (
                    <div className="council-free-status" role="status">
                      <span>
                        {quota?.error ||
                          (quota?.known
                            ? `${quota.remaining} / ${quota.limit} provider requests left today; ${localRemaining ?? "unknown"} workspace attempts left.`
                            : "Provider quota not yet verified.")}{" "}
                        Shared free-model capacity is not guaranteed.
                        {setupBlocked &&
                          !quota?.error &&
                          ` This council needs ${requiredStart} attempts including recovery; reduce the models or wait for the daily reset.`}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          act(async () => {
                            setAvailability(await api("/chats/availability"));
                            await loadBoot();
                          })
                        }
                        disabled={busy}
                      >
                        Refresh allowance
                      </button>
                      {setupBlocked &&
                        !quota?.error &&
                        availableCalls >= 11 && (
                          <button
                            type="button"
                            onClick={() => {
                              setModels(models.slice(0, 2));
                            }}
                          >
                            Use 2 models
                          </button>
                        )}
                    </div>
                  )}
                  {!chat && provider === "nebius_token_factory" && (
                    <div className="council-direct-status" role="status">
                      <span>
                        {!boot?.providers.nebius_token_factory.ready && (
                          <>
                            Token Factory needs a connection and price refresh.
                            Your chosen models are preserved.{" "}
                            <button
                              type="button"
                              onClick={() => {
                                api("/chats/token-factory/refresh", {})
                                  .then((result) => {
                                    setBoot(result);
                                    setSetupPreview(null);
                                    if (
                                      !result.providers.nebius_token_factory
                                        .ready
                                    )
                                      setError(
                                        result.providers.nebius_token_factory
                                          .price_refresh?.message ||
                                          "Token Factory could not reconnect. Your models remain selected.",
                                      );
                                  })
                                  .catch((error) => setError(error.message));
                              }}
                            >
                              Reconnect Token Factory
                            </button>{" "}
                          </>
                        )}
                        Nemotron Super leads. {models.length} Token Factory
                        models · shared $24 total application cap across all
                        chats. Cached prices use reported tokens; missing
                        telemetry stays unknown. Raw opening answers use the
                        requested reasoning controls without a word limit; the
                        full review follows with model-specific controls. Output
                        stays within model context and remaining credit.
                      </span>
                    </div>
                  )}
                  {!chat && provider === "direct_council" && (
                    <div className="council-direct-status" role="status">
                      <span>
                        Z.ai, Gemini, NVIDIA NIM and Groq use their own
                        endpoints. {directSettings?.daily_remaining} /{" "}
                        {directSettings?.daily_attempt_cap} local attempts left
                        today. {planned} planned calls +{" "}
                        {searchEnabled ? "5 research calls + " : ""}3 shared
                        retry attempts. Provider quotas vary; invoice cost is
                        not reported by every API.
                        {setupBlocked
                          ? " This setup does not fit the current local allowance or free access is not confirmed."
                          : ""}
                      </span>
                    </div>
                  )}
                  {!chat && (
                    <div className="council-setup">
                      <label className="council-provider-select">
                        <ShieldCheck size={15} />
                        <select
                          aria-label="Council provider"
                          value={provider}
                          onChange={(e) => {
                            setProvider(e.target.value);
                            setModels(
                              boot
                                ? defaultCouncilModels(boot, e.target.value)
                                : [],
                            );
                          }}
                        >
                          {Object.entries(providerName)
                            .filter(
                              ([key]) =>
                                key !== "openrouter_free" ||
                                boot?.providers.openrouter_free.enabled,
                            )
                            .map(([key, name]) => (
                              <option
                                key={key}
                                value={key}
                                disabled={
                                  !(
                                    boot?.providers[key]?.ready ||
                                    (key === "nebius_token_factory" &&
                                      boot?.providers[key]?.preferred) ||
                                    (key === "openrouter_free" &&
                                      boot?.providers[key].configured)
                                  )
                                }
                              >
                                {String(name)}
                                {!(
                                  boot?.providers[key]?.ready ||
                                  (key === "nebius_token_factory" &&
                                    boot?.providers[key]?.preferred) ||
                                  (key === "openrouter_free" &&
                                    boot?.providers[key].configured)
                                )
                                  ? " (locked)"
                                  : ""}
                              </option>
                            ))}
                        </select>
                      </label>
                      <button
                        className="council-members-toggle"
                        onClick={() => setMembersOpen(!membersOpen)}
                        aria-expanded={membersOpen}
                      >
                        <Layers3 size={15} /> {models.length} models{" "}
                        <ChevronDown size={14} />
                      </button>
                      {membersOpen && (
                        <fieldset className="council-model-choices">
                          <legend>Distinct participants</legend>
                          {options.map((m: Dict) => (
                            <label key={m.id}>
                              <input
                                type="checkbox"
                                disabled={m.configured === false}
                                checked={models.includes(m.id)}
                                onChange={(e) =>
                                  setModels(
                                    e.target.checked
                                      ? [...models, m.id]
                                      : models.filter((id) => id !== m.id),
                                  )
                                }
                              />
                              <span>
                                {m.name}
                                <small>{m.id}</small>
                                {m.selection_notice && (
                                  <small>{m.selection_notice}</small>
                                )}
                              </span>
                            </label>
                          ))}
                        </fieldset>
                      )}
                    </div>
                  )}
                  {!chat && (
                    <>
                      <ReviewSetup
                        value={reviewOptions}
                        onChange={setReviewOptions}
                      />
                      {currentPreview && (
                        <details className="review-setup-details">
                          <summary>Review role assignments</summary>
                          <dl className="review-role-list">
                            {Object.entries(
                              currentPreview.role_names || {},
                            ).map(([phase, name]) => (
                              <div key={phase}>
                                <dt>{phase}</dt>
                                <dd>{String(name)}</dd>
                              </div>
                            ))}
                          </dl>
                          <p>
                            Each proposer also replies to its own objections.
                            Shared models do not provide independent external
                            verification.
                          </p>
                        </details>
                      )}
                    </>
                  )}
                </CouncilSetupSurface>
              </div>
            )}
            {!chat && setupBlocked && !explain && !customizeOpen && (
              <div className="council-error" role="alert">
                {currentPreview?.reason ||
                  "This setup cannot start with the current allowance or provider access."}{" "}
                <button onClick={() => setCustomizeOpen(true)}>
                  Review setup
                </button>
              </div>
            )}
            {tokenFactory && (
              <>
                {explain && (
                  <CouncilThinkingDetails
                    settings={thinkingSettings}
                    models={
                      chat
                        ? (data?.effective_members || chat.participants).map(
                            (member: Dict) => member.model,
                          )
                        : models
                    }
                    activeLevel={chat?.active_turn?.thinking_level}
                  />
                )}
                {explain && chat && data?.conversation_allowance && (
                  <ConversationAllowance
                    value={data.conversation_allowance}
                    budget={data.budget}
                    chatId={chat.id}
                    onChange={refresh}
                  />
                )}
              </>
            )}
            <form
              className="council-composer"
              onSubmit={(e) => {
                e.preventDefault();
                if (!sendDisabled) send();
              }}
            >
              {!chat && (
                <label className="composer-source-upload">
                  Add sources
                  {pendingSources.length
                    ? ` · ${pendingSources.length} selected`
                    : ""}
                  <input
                    aria-label="Attach sources before starting"
                    type="file"
                    multiple
                    accept=".txt,.md,.html,.pdf,.docx"
                    disabled={busy}
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []);
                      if (
                        files.length > 4 ||
                        files.some((file) => file.size > 2097152)
                      ) {
                        setError(
                          "Choose up to four documents, no larger than 2 MiB each.",
                        );
                        e.target.value = "";
                        return;
                      }
                      setPendingSources(files);
                    }}
                  />
                </label>
              )}
              <textarea
                ref={input}
                id="council-question"
                name="question"
                aria-label="Message the council"
                placeholder={
                  finalWriting
                    ? "The final synthesis is being written…"
                    : chat
                      ? "Add a concern, challenge an answer, or guide the next turn…"
                      : "What would you like to work through?"
                }
                rows={2}
                maxLength={8000}
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    if (!sendDisabled) send();
                  }
                }}
              />
              <div className="council-composer-bottom">
                <span>
                  {chat
                    ? finalWriting
                      ? "Wait for this turn before sending a follow-up."
                      : followupBlocked
                        ? data?.continuation?.reason ||
                          "The free request allowance is exhausted. Your chat is saved; continue here when the allowance resets."
                        : stopped
                          ? "Council stopped. Start a new council to continue."
                          : "Enter to send · Shift + Enter for a new line"
                    : models.length < 2
                      ? "Choose at least two distinct models."
                      : explain
                        ? `${models.length} independent answers · challenges · revisions · checks · final answer`
                        : "Enter to send · Shift + Enter for a new line"}
                </span>
                <div className="council-composer-actions">
                  {["direct_council", "nebius_token_factory"].includes(
                    chat?.provider || provider,
                  ) && (
                    <CouncilSearch
                      chat={chat}
                      configured={!!boot?.research?.configured}
                      selected={searchWeb}
                      onSelect={setSearchWeb}
                      onData={setData}
                    />
                  )}
                  {tokenFactory && (
                    <>
                      <CouncilThinking
                        level={
                          chat
                            ? data?.thinking?.level ||
                              chat.thinking_level ||
                              "balanced"
                            : thinkingLevel
                        }
                        settings={thinkingSettings}
                        chatId={chat?.id}
                        onSelect={setThinkingLevel}
                        onChange={refresh}
                      />
                      <CouncilContext
                        status={
                          (chat && data?.context_status) || {
                            supported: true,
                            capacity_tokens:
                              boot?.providers?.nebius_token_factory?.generation
                                ?.context_tokens || 262144,
                            automatic_threshold_percent: 80,
                            mode: "adaptive",
                            latest: null,
                          }
                        }
                        chatId={chat?.id}
                        explain={explain}
                        onChange={refresh}
                      />
                    </>
                  )}
                  <button
                    className="council-send"
                    type="submit"
                    disabled={sendDisabled}
                    aria-label={cid ? "Send message" : "Start council"}
                  >
                    {busy ? (
                      <LoaderCircle size={18} className="council-spin" />
                    ) : (
                      <ArrowUp size={19} />
                    )}
                  </button>
                </div>
              </div>
            </form>
            {chat && <ConversationTotals accounting={data?.accounting} />}
            {(!tokenFactory || explain) && (
              <div className="council-composer-footnote">
                <span>
                  {!explain
                    ? chat?.provider === "fixture" ||
                      (!chat && provider === "fixture")
                      ? "Scripted demo · no live models"
                      : "Provider limits may pause a council · no paid fallback"
                    : chat
                      ? chat.provider === "fixture"
                        ? "Scripted demo · no inference"
                        : chat.provider === "direct_council"
                          ? `${data?.budget.attempts || 0} total attempts · ${data?.direct_capacity?.daily_remaining ?? "?"} left today · follow-ups stay in this chat`
                          : chat.provider === "openrouter_free"
                            ? `${data?.budget.attempts || 0} / ${data?.budget.attempt_cap || freeCap} attempts · $${(data?.budget.settled_usd || 0).toFixed(4)} reported`
                            : `$${(data?.budget.settled_usd || 0).toFixed(4)} settled · existing credit only`
                      : provider === "fixture"
                        ? "Scripted demo · no live models"
                        : provider === "direct_council"
                          ? `${planned} planned calls + ${searchEnabled ? "5 research calls + " : ""}3 shared retries · no paid fallback`
                          : provider === "openrouter_free"
                            ? `${planned} planned calls + up to ${freeSettings?.retry_allowance || 3} retries · free only${planned > freeCap ? " · exceeds conversation allowance" : ""}`
                            : `${planned} calls maximum · verified existing credit only`}
                </span>
                <span>
                  {explain
                    ? "Public replies · scoped checks · human judgment"
                    : "Your conversations stay here."}
                </span>
              </div>
            )}
          </div>
        </div>
      </main>
      {explain && (
        <div className="council-desktop-diagnostics">
          <CouncilDiagnostics
            data={data}
            preview={currentPreview}
            provider={provider}
            selectedCount={models.length}
            planned={planned}
          />
        </div>
      )}
      {editing && chat && (
        <CouncilMessageEditor
          key={editing.id}
          message={editing}
          blocked={
            !!chat.active_turn || ["running", "waiting"].includes(chat.status)
          }
          busy={busy}
          error={editError}
          unknownCharge={!!data?.unknown_paid_attempts}
          onClose={() => setEditing(null)}
          onSubmit={regenerateMessage}
          onPause={() => control("pause")}
        />
      )}
      {compareOpen && chat && data && (
        <CouncilCompare
          data={data}
          open
          onClose={closeCompare}
          onSource={openSource}
        />
      )}
      {reviewOpen && data?.review && (
        <ReviewPanel
          data={data}
          onData={setData}
          onClose={() => {
            setReviewOpen(false);
            requestAnimationFrame(() =>
              document
                .querySelector<HTMLButtonElement>("[data-review-trigger]")
                ?.focus(),
            );
          }}
        />
      )}
    </div>
  );
}
