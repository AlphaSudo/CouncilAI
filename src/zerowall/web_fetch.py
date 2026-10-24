"""Public URL fetching with address pinning, verified TLS and hard byte bounds."""

import http.client
import ipaddress
import queue
import re
import socket
import ssl
import threading
import time
import zlib
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from .db import DomainError

FETCH_SLOTS = threading.BoundedSemaphore(2)
MAX_BYTES = 2 * 1024 * 1024


def canonical_url(url):
    if not isinstance(url, str) or len(url) > 2000 or any(ord(c) < 33 for c in url):
        raise DomainError("Invalid public URL", 422)
    value = urlsplit(url)
    if any(
        re.fullmatch(
            r"(?i)(api[_-]?key|access[_-]?token|auth(?:orization)?|password|secret|token)",
            key,
        )
        and val
        for key, val in parse_qsl(value.query)
    ):
        raise DomainError("Credential-bearing public URLs are blocked", 422)
    try:
        port = value.port
    except ValueError:
        raise DomainError("Invalid URL port", 422) from None
    if (
        value.scheme.lower() not in ("http", "https")
        or not value.hostname
        or value.username is not None
        or value.password is not None
        or port not in (None, 80, 443)
    ):
        raise DomainError(
            "Only credential-free public HTTP(S) URLs on standard ports are allowed",
            422,
        )
    host = value.hostname.encode("idna").decode().lower().rstrip(".")
    rendered = "[" + host + "]" if ":" in host else host
    if port and port != (443 if value.scheme.lower() == "https" else 80):
        rendered += ":" + str(port)
    return urlunsplit(
        (value.scheme.lower(), rendered, value.path or "/", value.query, "")
    )


def public_addresses(host, port, timeout):
    result = queue.Queue(maxsize=1)

    def resolve():
        try:
            result.put(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
        except OSError as error:
            result.put(error)

    threading.Thread(target=resolve, daemon=True).start()
    try:
        values = result.get(timeout=max(0.01, timeout))
    except queue.Empty:
        raise DomainError("Public URL DNS deadline exceeded", 504) from None
    if isinstance(values, Exception):
        raise DomainError("Public URL DNS resolution failed", 422)
    addresses = sorted({r[4][0] for r in values})
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise DomainError(
            "Private, local, reserved and metadata destinations are blocked", 422
        )
    return addresses


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, address, timeout, tls):
        super().__init__(host, port, timeout=timeout)
        self.address, self.tls = address, tls

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        if self.tls:
            self.sock = ssl.create_default_context().wrap_socket(
                self.sock, server_hostname=self.host
            )


def fetch(url, *, validators=None, cancelled=lambda: False):
    deadline = time.monotonic() + 20
    if not FETCH_SLOTS.acquire(timeout=20):
        raise DomainError("Public fetch capacity is busy", 429)
    try:
        chain, raw_count, current = [], 0, canonical_url(url)
        for hop in range(4):
            if cancelled() or time.monotonic() >= deadline:
                raise DomainError("Public fetch stopped or its deadline expired", 409)
            value = urlsplit(current)
            port = value.port or (443 if value.scheme == "https" else 80)
            addresses = public_addresses(
                value.hostname, port, deadline - time.monotonic()
            )
            connection = PinnedHTTP(
                value.hostname,
                port,
                addresses[0],
                max(0.1, deadline - time.monotonic()),
                value.scheme == "https",
            )
            try:
                headers = {
                    "User-Agent": "CouncilResearch/1.05",
                    "Accept-Encoding": "gzip",
                    "Accept": "text/plain,text/html,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }
                headers.update(validators or {})
                connection.request(
                    "GET",
                    value.path + ("?" + value.query if value.query else ""),
                    headers=headers,
                )
                wire_socket = getattr(connection, "sock", None)
                response = connection.getresponse()
                if (
                    sum(
                        len(k) + len(v)
                        for k, v in getattr(response, "getheaders", list)()
                    )
                    > 65536
                ):
                    raise DomainError("Public source header limit exceeded", 413)
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader("Location")
                    if not location or hop == 3:
                        raise DomainError("Public URL redirect limit reached", 422)
                    chain.append(current)
                    current = canonical_url(urljoin(current, location))
                    validators = None
                    continue
                metadata = {
                    "final_url": current,
                    "redirect_chain": chain,
                    "etag": response.getheader("ETag"),
                    "last_modified": response.getheader("Last-Modified"),
                    "http_status": response.status,
                    "robots": response.getheader("X-Robots-Tag"),
                    "network_requests": hop + 1,
                }
                if response.status == 304:
                    return {"not_modified": True, "metadata": metadata, "raw_bytes": 0}
                if response.status != 200:
                    raise DomainError(
                        f"Public source returned HTTP {response.status}; access was not bypassed",
                        422,
                    )
                mime = (
                    response.getheader("Content-Type", "").split(";")[0].strip().lower()
                )
                if mime not in (
                    "text/plain",
                    "text/markdown",
                    "text/html",
                    "application/xhtml+xml",
                    "application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ):
                    raise DomainError("Unsupported public source MIME type", 422)
                encoding = response.getheader("Content-Encoding", "identity").lower()
                if encoding not in ("gzip", "identity"):
                    raise DomainError("Unsupported content encoding", 422)
                decoder = (
                    zlib.decompressobj(16 + zlib.MAX_WBITS)
                    if encoding == "gzip"
                    else None
                )
                content = bytearray()
                while True:
                    if cancelled() or time.monotonic() >= deadline:
                        raise DomainError("Public source deadline exceeded", 504)
                    if wire_socket is not None:
                        wire_socket.settimeout(max(0.01, deadline - time.monotonic()))
                    block = response.read1(16384)
                    if not block:
                        break
                    raw_count += len(block)
                    if raw_count > MAX_BYTES:
                        raise DomainError("Compressed/source byte limit exceeded", 413)
                    content.extend(
                        decoder.decompress(block, MAX_BYTES - len(content) + 1)
                        if decoder
                        else block
                    )
                    if len(content) > MAX_BYTES or (
                        decoder and decoder.unconsumed_tail
                    ):
                        raise DomainError("Decoded source byte limit exceeded", 413)
                if decoder and not decoder.eof:
                    raise DomainError("Incomplete compressed source body", 422)
                return {
                    "raw": bytes(content),
                    "mime": mime,
                    "metadata": metadata,
                    "raw_bytes": raw_count,
                    "not_modified": False,
                }
            finally:
                connection.close()
        raise DomainError("Redirect limit exceeded", 422)
    finally:
        FETCH_SLOTS.release()
