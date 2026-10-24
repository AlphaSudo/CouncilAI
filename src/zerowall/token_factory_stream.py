"""Collect public SSE output and final measured usage without retaining reasoning text."""

import json
import time

import httpx

from .db import now


def complete(
    client, url, headers, request, capture, cancelled, *, progress=None, started=None
):
    started = time.perf_counter() if started is None else started
    stats = capture["stream_progress"] = {
        "phase": "waiting_for_provider",
        "events": 0,
        "reasoning_chunks": 0,
        "answer_chunks": 0,
        "answer_characters": 0,
    }
    last_publish = -2.0

    def publish(force=False):
        nonlocal last_publish
        clock = time.perf_counter()
        if progress and (force or clock - last_publish >= 2):
            progress(dict(stats))
            last_publish = clock

    with client.stream("POST", url, headers=headers, json=request) as response:
        capture["http_status"] = response.status_code
        stats["headers_received_ms"] = (time.perf_counter() - started) * 1000
        publish(force=True)
        if (
            "text/event-stream" not in response.headers.get("content-type", "")
            or not response.is_success
        ):
            response.read()
            return response
        public = {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }
            ]
        }
        capture["response"] = public
        parts = capture["content_parts"] = []
        last_cancel_check = 0
        for line in response.iter_lines():
            if time.monotonic() - last_cancel_check >= 0.5:
                last_cancel_check = time.monotonic()
                if cancelled():
                    capture["interruption_reason"] = "cancelled_by_director"
                    raise httpx.ReadError("Streaming request cancelled after dispatch")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError as error:
                raise httpx.RemoteProtocolError(
                    "Invalid completion stream event"
                ) from error
            if not isinstance(chunk, dict) or chunk.get("error"):
                raise httpx.RemoteProtocolError("Completion stream returned an error")
            elapsed_ms = (time.perf_counter() - started) * 1000
            stats.setdefault("first_event_ms", elapsed_ms)
            stats["events"] += 1
            stats["last_activity_at"] = now()
            if stats["phase"] == "waiting_for_provider":
                stats["phase"] = "provider_streaming"
            for key in ("id", "model", "created", "object"):
                if key in chunk:
                    if key == "model" and public.get(key) and public[key] != chunk[key]:
                        raise httpx.RemoteProtocolError(
                            "Completion stream changed model identity"
                        )
                    public[key] = chunk[key]
            if isinstance(chunk.get("usage"), dict):
                public["usage"] = chunk["usage"]
            choices = chunk.get("choices") or []
            for choice in choices:
                if choice.get("index", 0) != 0:
                    continue
                delta = choice.get("delta") or {}
                # Observe activity only. Never retain private reasoning text or
                # estimate token usage from the number/size of these chunks.
                if any(
                    isinstance(delta.get(key), str) and delta[key]
                    for key in ("reasoning_content", "reasoning")
                ):
                    stats["reasoning_chunks"] += 1
                    if not stats["answer_chunks"]:
                        stats["phase"] = "reasoning"
                content = delta.get("content")
                if isinstance(content, str):
                    parts.append(content)
                    if content:
                        stats.setdefault("first_answer_ms", elapsed_ms)
                        stats["answer_chunks"] += 1
                        stats["answer_characters"] += len(content)
                        stats["phase"] = "answering"
                if choice.get("finish_reason"):
                    public["choices"][0]["finish_reason"] = choice["finish_reason"]
            publish()
            if public["choices"][0]["finish_reason"] and isinstance(
                public.get("usage"), dict
            ):
                break
        if not public["choices"][0]["finish_reason"]:
            raise httpx.RemoteProtocolError(
                "Completion stream ended without a finish reason"
            )
        public["choices"][0]["message"]["content"] = "".join(parts)
        stats["phase"] = "finished"
        publish(force=True)
        # iter_lines has already decoded the upstream transfer. These headers
        # describe its wire bytes, not the reconstructed JSON body.
        headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower()
            not in {
                "content-encoding",
                "content-length",
                "transfer-encoding",
                "content-type",
            }
        }
        return httpx.Response(response.status_code, headers=headers, json=public)
