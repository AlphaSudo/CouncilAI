import asyncio
import json

from zerowall.cloud_responses import CloudJSONResponse, streamed_download


def deliver(response):
    messages = []

    async def send(message):
        messages.append(message)

    asyncio.run(response({"type": "http", "asgi": {"spec_version": "2.4"}}, None, send))
    headers = dict(messages[0]["headers"])
    chunks = [message.get("body", b"") for message in messages[1:]]
    return headers, chunks


def test_large_json_history_streams_all_bytes_without_content_length():
    text = "A complete public answer. " * 240000
    headers, chunks = deliver(CloudJSONResponse({"answer": text}))
    assert b"content-length" not in headers
    assert len(chunks) > 2
    assert json.loads(b"".join(chunks))["answer"] == text


def test_small_json_keeps_normal_response_semantics():
    headers, chunks = deliver(CloudJSONResponse({"ok": True}))
    assert int(headers[b"content-length"]) == len(b"".join(chunks))


def test_export_stream_preserves_zip_bytes(tmp_path):
    data = b"zip-fixture" * 500000
    path = tmp_path / "export.zip"
    path.write_bytes(data)
    headers, chunks = deliver(streamed_download(path, "zerowall-export.zip"))
    assert headers[b"content-type"] == b"application/zip"
    assert b"content-length" not in headers
    assert b"".join(chunks) == data
