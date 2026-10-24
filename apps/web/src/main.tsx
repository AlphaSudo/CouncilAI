import React, { useState, useEffect, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowRight,
  Plus,
  FlaskConical,
  Layers3,
  Network,
  ShieldCheck,
  LockKeyhole,
  Check,
  ChevronDown,
  ChevronRight,
  Pause,
  Play,
  RotateCcw,
  Download,
  Activity,
  Command,
  Search,
  X,
  Menu,
  FileCheck2,
  MessageSquare,
  AlertCircle,
  CheckCircle2,
  Settings2,
  LogOut,
  LoaderCircle,
} from "lucide-react";
import { api, openLocalSession } from "./api";
import type { Dict, ResearchView, View } from "./types";
import type { MissionBrief } from "./contracts.generated";
import "./style.css";
import CouncilChat from "./CouncilChat";

const groups: { title: string; items: View[] }[] = [
  { title: "01 / Frame", items: ["Mission room", "Step graph"] },
  { title: "02 / Challenge", items: ["Council round", "Conflict map"] },
  {
    title: "03 / Test",
    items: ["Experiment board", "Evidence", "Bottleneck map"],
  },
  { title: "04 / Decide", items: ["Decision ledger", "Research report"] },
];
const money = (n: number) => "$" + (n || 0).toFixed(4);
const short = (s: string) => s?.replace(/_/g, " ");
const seatCode: Dict = {
  hardware: "HW",
  runtime: "RT",
  engine: "IE",
  algorithms: "MA",
};
function Badge({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
function Button({
  children,
  onClick,
  disabled = false,
  kind = "",
  title,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  kind?: string;
  title?: string;
}) {
  return (
    <button
      className={"button " + kind}
      onClick={onClick}
      disabled={disabled}
      title={title}
    >
      {children}
    </button>
  );
}
function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-mark">
        <Layers3 size={24} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Json({ value }: { value: unknown }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}
function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
function Dialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const nodes = Array.from(
          document.querySelectorAll<HTMLElement>(
            ".dialog button:not(:disabled),.dialog input,.dialog textarea,.dialog select,.dialog a",
          ),
        );
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    document
      .querySelector<HTMLElement>(
        ".dialog input,.dialog textarea,.dialog button",
      )
      ?.focus();
    return () => {
      document.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

function ResearchApp() {
  const [boot, setBoot] = useState<Dict | null>(null),
    [data, setData] = useState<ResearchView | null>(null),
    [mid, setMid] = useState(""),
    [sid, setSid] = useState(""),
    [view, setView] = useState<View>("Mission room"),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [authenticated, setAuthenticated] = useState(false),
    [loading, setLoading] = useState(true),
    [modal, setModal] = useState(""),
    [mobile, setMobile] = useState(false),
    [artifact, setArtifact] = useState<unknown>(null);
  const loadBoot = useCallback(async () => {
    const b = await api("/bootstrap");
    setBoot(b);
    setAuthenticated(true);
    setMid((current) => current || b.missions[0]?.id || "");
    return b;
  }, []);
  const refresh = useCallback(async () => {
    if (mid) {
      const d = await api("/missions/" + mid);
      setData(d);
      setSid((current) =>
        d.steps.some((s: Dict) => s.id === current)
          ? current
          : d.steps[0]?.id || "",
      );
    }
  }, [mid]);
  useEffect(() => {
    (async () => {
      try {
        await openLocalSession();
        await loadBoot();
      } catch {
        setAuthenticated(false);
      } finally {
        setLoading(false);
      }
    })();
  }, []);
  useEffect(() => {
    if (authenticated) refresh().catch((e) => setError(e.message));
  }, [mid, authenticated, refresh]);
  useEffect(() => {
    if (!mid || !authenticated) return;
    const stream = new EventSource("/api/missions/" + mid + "/events");
    let cursor = 0,
      scheduled: number | undefined;
    stream.addEventListener("research", (event) => {
      const sequence = JSON.parse((event as MessageEvent).data).seq;
      if (sequence <= cursor) return;
      cursor = sequence;
      window.clearTimeout(scheduled);
      scheduled = window.setTimeout(() => refresh().catch(() => {}), 50);
    });
    return () => {
      stream.close();
      window.clearTimeout(scheduled);
    };
  }, [mid, authenticated, refresh]);
  async function act(fn: () => Promise<any>, success?: string) {
    setBusy(true);
    setError("");
    try {
      const result = await fn();
      await refresh();
      await loadBoot();
      if (success) {
        setNotice(success);
        setTimeout(() => setNotice(""), 5000);
      }
      return result;
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setBusy(false);
    }
  }
  const step = data?.steps.find((s) => s.id === sid),
    mission = data?.mission;
  const freeMission = mission?.brief.provider === "openrouter_free";
  const rounds = data?.rounds.filter((r) => r.step_id === sid) || [],
    round = rounds[rounds.length - 1];
  const hypotheses = data?.hypotheses.filter((h) => h.step_id === sid) || [],
    experiments = data?.experiments.filter((e) => e.step_id === sid) || [],
    evidences = data?.evidences.filter((e) => e.step_id === sid) || [],
    decisions = data?.decisions.filter((d) => d.step_id === sid) || [],
    concerns = data?.concerns.filter((c) => c.step_id === sid) || [];
  const openConcerns = concerns.filter((c) => c.status !== "resolved");
  const nav = (next: View) => {
    setView(next);
    setMobile(false);
  };
  const stepAction = (verb: string) =>
    act(() =>
      api(`/steps/${sid}/control/${verb}`, {
        expected_revision: step?.revision,
      }),
    );
  const startRound = () =>
    act(
      () =>
        api(`/steps/${sid}/rounds`, {
          expected_revision: step?.revision,
          mode: mission?.brief.mode,
        }),
      "Independent round queued.",
    );
  async function inspect(id: string) {
    const result = await act(() => api("/artifacts/" + id));
    if (result) {
      setArtifact(result);
      setModal("artifact");
    }
  }
  async function exportPack() {
    const result = await act(
      () => api(`/missions/${mid}/exports`, {}),
      "Reproducibility pack created.",
    );
    if (result) {
      const a = document.createElement("a");
      a.href = "/api/exports/" + result.id + "/download";
      a.click();
    }
  }

  if (loading)
    return (
      <div className="splash">
        <span className="brand-symbol">Z</span>
        <p>Opening the research workspace…</p>
      </div>
    );
  if (!authenticated)
    return (
      <main className="login">
        <div className="login-brand">
          <span className="brand-symbol">Z</span>
          <strong>ZeroWall</strong>
        </div>
        <div className="login-form">
          <span className="eyebrow">Local research workspace</span>
          <h1>Open your research workspace.</h1>
          <p>Continue your research or start a new council conversation.</p>
          {error && (
            <p role="alert" className="error-text">
              {error}
            </p>
          )}
          <Button
            disabled={busy}
            onClick={() =>
              act(async () => {
                await openLocalSession();
                await loadBoot();
              })
            }
          >
            Open workspace <ArrowRight size={17} />
          </Button>
          <a href="/">
            Go to prompt <ArrowUpRight size={17} />
          </a>
          <small>Provider keys stay on the server.</small>
        </div>
      </main>
    );

  return (
    <div className="app-shell">
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            nav("Mission room");
          }}
        >
          <span className="brand-symbol">Z</span>
          <span>
            ZeroWall<span className="brand-dot">.</span>
          </span>
        </a>
        <div className="workspace-label">
          Research workspace <span>LOCAL</span>
        </div>
        <button className="mission-switch" onClick={() => setModal("missions")}>
          <span className="small-square">
            <FlaskConical size={17} />
          </span>
          <span>{mission?.brief.title || "Choose a mission"}</span>
          <ChevronDown size={15} />
        </button>
        <a className="research-chat-link" href="/">
          <MessageSquare size={15} /> Council chat <ArrowUpRight size={13} />
        </a>
        <nav aria-label="Research views">
          {groups.map((g) => (
            <div className="nav-group" key={g.title}>
              <p>{g.title}</p>
              {g.items.map((item) => (
                <button
                  key={item}
                  className={view === item ? "selected" : ""}
                  onClick={() => nav(item)}
                >
                  <span className="nav-tick" />
                  {item}
                  {item === "Council round" &&
                    round?.status === "committed" && (
                      <span className="nav-count">4</span>
                    )}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="provider-dot" />
          <div>
            <strong>{freeMission ? "OpenRouter free" : "Token Factory"}</strong>
            <p>
              {freeMission
                ? "Zero-price models only"
                : boot?.live_ready
                  ? "Verification recorded"
                  : "Live dispatch locked"}
            </p>
          </div>
          <button
            className="icon-button"
            title="Provider and spending settings"
            aria-label="Provider and spending settings"
            onClick={() => setModal("settings")}
          >
            <Settings2 size={16} />
          </button>
        </div>
        <div className="director">
          <span>AD</span>
          <div>
            <strong>Human director</strong>
            <small>Final decision authority</small>
          </div>
          <button
            className="icon-button"
            aria-label="Sign out"
            onClick={() =>
              act(async () => {
                await api("/logout", {});
                setAuthenticated(false);
                setData(null);
              })
            }
          >
            <LogOut size={15} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">
              Workspace <ChevronRight size={14} /> <strong>{view}</strong>
            </span>
          </div>
          <div className="topbar-right">
            <span className="connection">
              <span /> Local · saved
            </span>
            <button
              className="text-button"
              onClick={() => setModal("settings")}
            >
              <ShieldCheck size={15} /> Credit only
            </button>
          </div>
        </header>
        {error && (
          <div className="alert" role="alert">
            <AlertCircle size={17} />
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}
        {notice && (
          <div className="toast" role="status">
            <CheckCircle2 size={17} />
            {notice}
          </div>
        )}
        {busy && (
          <div className="working" role="status">
            <LoaderCircle size={14} /> Saving action…
          </div>
        )}
        {!data ? (
          <div className="welcome">
            <span className="eyebrow">Research starts with a question</span>
            <h1>
              Frame. Challenge.
              <br />
              Test. Decide.
            </h1>
            <p>
              Create a mission, give four research seats an independent first
              pass, then let evidence change the direction.
            </p>
            <Button onClick={() => setModal("new")}>
              Create a mission <Plus size={17} />
            </Button>
            <div className="welcome-flow">
              01 Mission <ArrowRight /> 02 Council <ArrowRight /> 03 Evidence{" "}
              <ArrowRight /> 04 Decision
            </div>
          </div>
        ) : (
          <>
            <section className="mission-heading">
              <div>
                <div className="eyebrow">
                  <span className="live-dot" /> Mission{" "}
                  {mid.slice(-4).toUpperCase()} <span className="slash">/</span>{" "}
                  Revision {mission?.revision}{" "}
                  <Badge
                    tone={mission?.brief.mode === "fixture" ? "muted" : "green"}
                  >
                    {mission?.brief.mode === "fixture"
                      ? "Fixture council · local tools"
                      : freeMission
                        ? "OpenRouter · free only"
                        : "Live Token Factory"}
                  </Badge>
                </div>
                <h1>{view === "Mission room" ? mission?.brief.title : view}</h1>
                <p>
                  {view === "Mission room"
                    ? "A governed investigation. Independent views, bounded experiments, inspectable decisions."
                    : step?.title +
                      " · Step revision " +
                      step?.revision +
                      " · " +
                      short(step?.status || "")}
                </p>
              </div>
              <div className="heading-actions">
                <Button
                  kind="secondary"
                  onClick={exportPack}
                  disabled={busy || !data.rounds.length}
                >
                  <Download size={16} /> Export pack
                </Button>
                {mission?.status === "draft" ? (
                  <Button
                    onClick={() =>
                      act(
                        () =>
                          api(`/missions/${mid}/freeze`, {
                            expected_revision: mission.revision,
                          }),
                        "Mission frozen.",
                      )
                    }
                    disabled={busy}
                  >
                    <LockKeyhole size={16} /> Freeze mission
                  </Button>
                ) : (
                  <Button
                    onClick={startRound}
                    disabled={
                      busy ||
                      step?.paused ||
                      step?.stale ||
                      step?.status === "committing" ||
                      step?.status === "approved"
                    }
                  >
                    <Plus size={16} /> New round
                  </Button>
                )}
              </div>
            </section>
            <div className="budget-strip">
              <div>
                <span className="mini-label">MISSION ALLOWANCE</span>
                <strong>{money(mission?.brief.budget_usd)}</strong>
              </div>
              <div>
                <span className="mini-label">SETTLED</span>
                <strong>{money(data.budget.settled_usd)}</strong>
              </div>
              <div>
                <span className="mini-label">RESERVED / UNKNOWN</span>
                <strong>
                  {money(data.budget.reserved_usd + data.budget.unknown_usd)}
                </strong>
              </div>
              <div className="budget-progress">
                <div>
                  <span>
                    {freeMission
                      ? "Free mission calls"
                      : "Existing credit authorization"}
                  </span>
                  <span>
                    {freeMission
                      ? `${data.budget.attempts} / 12 attempts`
                      : `${money(data.budget.absolute_cap_usd)} max · $0 additional`}
                  </span>
                </div>
                <div className="progress-track">
                  <i
                    style={{
                      width:
                        Math.min(
                          100,
                          (freeMission
                            ? data.budget.attempts / 12
                            : data.budget.global_committed_usd / data.budget.absolute_cap_usd) * 100,
                        ) + "%",
                    }}
                  />
                </div>
              </div>
              <button
                onClick={() => setModal("settings")}
                className="budget-state"
              >
                <LockKeyhole size={14} />
                {freeMission
                  ? boot?.openrouter_free?.ready
                    ? "Free calls available"
                    : "Free calls blocked"
                  : boot?.live_ready
                    ? "Live controls recorded"
                    : "Live spending locked"}
                <ArrowUpRight size={14} />
              </button>
            </div>
            <div className="step-strip">
              <span>Research steps</span>
              {data.steps.map((s, index) => (
                <button
                  key={s.id}
                  className={sid === s.id ? "active" : ""}
                  onClick={() => setSid(s.id)}
                >
                  <span className="step-number">
                    {s.status === "approved" ? (
                      <Check size={12} />
                    ) : (
                      String(index + 1).padStart(2, "0")
                    )}
                  </span>
                  {s.title}
                  <span className={"state-dot " + s.status} />
                  {index < data.steps.length - 1 && <ChevronRight size={13} />}
                </button>
              ))}
            </div>
            <div className="workspace-grid">
              <main className="workspace-content">
                {view === "Mission room" && (
                  <>
                    <section className="framing">
                      <div className="section-title">
                        <span className="eyebrow">01 / Research brief</span>
                        <Badge>{mission?.status}</Badge>
                      </div>
                      <h2>{mission?.brief.goal}</h2>
                      <div className="brief-details">
                        <div>
                          <h4>Deliverable</h4>
                          <p>{mission?.brief.deliverable}</p>
                        </div>
                        <div>
                          <h4>Primary objective</h4>
                          <p>{short(mission?.brief.primary_metric)}</p>
                          <small>
                            Validity and quality gates apply before cost.
                          </small>
                        </div>
                      </div>
                      <div className="constraints">
                        <h4>Frozen constraints</h4>
                        {mission?.brief.constraints.map(
                          (c: string, i: number) => (
                            <div key={i}>
                              <ShieldCheck size={15} />
                              <span>{c}</span>
                            </div>
                          ),
                        )}
                      </div>
                    </section>
                    <section className="section-block">
                      <div className="section-title">
                        <div>
                          <span className="eyebrow">
                            02 / Current investigation
                          </span>
                          <h2>{step?.title}</h2>
                        </div>
                        <Badge
                          tone={step?.status === "approved" ? "green" : ""}
                        >
                          {short(step?.status)}
                        </Badge>
                      </div>
                      <div className="phase-line">
                        {[
                          "ready",
                          "committing",
                          "reviewing",
                          "awaiting_evidence",
                          "decision_ready",
                          "approved",
                        ].map((phase, i) => (
                          <div
                            className={phase === step?.status ? "current" : ""}
                            key={phase}
                          >
                            <span>{String(i + 1).padStart(2, "0")}</span>
                            <strong>
                              {
                                [
                                  "Frame",
                                  "Commit & reveal",
                                  "Cross-review",
                                  "Test",
                                  "Decision",
                                  "Approved",
                                ][i]
                              }
                            </strong>
                          </div>
                        ))}
                      </div>
                      <div className="next-action">
                        <span className="round-icon">
                          <ArrowUpRight size={21} />
                        </span>
                        <div>
                          <strong>
                            {!round
                              ? "Collect independent views"
                              : !round.revealed
                                ? "Inspect and reveal the round"
                                : !round.reviews_complete
                                  ? "Challenge the mechanisms"
                                  : !evidences.length
                                    ? "Test a falsifiable prediction"
                                    : "Record what the evidence changed"}
                          </strong>
                          <p>
                            {!round
                              ? "All four seats receive the same frozen context with separate role instructions."
                              : !round.revealed
                                ? "Submissions stay private until all four valid commitments are ready."
                                : !round.reviews_complete
                                  ? "Cross-examine controls, trade-offs and unresolved director concerns."
                                  : !evidences.length
                                    ? "Approve a bounded experiment and preserve its raw result."
                                    : "Keep alternatives, dissent and remaining uncertainty in the decision."}
                          </p>
                        </div>
                        <button
                          className="icon-button"
                          aria-label="Go to next research action"
                          onClick={() =>
                            nav(
                              !round || !round.reviews_complete
                                ? "Council round"
                                : !evidences.length
                                  ? "Experiment board"
                                  : "Decision ledger",
                            )
                          }
                        >
                          <ArrowRight size={20} />
                        </button>
                      </div>
                    </section>
                    <section className="section-block">
                      <div className="section-title">
                        <h3>Source packet</h3>
                        <span className="muted-text">
                          {mission?.brief.sources.length} sources · frozen with
                          mission
                        </span>
                      </div>
                      {mission?.brief.sources.map((s: Dict) => (
                        <details className="source" key={s.id}>
                          <summary>
                            <span>{s.id}</span>
                            {s.provenance}
                            <ChevronDown size={15} />
                          </summary>
                          <p>{s.text}</p>
                        </details>
                      ))}
                      <div className="protocol-foot">
                        <FileCheck2 size={15} />
                        <span>
                          Protocol{" "}
                          {mission?.protocol_hash?.slice(0, 16) || "not frozen"}{" "}
                          · No provider hardware observation
                        </span>
                      </div>
                    </section>
                  </>
                )}
                {view === "Step graph" && (
                  <section className="section-block">
                    <span className="eyebrow">Decision dependencies</span>
                    <h2>Evidence before the next step.</h2>
                    <div className="dependency-graph">
                      {data.steps.map((s, i) => (
                        <React.Fragment key={s.id}>
                          {i > 0 && (
                            <div className="dependency-link">
                              <ArrowRight />
                            </div>
                          )}
                          <button
                            className={
                              "dependency-node " +
                              (s.id === sid ? "active" : "")
                            }
                            onClick={() => setSid(s.id)}
                          >
                            <span className="eyebrow">Step {i + 1}</span>
                            <h3>{s.title}</h3>
                            <Badge>{short(s.status)}</Badge>
                            <p>
                              {s.depends_on.length
                                ? `Requires ${s.depends_on.map((id: string) => data.steps.find((d) => d.id === id)?.title).join(", ")}`
                                : "No prerequisites"}
                            </p>
                            <small>
                              Revision {s.revision}
                              {s.stale ? " · stale" : ""}
                            </small>
                          </button>
                        </React.Fragment>
                      ))}
                    </div>
                    <p className="muted-text">
                      Reopening a prerequisite invalidates its decision and
                      marks every dependent step stale. Historical evidence
                      remains inspectable.
                    </p>
                  </section>
                )}
                {view === "Council round" && (
                  <>
                    <div className="section-title">
                      <div>
                        <span className="eyebrow">
                          Independent commit → atomic reveal
                        </span>
                        <h2>Four seats. One shared context.</h2>
                      </div>
                      {round && (
                        <select
                          aria-label="Council round history"
                          value={round.id}
                          onChange={(e) => {
                            setArtifact(
                              rounds.find((r) => r.id === e.target.value),
                            );
                            setModal("artifact");
                          }}
                        >
                          {rounds.map((r, i) => (
                            <option key={r.id} value={r.id}>
                              Round {i + 1} · {short(r.status)}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                    {!round ? (
                      <Empty title="The council is ready">
                        Freeze the mission and start a round. Four role-isolated
                        submissions will commit privately.
                      </Empty>
                    ) : (
                      <>
                        <div className="round-meta">
                          <span>
                            Context{" "}
                            <code>{round.context_hash.slice(0, 16)}</code>
                          </span>
                          <span>Concern revision {round.concern_revision}</span>
                          <Badge>{short(round.status)}</Badge>
                          {[
                            "queued",
                            "committing",
                            "committed",
                            "reviewing",
                            "failed",
                            "interrupted",
                          ].includes(round.status) && (
                            <Button
                              kind="text"
                              disabled={busy}
                              onClick={() =>
                                act(
                                  () =>
                                    api(`/rounds/${round.id}/cancel`, {
                                      expected_revision: step?.revision,
                                    }),
                                  "Round cancelled; existing evidence and charges retained.",
                                )
                              }
                            >
                              Cancel round
                            </Button>
                          )}
                        </div>
                        {["failed", "interrupted"].includes(round.status) && (
                          <div className="recovery-banner">
                            <div>
                              <strong>Valid commitments are preserved.</strong>
                              <p>
                                {round.error ||
                                  "The executor stopped before this phase finished."}
                              </p>
                            </div>
                            <Button
                              kind="secondary"
                              disabled={busy}
                              onClick={() =>
                                act(
                                  () =>
                                    api(`/rounds/${round.id}/continue`, {
                                      expected_revision: step?.revision,
                                    }),
                                  "Continuing missing seats only.",
                                )
                              }
                            >
                              <Play size={14} /> Continue missing seats
                            </Button>
                          </div>
                        )}
                        <div className="seat-grid">
                          {round.seats.map((seat: Dict) => (
                            <article className="seat" key={seat.id}>
                              <div className="seat-top">
                                <span className="seat-avatar">
                                  {seatCode[seat.id]}
                                </span>
                                <Badge
                                  tone={
                                    seat.state === "pending" ? "muted" : "green"
                                  }
                                >
                                  {short(seat.state)}
                                </Badge>
                              </div>
                              <h3>{seat.name}</h3>
                              <p className="seat-role">{seat.role}</p>
                              <div className="model-label">
                                <span>Actual model</span>
                                <code>{seat.model}</code>
                              </div>
                              {round.revealed ? (
                                round.submissions
                                  ?.filter((sub: Dict) => sub.seat === seat.id)
                                  .map((sub: Dict) => (
                                    <div className="submission" key={sub.id}>
                                      <h4>Mechanism</h4>
                                      <p>{sub.content.mechanism}</p>
                                      <h4>Predicted signature</h4>
                                      <p>{sub.content.prediction}</p>
                                      <h4>Kill rule</h4>
                                      <p>{sub.content.kill_rule}</p>
                                      <details>
                                        <summary>
                                          Uncertainty & provenance{" "}
                                          <ChevronDown size={13} />
                                        </summary>
                                        <p>{sub.content.uncertainty}</p>
                                        <code>{sub.commitment}</code>
                                        <Button
                                          kind="text"
                                          onClick={() =>
                                            inspect(sub.artifact_id)
                                          }
                                        >
                                          Inspect raw artifact{" "}
                                          <ArrowUpRight size={14} />
                                        </Button>
                                      </details>
                                    </div>
                                  ))
                              ) : (
                                <div className="private-seat">
                                  <LockKeyhole size={22} />
                                  <strong>
                                    {seat.state === "committed"
                                      ? "Commitment saved"
                                      : "Awaiting submission"}
                                  </strong>
                                  <p>
                                    Content stays private until the four-seat
                                    reveal barrier.
                                  </p>
                                  {seat.commitment && (
                                    <code>{seat.commitment.slice(0, 18)}…</code>
                                  )}
                                </div>
                              )}
                            </article>
                          ))}
                        </div>
                        <div className="council-actions">
                          <p>
                            <ShieldCheck size={16} />
                            {round.mode === "fixture"
                              ? "Synthetic council fixture. No model inference has been claimed."
                              : "Logical seats may reuse a model. Identity is shown for every seat."}
                          </p>
                          {!round.revealed ? (
                            <Button
                              disabled={busy || round.status !== "committed"}
                              onClick={() =>
                                act(
                                  () =>
                                    api(`/rounds/${round.id}/reveal`, {
                                      expected_revision: step?.revision,
                                    }),
                                  "Four submissions revealed together.",
                                )
                              }
                            >
                              <LockKeyhole size={16} /> Reveal all four
                            </Button>
                          ) : (
                            <Button
                              disabled={
                                busy ||
                                round.status === "reviewing" ||
                                round.review_passes >= 2
                              }
                              onClick={() =>
                                act(
                                  () =>
                                    api(`/rounds/${round.id}/review`, {
                                      expected_revision: step?.revision,
                                    }),
                                  "Cross-review queued.",
                                )
                              }
                            >
                              <MessageSquare size={16} /> Cross-examine
                            </Button>
                          )}
                        </div>
                        {round.reviews?.length > 0 && (
                          <section className="section-block">
                            <h3>Cross-examination</h3>
                            {round.reviews.map((r: Dict) => (
                              <details className="review" key={r.id}>
                                <summary>
                                  <span className="seat-avatar small">
                                    {seatCode[r.seat]}
                                  </span>
                                  <strong>{short(r.seat)}</strong>
                                  <span>
                                    {r.content.challenged_hypothesis_ids.length}{" "}
                                    hypotheses challenged
                                  </span>
                                  <ChevronDown size={15} />
                                </summary>
                                <div className="review-body">
                                  <h4>Missing controls</h4>
                                  <ul>
                                    {r.content.missing_controls.map(
                                      (x: string) => (
                                        <li key={x}>{x}</li>
                                      ),
                                    )}
                                  </ul>
                                  <h4>Trade-offs</h4>
                                  <ul>
                                    {r.content.tradeoffs.map((x: string) => (
                                      <li key={x}>{x}</li>
                                    ))}
                                  </ul>
                                  <h4>Revised recommendation</h4>
                                  <p>{r.content.revised_recommendation}</p>
                                  <h4>Concern responses</h4>
                                  {Object.entries(
                                    r.content.concern_responses,
                                  ).map(([id, text]) => (
                                    <p key={id}>
                                      {concerns.find((c) => c.id === id)?.text}:{" "}
                                      {String(text)}
                                    </p>
                                  ))}
                                </div>
                              </details>
                            ))}
                          </section>
                        )}
                      </>
                    )}
                  </>
                )}
                {view === "Conflict map" && (
                  <section>
                    <span className="eyebrow">
                      Challenges & retained alternatives
                    </span>
                    <h2>Disagreement is research input.</h2>
                    {hypotheses.length > 0 && (
                      <div className="conflict-toolbar">
                        <Button
                          kind="secondary"
                          disabled={step?.status === "approved"}
                          onClick={() => {
                            setArtifact(null);
                            setModal("group");
                          }}
                        >
                          <Plus size={14} /> Group challenges
                        </Button>
                        <Button
                          kind="text"
                          onClick={async () => {
                            const result = await act(() =>
                              api(`/steps/${sid}/related-hypotheses`),
                            );
                            if (result) {
                              setArtifact(result);
                              setModal("artifact");
                            }
                          }}
                        >
                          Find related proposals <Search size={14} />
                        </Button>
                      </div>
                    )}
                    {data.challenge_groups
                      ?.filter((g) => g.step_id === sid)
                      .map((g) => (
                        <div className="challenge-group" key={g.id}>
                          <div>
                            <strong>{g.title}</strong>
                            <small>
                              {g.hypothesis_ids.length} hypotheses ·{" "}
                              {g.review_ids.length} cited reviews · revision{" "}
                              {g.revision}
                            </small>
                          </div>
                          <Button
                            kind="text"
                            disabled={step?.status === "approved"}
                            onClick={() => {
                              setArtifact(g);
                              setModal("group");
                            }}
                          >
                            Edit group <ArrowUpRight size={13} />
                          </Button>
                        </div>
                      ))}
                    {!hypotheses.length ? (
                      <Empty title="Reveal a round first">
                        The conflict map uses actual hypotheses and cited
                        cross-review challenges.
                      </Empty>
                    ) : (
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Hypothesis / author</th>
                              <th>Predicted signature</th>
                              <th>Challenges</th>
                              <th>State</th>
                            </tr>
                          </thead>
                          <tbody>
                            {hypotheses.map((h) => (
                              <tr key={h.id}>
                                <td>
                                  <span className="seat-avatar small">
                                    {seatCode[h.seat]}
                                  </span>
                                  <p>{h.mechanism}</p>
                                </td>
                                <td>{h.prediction}</td>
                                <td>
                                  {data.rounds
                                    .flatMap((r) => r.reviews || [])
                                    .filter((r) =>
                                      r.content.challenged_hypothesis_ids.includes(
                                        h.id,
                                      ),
                                    )
                                    .map((r) => (
                                      <span className="reviewer-tag" key={r.id}>
                                        {seatCode[r.seat]}
                                      </span>
                                    ))}
                                  <small>
                                    Referenced challenges; no inferred agreement
                                    score
                                  </small>
                                </td>
                                <td>
                                  <Badge>{h.status}</Badge>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>
                )}
                {view === "Experiment board" && (
                  <>
                    <div className="section-title">
                      <div>
                        <span className="eyebrow">Bounded capabilities</span>
                        <h2>Choose the discriminating test.</h2>
                      </div>
                      <Button
                        kind="secondary"
                        disabled={!hypotheses.length}
                        onClick={() => setModal("experiment")}
                      >
                        <Plus size={16} /> Plan experiment
                      </Button>
                    </div>
                    <p className="section-intro">
                      Rank by information value, impact, feasibility and cost. A
                      director approval freezes the exact inputs before
                      execution.
                    </p>
                    {!experiments.length ? (
                      <Empty title="No experiments planned">
                        Reveal a council round to turn a hypothesis into a
                        bounded local or API experiment.
                      </Empty>
                    ) : (
                      <div className="experiment-list">
                        {[...experiments]
                          .sort((a, b) => b.priority_score - a.priority_score)
                          .map((e, i) => (
                            <article className="experiment" key={e.id}>
                              <div className="experiment-rank">
                                {String(i + 1).padStart(2, "0")}
                              </div>
                              <div className="experiment-main">
                                <div className="section-title">
                                  <h3>{e.title}</h3>
                                  <Badge
                                    tone={
                                      e.status === "completed" ? "green" : ""
                                    }
                                  >
                                    {short(e.status)}
                                  </Badge>
                                </div>
                                <p>{e.prediction}</p>
                                <div className="experiment-meta">
                                  <span>{e.capability}</span>
                                  <span>
                                    Priority {e.priority_score.toFixed(1)} / 5
                                  </span>
                                  <span>
                                    {e.capability.startsWith("inference.run")
                                      ? "Paid API · credit guard applies"
                                      : "Local execution · $0 inference"}
                                  </span>
                                </div>
                                <details>
                                  <summary>
                                    Plan, controls & kill rule{" "}
                                    <ChevronDown size={14} />
                                  </summary>
                                  <div className="plan-details">
                                    <p>
                                      <strong>Control:</strong> {e.control}
                                    </p>
                                    <p>
                                      <strong>Treatment:</strong> {e.treatment}
                                    </p>
                                    <p>
                                      <strong>Reject if:</strong> {e.kill_rule}
                                    </p>
                                    <p>
                                      <strong>Priority:</strong>{" "}
                                      {e.priority_reason}
                                    </p>
                                    <Json value={e.args} />
                                    <small>Plan hash {e.plan_hash}</small>
                                  </div>
                                </details>
                                <div className="experiment-actions">
                                  {e.status === "planned" && (
                                    <Button
                                      disabled={busy}
                                      onClick={() =>
                                        act(
                                          () =>
                                            api(
                                              `/experiments/${e.id}/approve`,
                                              { expected_revision: e.revision },
                                            ),
                                          "Experiment approved and queued.",
                                        )
                                      }
                                    >
                                      <Play size={15} /> Approve & run
                                    </Button>
                                  )}
                                  {["planned", "queued", "running"].includes(
                                    e.status,
                                  ) && (
                                    <Button
                                      kind="text"
                                      disabled={busy}
                                      onClick={() =>
                                        act(
                                          () =>
                                            api(`/experiments/${e.id}/cancel`, {
                                              expected_revision: e.revision,
                                            }),
                                          "Stopped new dispatch. In-flight charges remain counted.",
                                        )
                                      }
                                    >
                                      Cancel
                                    </Button>
                                  )}
                                  {e.status === "completed" && (
                                    <Button
                                      kind="text"
                                      onClick={() => nav("Evidence")}
                                    >
                                      Inspect evidence <ArrowRight size={15} />
                                    </Button>
                                  )}
                                  {e.error && (
                                    <p className="error-text">{e.error}</p>
                                  )}
                                </div>
                              </div>
                            </article>
                          ))}
                      </div>
                    )}
                  </>
                )}
                {view === "Evidence" && (
                  <>
                    <div className="section-title">
                      <div>
                        <span className="eyebrow">
                          Raw artifacts → deterministic checks
                        </span>
                        <h2>Show what actually happened.</h2>
                      </div>
                      <Badge>{evidences.length} results</Badge>
                    </div>
                    {!evidences.length ? (
                      <Empty title="Evidence will appear here">
                        Approve a registered experiment. Calculated, imported
                        and measured results retain distinct labels.
                      </Empty>
                    ) : (
                      evidences.map((e) => (
                        <article className="evidence-result" key={e.id}>
                          <div className="section-title">
                            <div>
                              <Badge
                                tone={
                                  e.evidence_class === "calculated"
                                    ? "green"
                                    : ""
                                }
                              >
                                {short(e.evidence_class)}
                              </Badge>
                              {e.provider === "openrouter_free" && (
                                <Badge>OpenRouter free</Badge>
                              )}
                              <h3>
                                {
                                  experiments.find(
                                    (x) => x.id === e.experiment_id,
                                  )?.title
                                }
                              </h3>
                            </div>
                            <Button
                              kind="secondary"
                              onClick={() => inspect(e.artifact_id)}
                            >
                              Raw artifact <ArrowUpRight size={14} />
                            </Button>
                          </div>
                          {e.capability === "analysis.calculate_bound" && (
                            <div className="bound-result">
                              <strong>
                                {(e.result.minimum_seconds * 1000).toFixed(2)}
                                <span>ms</span>
                              </strong>
                              <div>
                                <h4>Bandwidth-only lower bound</h4>
                                <p>{e.result.scope}</p>
                                <code>{e.result.method}</code>
                              </div>
                            </div>
                          )}
                          {e.result.cells && <Comparison result={e.result} />}
                          <details>
                            <summary>
                              Full result and provenance{" "}
                              <ChevronDown size={14} />
                            </summary>
                            <Json value={e.result} />
                            <p className="muted-text">
                              SHA-256 {e.sha256} · method {e.method_version} ·
                              step revision {e.step_revision}
                            </p>
                          </details>
                        </article>
                      ))
                    )}
                    <div className="protocol-foot">
                      <ShieldCheck size={16} />
                      <p>
                        Client API observations cannot establish provider
                        hardware behavior. Source-ID checks alone do not certify
                        semantic support.
                      </p>
                    </div>
                  </>
                )}
                {view === "Bottleneck map" && (
                  <>
                    <span className="eyebrow">Mechanisms & transfer</span>
                    <div className="section-title">
                      <h2>Follow the effect to the outcome.</h2>
                      <Button
                        kind="secondary"
                        disabled={!evidences.length}
                        onClick={() => setModal("reframe")}
                      >
                        <Plus size={16} /> Record reframe
                      </Button>
                    </div>
                    <div className="causal-baseline">
                      <div>
                        <span>Intervention</span>
                        <h3>Context / routing</h3>
                        <Badge>Untested until run</Badge>
                      </div>
                      <ArrowRight />
                      <div>
                        <span>Observable surface</span>
                        <h3>API + local tools</h3>
                        <Badge>Evidence required</Badge>
                      </div>
                      <ArrowRight />
                      <div>
                        <span>User outcome</span>
                        <h3>Valid answer cost</h3>
                        <Badge>Quality gated</Badge>
                      </div>
                    </div>
                    {data.causal_nodes
                      ?.filter((n) => n.step_id === sid)
                      .map((n) => (
                        <div className="causal-observation" key={n.id}>
                          <Badge tone="green">{short(n.status)}</Badge>
                          <div>
                            <h4>{n.label}</h4>
                            <p>{n.scope}</p>
                            <small>
                              Artifact {n.artifact_sha256.slice(0, 16)} · linked
                              to its tested hypotheses
                            </small>
                          </div>
                        </div>
                      ))}
                    {!data.reframes.filter((r) => r.step_id === sid).length ? (
                      <Empty title="No causal reframe recorded">
                        Use contrary evidence, hidden costs or a surprising
                        result to change the interpretation and next test.
                      </Empty>
                    ) : (
                      data.reframes
                        .filter((r) => r.step_id === sid)
                        .map((r) => (
                          <article className="reframe-item" key={r.id}>
                            <span className="timeline-dot" />
                            <span className="eyebrow">
                              {new Date(r.created_at).toLocaleString()}
                            </span>
                            <h3>{r.reason}</h3>
                            <p>{r.interpretation}</p>
                            <div className="next-test">
                              <ArrowUpRight size={16} />
                              {r.next_action}
                            </div>
                            <Badge>Inferred interpretation</Badge>
                          </article>
                        ))
                    )}
                    <section className="section-block">
                      <div className="section-title">
                        <h3>Trade-off register</h3>
                        <Button
                          kind="text"
                          onClick={() => setModal("tradeoff")}
                        >
                          <Plus size={15} /> Add trade-off
                        </Button>
                      </div>
                      {data.tradeoffs
                        .filter((t) => t.step_id === sid)
                        .map((t) => (
                          <details className="source" key={t.id}>
                            <summary>
                              <Badge>{short(t.category)}</Badge>
                              {t.title}
                              <ChevronDown size={15} />
                            </summary>
                            <Json value={t} />
                          </details>
                        ))}
                      <p className="muted-text">
                        Synergy, conflict, constraint conversion, hidden-cost
                        removal, adaptive hybrid and new operating point are
                        supported categories. Discovery is not assumed.
                      </p>
                    </section>
                  </>
                )}
                {view === "Decision ledger" && (
                  <>
                    <div className="section-title">
                      <div>
                        <span className="eyebrow">
                          Human authority · evidence gates
                        </span>
                        <h2>Keep the reasons and the dissent.</h2>
                      </div>
                      <Button
                        kind="secondary"
                        disabled={!evidences.length || !round?.reviews_complete}
                        onClick={() => setModal("decision")}
                      >
                        <Plus size={16} /> Draft decision
                      </Button>
                    </div>
                    {!decisions.length ? (
                      <Empty title="No conclusion recorded">
                        Complete a current cross-review and an experiment, then
                        record a bounded finding. Inconclusive and negative
                        results are valid outcomes.
                      </Empty>
                    ) : (
                      decisions.map((d) => (
                        <article className="decision" key={d.id}>
                          <div className="section-title">
                            <Badge
                              tone={d.status === "approved" ? "green" : ""}
                            >
                              {d.status} · {d.verdict}
                            </Badge>
                            <span className="muted-text">
                              {short(d.agreement)}
                            </span>
                          </div>
                          <h2>{d.conclusion}</h2>
                          <div className="gates">
                            {d.gates.map((g: Dict) => (
                              <div key={g.id}>
                                <span className={"gate-icon " + g.status}>
                                  {g.status === "pass" ? (
                                    <Check size={13} />
                                  ) : g.status === "fail" ? (
                                    <X size={13} />
                                  ) : (
                                    <span>?</span>
                                  )}
                                </span>
                                <span>{g.name}</span>
                                <Badge>{g.status}</Badge>
                              </div>
                            ))}
                          </div>
                          <div className="decision-columns">
                            <div>
                              <h4>Reasons</h4>
                              {d.reasons.map((x: string) => (
                                <p key={x}>{x}</p>
                              ))}
                              <h4>Retained dissent</h4>
                              {(d.dissent.length
                                ? d.dissent
                                : ["No dissent recorded."]
                              ).map((x: string) => (
                                <p key={x}>{x}</p>
                              ))}
                            </div>
                            <div>
                              <h4>Assumptions</h4>
                              {d.assumptions.map((x: string) => (
                                <p key={x}>{x}</p>
                              ))}
                              <h4>Reopen when</h4>
                              {d.reopen_triggers.map((x: string) => (
                                <p key={x}>{x}</p>
                              ))}
                            </div>
                          </div>
                          {d.status === "draft" && (
                            <Button
                              disabled={busy}
                              onClick={() =>
                                act(
                                  () =>
                                    api(`/decisions/${d.id}/approve`, {
                                      expected_revision: d.revision,
                                    }),
                                  "Director decision recorded.",
                                )
                              }
                            >
                              <Check size={15} /> Approve {d.verdict} report
                            </Button>
                          )}
                        </article>
                      ))
                    )}
                  </>
                )}
                {view === "Research report" && (
                  <>
                    <div className="section-title">
                      <div>
                        <span className="eyebrow">
                          Portable research record
                        </span>
                        <h2>The finding includes its limits.</h2>
                      </div>
                      <Button onClick={exportPack} disabled={busy}>
                        <Download size={16} /> Download evidence pack
                      </Button>
                    </div>
                    <div className="report-summary">
                      <span className="eyebrow">
                        {mission?.brief.mode === "fixture"
                          ? "Development demonstration"
                          : "Research mission"}
                      </span>
                      <h2>{mission?.brief.title}</h2>
                      <p>{mission?.brief.deliverable}</p>
                      <div className="report-stats">
                        <div>
                          <strong>{data.rounds.length}</strong>
                          <span>Council rounds</span>
                        </div>
                        <div>
                          <strong>{data.evidences.length}</strong>
                          <span>Evidence artifacts</span>
                        </div>
                        <div>
                          <strong>
                            {
                              data.decisions.filter(
                                (d) => d.status === "approved",
                              ).length
                            }
                          </strong>
                          <span>Approved decisions</span>
                        </div>
                      </div>
                    </div>
                    <div className="pack-contents">
                      <h3>Included in every pack</h3>
                      {[
                        "Frozen mission, source packets and protocol hash",
                        "Research map, hypotheses, negative results and trade-offs",
                        "Raw tool/API artifacts and per-attempt budget ledger",
                        "Decisions, dissent, concerns, assumptions and next actions",
                        "Markdown + escaped HTML report, JSON registries and checksums",
                        "Offline verification and deterministic numerical reanalysis",
                      ].map((x) => (
                        <div key={x}>
                          <FileCheck2 size={17} />
                          {x}
                        </div>
                      ))}
                    </div>
                    <section className="section-block">
                      <h3>What this record can support</h3>
                      <p>
                        Claims stay within the recorded task set and evidence
                        classes. Fixtures verify the workflow. Local tools make
                        calculations. Live API results measure client-visible
                        behavior. Confirmation, human quality review and
                        hardware telemetry each need their own evidence.
                      </p>
                    </section>
                    <div className="offline-command">
                      <code>
                        python scripts/verify_pack.py pack.zip
                        <br />
                        python scripts/reproduce.py pack.zip
                      </code>
                      <Badge>Offline · no API key</Badge>
                    </div>
                  </>
                )}
              </main>
              <aside className="inspector">
                <div className="inspector-title">
                  <span className="eyebrow">Director desk</span>
                  <Command size={15} />
                </div>
                <div className="inspector-state">
                  <span className={"state-dot " + step?.status} />
                  <strong>{short(step?.status || "")}</strong>
                  <small>
                    {step?.paused
                      ? "Paused · new dispatch stopped"
                      : "Changes are persisted locally"}
                  </small>
                </div>
                <div className="inspector-controls">
                  <Button
                    kind="secondary"
                    disabled={busy}
                    onClick={() =>
                      stepAction(step?.paused ? "resume" : "pause")
                    }
                  >
                    {step?.paused ? <Play size={14} /> : <Pause size={14} />}{" "}
                    {step?.paused ? "Resume" : "Pause"}
                  </Button>
                  <Button
                    kind="secondary"
                    disabled={busy}
                    onClick={() => stepAction("reopen")}
                  >
                    <RotateCcw size={14} /> Reopen
                  </Button>
                </div>
                <div className="inspector-divider" />
                <div className="section-title">
                  <h4>Director concerns</h4>
                  <span className="count">{openConcerns.length}</span>
                </div>
                <p className="inspector-help">
                  A new concern changes the context revision and blocks stale
                  approval.
                </p>
                <Button kind="outline" onClick={() => setModal("concern")}>
                  <Plus size={14} /> Raise a concern
                </Button>
                {concerns.map((c) => (
                  <div className="concern" key={c.id}>
                    <Badge tone={c.status === "resolved" ? "green" : "muted"}>
                      {c.status}
                    </Badge>
                    <p>{c.text}</p>
                    <div className="acknowledgements">
                      {["hardware", "runtime", "engine", "algorithms"].map(
                        (s) => (
                          <span
                            key={s}
                            title={
                              s +
                              " " +
                              (c.acknowledged_by.includes(s)
                                ? "acknowledged"
                                : "pending")
                            }
                            className={
                              c.acknowledged_by.includes(s) ? "ack" : ""
                            }
                          >
                            {seatCode[s]}
                          </span>
                        ),
                      )}
                    </div>
                    {c.status !== "resolved" &&
                      c.acknowledged_by.length === 4 && (
                        <Button
                          kind="text"
                          onClick={() => {
                            setArtifact(c);
                            setModal("resolve");
                          }}
                        >
                          Record disposition <ArrowRight size={13} />
                        </Button>
                      )}
                    {c.disposition && <small>{c.disposition}</small>}
                  </div>
                ))}
                <div className="inspector-divider" />
                <h4>Activity</h4>
                <div className="event-list">
                  {data.events.slice(0, 6).map((e) => (
                    <div key={e.seq}>
                      <span className="event-dot" />
                      <div>
                        <p>{short(e.type.replace(".", " "))}</p>
                        <small>
                          {new Date(e.created_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}{" "}
                          · #{e.seq}
                        </small>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="scope-note">
                  <Network size={18} />
                  <h4>Observe the boundary.</h4>
                  <p>
                    API and local evidence only. Provider hardware remains
                    unobserved.
                  </p>
                </div>
              </aside>
            </div>
            <footer className="footer">
              <span>ZeroWall / Human-directed research</span>
              <span>Commit independently. Decide with evidence.</span>
              <span>Local build 1.0.0</span>
            </footer>
          </>
        )}
      </div>
      {modal === "new" && (
        <MissionForm
          defaults={boot?.demo_brief}
          liveReady={boot?.live_ready}
          freeReady={boot?.openrouter_free?.ready}
          freeEnabled={boot?.openrouter_free?.enabled}
          busy={busy}
          close={() => setModal("")}
          save={async (b) => {
            const result = await act(() => api("/missions", b));
            if (result) {
              setMid(result.id);
              setSid("");
              setModal("");
              setView("Mission room");
            }
          }}
        />
      )}
      {modal === "missions" && (
        <Dialog title="Your missions" onClose={() => setModal("")}>
          <div className="mission-list">
            {boot?.missions.map((m: Dict) => (
              <button
                key={m.id}
                onClick={() => {
                  setMid(m.id);
                  setSid("");
                  setModal("");
                }}
              >
                <FlaskConical size={19} />
                <span>
                  <strong>{m.brief.title}</strong>
                  <small>
                    {m.brief.mode} · {m.status}
                  </small>
                </span>
                <ArrowRight size={16} />
              </button>
            ))}
          </div>
          <Button onClick={() => setModal("new")}>
            <Plus size={16} /> Create a mission
          </Button>
        </Dialog>
      )}
      {modal === "concern" && (
        <TextForm
          title="Raise a director concern"
          label="What needs to be addressed?"
          description="All four seats must respond in a fresh round. Prior decisions and queued plans become stale."
          busy={busy}
          close={() => setModal("")}
          save={async (text) => {
            const result = await act(() =>
              api(`/steps/${sid}/concerns`, {
                expected_revision: step?.revision,
                text,
              }),
            );
            if (result) setModal("");
          }}
        />
      )}
      {modal === "resolve" && (
        <TextForm
          title="Record concern disposition"
          label="How was this concern addressed?"
          description="Acknowledge any residual uncertainty. This does not override evidence gates."
          busy={busy}
          close={() => setModal("")}
          save={async (disposition) => {
            const c = artifact as Dict;
            const result = await act(() =>
              api(`/concerns/${c.id}/resolve`, {
                expected_revision: c.revision,
                disposition,
              }),
            );
            if (result) setModal("");
          }}
        />
      )}
      {modal === "artifact" && (
        <Dialog title="Artifact inspector" onClose={() => setModal("")}>
          <Json value={artifact} />
        </Dialog>
      )}
      {modal === "experiment" && (
        <ExperimentForm
          mode={mission?.brief.mode}
          provider={mission?.brief.provider}
          busy={busy}
          close={() => setModal("")}
          save={async (input) => {
            const result = await act(() =>
              api(`/steps/${sid}/experiments`, {
                ...input,
                expected_revision: step?.revision,
                hypothesis_ids: hypotheses.map((h) => h.id),
              }),
            );
            if (result) setModal("");
          }}
        />
      )}
      {modal === "decision" && (
        <DecisionForm
          busy={busy}
          close={() => setModal("")}
          save={async (input) => {
            const result = await act(() =>
              api(`/steps/${sid}/decisions`, {
                ...input,
                expected_revision: step?.revision,
                evidence_ids: evidences.map((e) => e.id),
              }),
            );
            if (result) setModal("");
          }}
        />
      )}
      {modal === "reframe" && (
        <ReframeForm
          busy={busy}
          close={() => setModal("")}
          save={async (input) => {
            const result = await act(() =>
              api(`/steps/${sid}/reframes`, {
                ...input,
                expected_revision: step?.revision,
                evidence_ids: evidences.map((e) => e.id),
                hypothesis_states: {},
              }),
            );
            if (result) setModal("");
          }}
        />
      )}
      {modal === "tradeoff" && (
        <TradeoffForm
          busy={busy}
          close={() => setModal("")}
          save={async (input) => {
            const result = await act(() =>
              api(`/steps/${sid}/tradeoffs`, {
                ...input,
                expected_revision: step?.revision,
                evidence_ids: evidences.map((e) => e.id),
              }),
            );
            if (result) setModal("");
          }}
        />
      )}
      {modal === "group" && (
        <GroupForm
          group={artifact as Dict | null}
          hypotheses={hypotheses}
          busy={busy}
          close={() => setModal("")}
          save={async (input) => {
            const reviews =
              data?.rounds
                .filter((r) => r.step_id === sid)
                .flatMap((r) => r.reviews || [])
                .filter((r) =>
                  r.content.challenged_hypothesis_ids.some((id: string) =>
                    input.hypothesis_ids.includes(id),
                  ),
                )
                .map((r) => r.id) || [];
            const result = await act(() =>
              api(`/steps/${sid}/challenge-groups`, {
                ...input,
                review_ids: reviews,
                expected_revision: step?.revision,
              }),
            );
            if (result) setModal("");
          }}
        />
      )}
      {modal === "settings" && (
        <SettingsForm
          boot={boot!}
          busy={busy}
          close={() => setModal("")}
          save={(input) =>
            act(
              () => api("/settings/live-verification", input),
              "Live verification recorded.",
            )
          }
          catalog={() => act(() => api("/settings/catalog", {}))}
          lock={() =>
            act(
              () => api("/settings/live-verification", {}, "DELETE"),
              "Live dispatch locked.",
            )
          }
        />
      )}
    </div>
  );
}

function GroupForm({
  group,
  hypotheses,
  busy,
  save,
  close,
}: {
  group: Dict | null;
  hypotheses: Dict[];
  busy: boolean;
  save: (v: Dict) => void;
  close: () => void;
}) {
  const [title, setTitle] = useState(
      group?.title || "Mechanism and control challenges",
    ),
    [selected, setSelected] = useState<string[]>(group?.hypothesis_ids || []);
  return (
    <Dialog
      title={group ? "Edit challenge group" : "Group related challenges"}
      onClose={close}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save({
            title,
            hypothesis_ids: selected,
            group_id: group?.id || null,
            group_revision: group?.revision || 1,
          });
        }}
      >
        <Field label="Group title">
          <input
            required
            minLength={3}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>
        <p>
          Select actual hypotheses. Their citing reviews are linked
          automatically.
        </p>
        {hypotheses.map((h) => (
          <label className="check-field" key={h.id}>
            <input
              type="checkbox"
              checked={selected.includes(h.id)}
              onChange={(e) =>
                setSelected(
                  e.target.checked
                    ? [...selected, h.id]
                    : selected.filter((id) => id !== h.id),
                )
              }
            />
            <span>
              <strong>{short(h.seat)}</strong>
              <br />
              {h.mechanism}
            </span>
          </label>
        ))}
        <Button disabled={busy || !selected.length}>
          Save challenge group
        </Button>
      </form>
    </Dialog>
  );
}

function Comparison({ result }: { result: Dict }) {
  const cells = Object.entries(result.cells) as [string, Dict][];
  const max = Math.max(
    ...cells.map(([, c]) => c.cost_per_valid_task || 0),
    0.000001,
  );
  return (
    <div className="comparison">
      <h4>Cost per valid task · USD</h4>
      {cells.map(([id, c]) => (
        <div className="bar-row" key={id}>
          <span>{id}</span>
          <div>
            <i
              style={{
                width: ((c.cost_per_valid_task || 0) / max) * 100 + "%",
              }}
            />
          </div>
          <strong>
            {c.cost_per_valid_task === null
              ? "undefined"
              : money(c.cost_per_valid_task)}
          </strong>
          <small>
            {c.valid}/{c.attempted} valid
          </small>
        </div>
      ))}
      <p>
        Integrity: {result.integrity_gate} · {result.independent_tasks}{" "}
        independent tasks · {result.split}
      </p>
      <p className="muted-text">{result.claim_scope}</p>
    </div>
  );
}
function TextForm({
  title,
  label,
  description,
  busy,
  save,
  close,
}: {
  title: string;
  label: string;
  description: string;
  busy: boolean;
  save: (s: string) => void;
  close: () => void;
}) {
  const [text, setText] = useState("");
  return (
    <Dialog title={title} onClose={close}>
      <p>{description}</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save(text);
        }}
      >
        <Field label={label}>
          <textarea
            required
            minLength={10}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
        <Button disabled={busy || text.length < 10}>
          Save director action <ArrowRight size={16} />
        </Button>
      </form>
    </Dialog>
  );
}
function MissionForm({
  defaults,
  liveReady,
  freeReady,
  freeEnabled,
  busy,
  save,
  close,
}: {
  defaults: MissionBrief;
  liveReady: boolean;
  freeReady: boolean;
  freeEnabled: boolean;
  busy: boolean;
  save: (s: Dict) => void;
  close: () => void;
}) {
  const [form, setForm] = useState<Dict>({ ...defaults });
  const set = (k: string, v: unknown) => setForm({ ...form, [k]: v });
  return (
    <Dialog title="Create a research mission" onClose={close}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save(form);
        }}
      >
        <Field label="Mission title">
          <input
            required
            minLength={3}
            value={form.title}
            onChange={(e) => set("title", e.target.value)}
          />
        </Field>
        <Field label="Research question">
          <textarea
            required
            minLength={10}
            value={form.goal}
            onChange={(e) => set("goal", e.target.value)}
          />
        </Field>
        <Field label="Deliverable">
          <textarea
            required
            minLength={5}
            value={form.deliverable}
            onChange={(e) => set("deliverable", e.target.value)}
          />
        </Field>
        <div className="form-grid">
          <Field label="Execution mode">
            <select
              value={
                form.mode === "fixture"
                  ? "fixture"
                  : form.provider || "nebius_token_factory"
              }
              onChange={(e) =>
                setForm({
                  ...form,
                  mode: e.target.value === "fixture" ? "fixture" : "live",
                  provider:
                    e.target.value === "openrouter_free"
                      ? "openrouter_free"
                      : "nebius_token_factory",
                  budget_usd:
                    e.target.value === "openrouter_free"
                      ? 0
                      : form.budget_usd || 1,
                })
              }
            >
              <option value="fixture">
                Fixture council + real local tools
              </option>
              {freeEnabled && (
                <option value="openrouter_free" disabled={!freeReady}>
                  OpenRouter · free only {!freeReady ? "(unavailable)" : ""}
                </option>
              )}
              <option value="nebius_token_factory" disabled={!liveReady}>
                Live Token Factory {!liveReady ? "(locked)" : ""}
              </option>
            </select>
          </Field>
          <Field label="Mission allowance · USD">
            <input
              type="number"
              min={form.provider === "openrouter_free" ? "0" : "0.01"}
              max="24"
              step="0.01"
              required
              value={form.budget_usd}
              disabled={form.provider === "openrouter_free"}
              onChange={(e) => set("budget_usd", Number(e.target.value))}
            />
          </Field>
        </div>
        {form.provider === "openrouter_free" && (
          <p className="form-note">
            Free missions allow 12 attempts and charge $0. The provider and
            model are fixed at freeze; free quotas may interrupt a round.
          </p>
        )}
        <Field label="Constraints · one per line">
          <textarea
            value={form.constraints.join("\n")}
            onChange={(e) =>
              set("constraints", e.target.value.split("\n").filter(Boolean))
            }
          />
        </Field>
        <details className="advanced">
          <summary>
            Source packet, rubric & dependency steps <ChevronDown size={14} />
          </summary>
          <JsonEditor
            value={{
              sources: form.sources,
              rubric: form.rubric,
              steps: form.steps,
              primary_metric: form.primary_metric,
              latency_limit_ms: form.latency_limit_ms,
              material_saving: form.material_saving,
            }}
            change={(value) => setForm({ ...form, ...value })}
          />
        </details>
        <p className="form-note">
          Review the full envelope before freezing. Frozen mission contracts
          cannot be edited.
        </p>
        <Button disabled={busy}>
          Create draft mission <ArrowRight size={16} />
        </Button>
      </form>
    </Dialog>
  );
}
function JsonEditor({
  value,
  change,
}: {
  value: unknown;
  change: (v: Dict) => void;
}) {
  const [raw, setRaw] = useState(JSON.stringify(value, null, 2)),
    [invalid, setInvalid] = useState(false);
  return (
    <div>
      <textarea
        className="json-input"
        aria-label="Structured input JSON"
        rows={10}
        value={raw}
        onChange={(e) => {
          setRaw(e.target.value);
          try {
            change(JSON.parse(e.target.value));
            setInvalid(false);
            e.target.setCustomValidity("");
          } catch {
            setInvalid(true);
            e.target.setCustomValidity(
              "Correct the JSON syntax before saving.",
            );
          }
        }}
      />
      {invalid && (
        <small className="error-text">
          Correct the JSON syntax before saving.
        </small>
      )}
    </div>
  );
}
const presets: Dict = {
  "analysis.calculate_bound": {
    title: "Check the bandwidth-only lower bound",
    args: {
      bytes_moved: 2000000000,
      bandwidth_gbps: 100,
      assumptions: ["Supplied decimal bandwidth; serial transfer; no overlap."],
    },
    control: "Declared transfer size and unit convention",
    treatment: "Evaluate the fixed bandwidth-bound formula",
    prediction: "The supplied values imply a 20 ms lower bound.",
    kill_rule:
      "Reject any arithmetic claim below the calculated lower bound under these assumptions.",
  },
  "analysis.compare_trials": {
    title: "Compare the paired four-cell observations",
    args: { observations: [], material_saving: 0.1, latency_limit_ms: 60000 },
    control: "Matched full-context strong-model baseline C00",
    treatment: "Context packing and routing in C10, C01 and C11",
    prediction: "The combined strategy may reduce cost per valid task.",
    kill_rule: "Reject a required-case regression or an incomplete comparison.",
  },
  "analysis.evaluate_rubric": {
    title: "Record human quality review",
    args: {
      scores: {},
      required: ["mechanism", "falsifiability", "confounders"],
      minimum: 3,
      reviewer: "Human director",
      reviewed_evidence_ids: [],
    },
    control: "Frozen rubric",
    treatment: "Human annotation of actual results",
    prediction: "Each required rubric dimension meets the frozen threshold.",
    kill_rule: "Reject quality preservation if any required dimension fails.",
  },
  "inference.run_benchmark": {
    title: "Run the controlled context and routing pilot",
    args: {
      split: "exploration",
      repeats: 1,
      routing_treatment_approved: false,
    },
    control: "Full facts and fixed first-priority model",
    treatment:
      "Exact-duplicate packing and explicitly approved fast-first routing",
    prediction:
      "Packing and routing may lower complete cost without new validator failures.",
    kill_rule:
      "Reject any new required failure, incomplete schedule or unavailable cost bound.",
  },
  "inference.run_trial": {
    title: "Run a bounded research request",
    args: {
      prompt: "",
      source_ids: [],
      max_output_tokens: 768,
      task_id: "director-trial",
    },
    control: "Frozen mission constraints and supplied sources",
    treatment: "One bounded request to the mission's frozen provider",
    prediction:
      "The answer yields a falsifiable mechanism with source support.",
    kill_rule: "Reject unsupported claims or invalid output.",
  },
  "inference.validate_request": {
    title: "Validate a request without dispatch",
    args: {
      prompt: "Return a concise source-supported research mechanism.",
      source_ids: [],
      max_output_tokens: 768,
      task_id: "request-check",
    },
    control: "Registered request contract",
    treatment: "Local schema and size validation",
    prediction: "The request is within supported local bounds.",
    kill_rule: "Reject malformed or unbounded input.",
  },
  "evidence.import": {
    title: "Import external evidence",
    args: {
      content: "",
      source: "",
      collected_at: new Date().toISOString(),
      method: "Manual source-preserving import",
    },
    control: "Original external content",
    treatment: "Record content, provenance and hash",
    prediction: "The source is inspectable and its scope is explicit.",
    kill_rule: "Reject unsupported provenance or a changed checksum.",
  },
  "evidence.validate": {
    title: "Check cited source identifiers",
    args: {
      source_ids: ["S01"],
      claims: [{ claim: "A declared analytical scenario.", source_id: "S01" }],
    },
    control: "Frozen list of source IDs",
    treatment: "Deterministic identifier coverage check",
    prediction: "Every claim refers to a known source ID.",
    kill_rule: "Reject any unknown source reference.",
  },
};
function ExperimentForm({
  mode,
  provider,
  busy,
  save,
  close,
}: {
  mode: string;
  provider: string;
  busy: boolean;
  save: (v: Dict) => void;
  close: () => void;
}) {
  const [cap, setCap] = useState("analysis.calculate_bound"),
    [p, setP] = useState<Dict>({ ...presets["analysis.calculate_bound"] }),
    [scores, setScores] = useState<Dict>({
      information_value: 3,
      impact: 3,
      feasibility: 4,
      cost_score: 5,
      priority_reason: "Director-defined priority",
    });
  return (
    <Dialog title="Plan a bounded experiment" onClose={close}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save({ ...p, ...scores, capability: cap });
        }}
      >
        <Field label="Capability">
          <select
            value={cap}
            onChange={(e) => {
              setCap(e.target.value);
              setP({ ...presets[e.target.value] });
            }}
          >
            {Object.keys(presets).map((k) => (
              <option
                key={k}
                disabled={
                  (mode !== "live" && k.startsWith("inference.run")) ||
                  (provider === "openrouter_free" &&
                    k === "inference.run_benchmark")
                }
                value={k}
              >
                {k.replaceAll(".", " / ")}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Experiment title">
          <input
            required
            value={p.title}
            onChange={(e) => setP({ ...p, title: e.target.value })}
          />
        </Field>
        <div className="form-grid">
          {["control", "treatment"].map((k) => (
            <Field label={short(k)} key={k}>
              <textarea
                required
                value={p[k]}
                onChange={(e) => setP({ ...p, [k]: e.target.value })}
              />
            </Field>
          ))}
        </div>
        <Field label="Predicted signature">
          <textarea
            required
            value={p.prediction}
            onChange={(e) => setP({ ...p, prediction: e.target.value })}
          />
        </Field>
        <Field label="Rejection rule">
          <textarea
            required
            value={p.kill_rule}
            onChange={(e) => setP({ ...p, kill_rule: e.target.value })}
          />
        </Field>
        <Field label="Exact experiment inputs">
          <JsonEditor
            key={cap}
            value={p.args}
            change={(args) => setP({ ...p, args })}
          />
        </Field>
        {cap === "inference.run_benchmark" && (
          <label className="check-field">
            <input
              type="checkbox"
              checked={p.args.routing_treatment_approved}
              onChange={(e) =>
                setP({
                  ...p,
                  args: {
                    ...p.args,
                    routing_treatment_approved: e.target.checked,
                  },
                })
              }
            />
            I approve this experiment’s fast-first routing departure from the
            default priority.
          </label>
        )}
        <details className="advanced">
          <summary>
            Priority ranking & director reason <ChevronDown size={14} />
          </summary>
          <div className="form-grid">
            {["information_value", "impact", "feasibility", "cost_score"].map(
              (k) => (
                <Field key={k} label={short(k) + " · 1–5"}>
                  <input
                    type="number"
                    min="1"
                    max="5"
                    value={scores[k]}
                    onChange={(e) =>
                      setScores({ ...scores, [k]: Number(e.target.value) })
                    }
                  />
                </Field>
              ),
            )}
          </div>
          <Field label="Priority reason">
            <input
              value={scores.priority_reason}
              onChange={(e) =>
                setScores({ ...scores, priority_reason: e.target.value })
              }
            />
          </Field>
        </details>
        <Button disabled={busy}>
          Save plan for approval <ArrowRight size={16} />
        </Button>
      </form>
    </Dialog>
  );
}
function DecisionForm({
  busy,
  save,
  close,
}: {
  busy: boolean;
  save: (v: Dict) => void;
  close: () => void;
}) {
  const [p, setP] = useState<Dict>({
    conclusion: "",
    verdict: "inconclusive",
    agreement: "unresolved",
    alternatives: "Collect more independent evidence",
    reasons: "",
    dissent: "",
    assumptions: "",
    reopen_triggers: "",
  });
  return (
    <Dialog title="Draft an evidence-backed decision" onClose={close}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const v = { ...p };
          for (const k of [
            "alternatives",
            "reasons",
            "dissent",
            "assumptions",
            "reopen_triggers",
          ])
            v[k] = p[k].split("\n").filter(Boolean);
          save(v);
        }}
      >
        <Field label="Bounded conclusion">
          <textarea
            required
            minLength={10}
            value={p.conclusion}
            onChange={(e) => setP({ ...p, conclusion: e.target.value })}
          />
        </Field>
        <div className="form-grid">
          <Field label="Verdict">
            <select
              value={p.verdict}
              onChange={(e) => setP({ ...p, verdict: e.target.value })}
            >
              {["inconclusive", "rejected", "invalid", "confirmed"].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </Field>
          <Field label="Council agreement">
            <select
              value={p.agreement}
              onChange={(e) => setP({ ...p, agreement: e.target.value })}
            >
              {[
                "unresolved",
                "majority_with_dissent",
                "conditional_consensus",
                "strong_consensus",
              ].map((x) => (
                <option key={x} value={x}>
                  {short(x)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {[
          "reasons",
          "alternatives",
          "dissent",
          "assumptions",
          "reopen_triggers",
        ].map((k) => (
          <Field key={k} label={short(k) + " · one per line"}>
            <textarea
              required={k !== "dissent"}
              value={p[k]}
              onChange={(e) => setP({ ...p, [k]: e.target.value })}
            />
          </Field>
        ))}
        <p className="form-note">
          Confirmation requires every hard gate. An approved inconclusive report
          preserves unknown and failed gates.
        </p>
        <Button disabled={busy}>
          Draft decision <FileCheck2 size={16} />
        </Button>
      </form>
    </Dialog>
  );
}
function ReframeForm({
  busy,
  save,
  close,
}: {
  busy: boolean;
  save: (v: Dict) => void;
  close: () => void;
}) {
  const [p, setP] = useState<Dict>({
    reason: "",
    interpretation: "",
    prediction_comparison: "",
    changed_assumptions: "",
    alternative_explanations: "",
    next_action: "",
  });
  return (
    <Dialog title="Record a research reframe" onClose={close}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save({
            ...p,
            changed_assumptions: p.changed_assumptions
              .split("\n")
              .filter(Boolean),
            alternative_explanations: p.alternative_explanations
              .split("\n")
              .filter(Boolean),
          });
        }}
      >
        {Object.keys(p).map((k) => (
          <Field key={k} label={short(k)}>
            <textarea
              required
              minLength={10}
              value={p[k]}
              onChange={(e) => setP({ ...p, [k]: e.target.value })}
            />
          </Field>
        ))}
        <p className="form-note">
          The interpretation is labeled inferred and linked to the current
          step’s evidence.
        </p>
        <Button disabled={busy}>
          Record reframe <ArrowRight size={16} />
        </Button>
      </form>
    </Dialog>
  );
}
function TradeoffForm({
  busy,
  save,
  close,
}: {
  busy: boolean;
  save: (v: Dict) => void;
  close: () => void;
}) {
  const [p, setP] = useState<Dict>({
    title: "",
    category: "conflict",
    expected_pros: "",
    expected_cons: "",
    observed_pros: "",
    observed_cons: "",
    hidden_costs: "",
    mitigations: "",
    operating_region: "",
    complexity: "",
    rejection_rule: "",
  });
  return (
    <Dialog title="Add a trade-off card" onClose={close}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const v = { ...p };
          for (const k of [
            "expected_pros",
            "expected_cons",
            "observed_pros",
            "observed_cons",
            "hidden_costs",
            "mitigations",
          ])
            v[k] = p[k].split("\n").filter(Boolean);
          save(v);
        }}
      >
        <Field label="Category">
          <select
            value={p.category}
            onChange={(e) => setP({ ...p, category: e.target.value })}
          >
            {[
              "synergy",
              "conflict",
              "constraint_conversion",
              "hidden_cost_removal",
              "adaptive_hybrid",
              "new_operating_point",
            ].map((k) => (
              <option key={k} value={k}>
                {short(k)}
              </option>
            ))}
          </select>
        </Field>
        {Object.keys(p)
          .filter((k) => k !== "category")
          .map((k) => (
            <Field key={k} label={short(k)}>
              <textarea
                required={!k.startsWith("observed")}
                value={p[k]}
                onChange={(e) => setP({ ...p, [k]: e.target.value })}
              />
            </Field>
          ))}
        <Button disabled={busy}>Save trade-off</Button>
      </form>
    </Dialog>
  );
}
function SettingsForm({
  boot,
  busy,
  save,
  catalog,
  lock,
  close,
}: {
  boot: Dict;
  busy: boolean;
  save: (v: Dict) => Promise<any>;
  catalog: () => Promise<any>;
  lock: () => void;
  close: () => void;
}) {
  const [result, setResult] = useState<Dict | null>(null);
  const [raw, setRaw] = useState<Dict>({
    existing_credit_usd: 25,
    operational_cap_usd: 24,
    credit_only_confirmed: false,
    automatic_payments_disabled: false,
    billing_evidence: "",
    catalog_model_ids: [],
    prices: {},
    price_source: "",
    token_bound_verified: false,
    token_bound_evidence: "",
    all_billing_categories_bounded: false,
    additional_billed_output_tokens: 0,
    billed_input_multiplier: 2,
    expires_in_hours: 24,
    acknowledgement:
      "Use existing credit only; authorize no additional payment.",
  });
  return (
    <Dialog title="Provider & spending controls" onClose={close}>
      <div className="settings-overview">
        <ShieldCheck size={24} />
        <div>
          <strong>$24 total limit. Existing credit only. $0 additional payment.</strong>
          <p>
            The app’s ledger cannot control other applications or provider card
            charging. Record actual account evidence before enabling Token
            Factory dispatch.
          </p>
        </div>
      </div>
      <div className="section-title">
        <h3>OpenRouter free testing</h3>
        <Badge tone={boot.openrouter_free?.ready ? "green" : "muted"}>
          {boot.openrouter_free?.ready ? "Available" : "Unavailable"}
        </Badge>
      </div>
      <p>
        <code>{boot.openrouter_free?.model}</code>
      </p>
      <p className="muted-text">
        API key {boot.openrouter_free?.key_present ? "present" : "missing"}.
        Choose free execution when creating a mission. Every dispatch verifies
        zero pricing; 12 attempts per mission, 50 per UTC day in this workspace.
        Provider quotas may be lower.
      </p>
      <div className="inspector-divider" />
      <div className="section-title">
        <h3>Token Factory model priority</h3>
        <Badge tone={boot.key_present ? "green" : "muted"}>
          API key {boot.key_present ? "present" : "missing"}
        </Badge>
      </div>
      <ol className="model-order">
        {boot.models.map((m: string) => (
          <li key={m}>
            <code>{m}</code>
          </li>
        ))}
      </ol>
      <p className="muted-text">
        Only the configured models are enabled. Unlisted models are rejected. Text
        requests only; non-streaming TTFT stays unknown.
      </p>
      <Button
        kind="secondary"
        onClick={async () => setResult(await catalog())}
        disabled={busy}
      >
        Check account model catalog <Search size={15} />
      </Button>
      {result && <Json value={result} />}
      <div className="inspector-divider" />
      <h3>Live verification record</h3>
      {boot.live_verification?.authorization_mode === 'existing_credit_testing' && <p>Existing-credit testing is enabled within the $24 aggregate cap. Card-charging settings remain unverified; no payment setting was changed.</p>}
      <p>
        Complete only with verified billing settings, current prices and a
        conservative bound covering every billed token category. Unknown
        prerequisites keep live requests locked.
      </p>
      <JsonEditor value={raw} change={setRaw} />
      <div className="dialog-actions">
        <Button
          disabled={busy}
          onClick={async () => {
            if (
              !document
                .querySelector<HTMLTextAreaElement>(".dialog .json-input")
                ?.reportValidity()
            )
              return;
            const r = await save(raw);
            if (r) close();
          }}
        >
          Record verification
        </Button>
        <Button kind="secondary" disabled={busy} onClick={lock}>
          <LockKeyhole size={15} /> Lock Token Factory
        </Button>
      </div>
      <p className="form-note">
        Verification expires after 24 hours by default. A request that exceeds
        its asserted bound records the charge and locks subsequent calls.
      </p>
    </Dialog>
  );
}

function App() {
  return new URLSearchParams(location.search).get("workspace") ===
    "research" ? (
    <ResearchApp />
  ) : (
    <CouncilChat />
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
