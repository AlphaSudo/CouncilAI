import { useEffect, useState } from "react";
import type { Dict } from "./types";

function useRequestClock() {
  const [clock, setClock] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return clock;
}

export function RetryCountdown({ notBefore }: { notBefore: string }) {
  const clock = useRequestClock();
  return (
    <>{Math.max(0, Math.ceil((Date.parse(notBefore) - clock) / 1000)) || 0}</>
  );
}

export const secondsLabel = (value: number | null | undefined) =>
  value == null
    ? "Unavailable"
    : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} s`;

const rate = (value: number | null | undefined) =>
  value == null
    ? "Unavailable"
    : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} tokens/s`;

export function ReplyTimingSummary({ attempts }: { attempts?: Dict[] }) {
  const timed =
    attempts?.filter((a) => a.timing?.elapsed_seconds != null) || [];
  if (!timed.length) return null;
  const elapsed = timed.reduce((sum, a) => sum + a.timing.elapsed_seconds, 0);
  return (
    <span className="response-timing-summary">
      {secondsLabel(elapsed)}
      {attempts!.length > 1 ? " across attempts" : " request time"}
      {timed.length !== attempts!.length ? " (partial timing)" : ""}
      {attempts!.length === 1 &&
        timed[0].timing.output_tokens_per_second != null &&
        ` · ${rate(timed[0].timing.output_tokens_per_second)} including reasoning`}
    </span>
  );
}

export function AttemptTiming({ attempt }: { attempt: Dict }) {
  const timing = attempt.timing;
  if (!timing) return null;
  return (
    <div className="response-timing-detail">
      <dl className="usage-money" aria-label="Response timing">
        <div>
          <dt>Request time</dt>
          <dd>{secondsLabel(timing.elapsed_seconds)}</dd>
        </div>
        <div>
          <dt>First stream event</dt>
          <dd>{secondsLabel(timing.first_stream_seconds)}</dd>
        </div>
        <div>
          <dt>First answer text</dt>
          <dd>{secondsLabel(timing.first_answer_seconds)}</dd>
        </div>
        <div>
          <dt>Output rate, including reasoning</dt>
          <dd>{rate(timing.output_tokens_per_second)}</dd>
        </div>
        <div>
          <dt>Visible answer rate</dt>
          <dd>{rate(timing.visible_tokens_per_second)}</dd>
        </div>
      </dl>
      <p className="research-muted">
        Rates use reported tokens divided by total request time, including
        provider waiting and reasoning. They are not engine-only generation
        speed.
        {timing.output_tokens_per_second == null &&
          " TPS is unavailable without final token usage and request duration."}
        {!timing.stream &&
          " Stream activity was not recorded for this older attempt."}
        {timing.interruption_reason === "cancelled_by_director" &&
          " You paused or stopped this request; provider usage may remain unknown."}
        {timing.interruption_reason === "read_timeout_before_headers" &&
          " The provider sent no HTTP response before the read timeout. No answer or final token usage was received."}
        {timing.interruption_reason === "read_timeout_during_body" &&
          " The provider response stopped delivering data and reached the read timeout."}
        {timing.read_idle_timeout_seconds != null &&
          ` Silent-response timeout: ${timing.read_idle_timeout_seconds} s. This is an inactivity limit, not a total generation-time cap.`}
      </p>
    </div>
  );
}

export function ActiveResponseTiming({
  request,
  explain,
}: {
  request?: Dict | null;
  explain: boolean;
}) {
  const clock = useRequestClock();
  if (!request?.sent_at) return null;
  const started = Date.parse(request.sent_at);
  if (!Number.isFinite(started)) return null;
  const elapsed = Math.max(0, Math.floor((clock - started) / 1000));
  const stream = request.stream_progress;
  const status =
    stream?.phase === "reasoning"
      ? "Reasoning activity received; no answer text yet"
      : stream?.phase === "answering"
        ? "Receiving answer text"
        : stream?.phase === "finished"
          ? "Saving completed response"
          : stream?.phase === "provider_streaming"
            ? "Provider stream open; no answer text yet"
            : "Waiting for provider output";
  const lastActivity = stream?.last_activity_at
    ? Date.parse(stream.last_activity_at)
    : null;
  const quiet =
    lastActivity != null && Number.isFinite(lastActivity)
      ? Math.max(0, Math.floor((clock - lastActivity) / 1000))
      : null;
  return (
    <span className="active-response-timing">
      <span className="response-elapsed">{elapsed} s elapsed</span>
      <span>{status}</span>
      {elapsed >= 60 && stream?.phase === "reasoning" && (
        <span className="reasoning-delay">
          Still waiting for public answer text. The reasoning target is
          advisory; a low-effort request can exceed it.
        </span>
      )}
      {quiet != null && quiet >= 15 && (
        <span>No stream activity for {quiet} s</span>
      )}
      {explain && (
        <small>
          {stream?.first_answer_ms != null &&
            `First answer at ${secondsLabel(stream.first_answer_ms / 1000)}. `}
          {stream?.reasoning_chunks > 0 &&
            `${stream.reasoning_chunks.toLocaleString()} reasoning chunks observed. `}
          {stream?.answer_characters > 0 &&
            `${stream.answer_characters.toLocaleString()} answer characters received. `}
          TPS waits for final provider token usage. Chunks are not tokens.
          {stream?.phase === "waiting_for_provider" &&
            " Provider queue time cannot be separated from prefill or reasoning."}
        </small>
      )}
    </span>
  );
}
