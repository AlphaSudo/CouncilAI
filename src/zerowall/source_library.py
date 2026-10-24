"""Chat-scoped immutable source versions, local index and exact read receipts."""

import hashlib
import os
import re
import sqlite3
import uuid

from .db import DomainError, digest, now, uid
from .source_parsers import extract


class SourceLibrary:
    def __init__(self, research):
        self.research, self.store = research, research.store
        self.files = research.artifacts.files
        self.root = research.settings.data / "source-blobs"
        self.root.mkdir(exist_ok=True)
        self.maximum = 100 * 1024 * 1024
        if self.store.remote:
            self.fts = True
            return
        with self.store.tx() as c:
            try:
                c.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS source_fts USING fts5(chat_id UNINDEXED,version_id UNINDEXED,chunk_id UNINDEXED,title,text)"
                )
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False

    def check_secret(self, text):
        if self.research.artifacts.redact(text) != text or re.search(
            r"(?i)(?:tvly-(?:dev-)?|sk-or-v1-|nvapi-|gsk_)[A-Za-z0-9_-]{16,}", text
        ):
            raise DomainError(
                "Source or query contains a credential; remove it before research", 422
            )

    def blob(self, content):
        sha = hashlib.sha256(content).hexdigest()
        if self.files:
            self.files.write('source-blobs/' + sha, content)
            return sha
        path = self.root / sha
        if not path.exists():
            temporary = self.root / (sha + "." + uuid.uuid4().hex + ".tmp")
            try:
                with temporary.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        return sha

    def read_blob(self, sha):
        if not re.fullmatch("[0-9a-f]{64}", sha):
            raise DomainError("Invalid source hash", 422)
        if self.files:
            return self.files.read('source-blobs/' + sha, sha)
        try:
            data = (self.root / sha).read_bytes()
        except FileNotFoundError:
            raise DomainError(
                "Source bytes missing; offline replay is incomplete", 422
            ) from None
        if hashlib.sha256(data).hexdigest() != sha:
            raise DomainError("Source integrity check failed", 422)
        return data

    def ingest(self, chat, raw, *, title, mime="text/plain", url=None, metadata=None):
        self.check_secret(raw.decode("utf-8", errors="ignore"))
        if (
            not title
            or len(title) > 240
            or re.search(
                r"(^|[/\\])(?:\.env(?:\..*)?|credentials.*|director-token|id_rsa)$",
                title,
                re.IGNORECASE,
            )
        ):
            raise DomainError("Invalid or secret-file source name", 422)
        try:
            parsed = extract(raw, mime)
        except (ValueError, OSError) as error:
            raise DomainError(str(error), 422) from None
        self.check_secret(parsed["text"])
        self.check_secret(title)
        identity = url or title
        source_origin = (metadata or {}).get(
            "origin", "public_url" if url else "user_supplied"
        )
        sid = "source_" + digest([chat["id"], identity])[:24]
        vid = (
            "version_"
            + digest(
                [
                    chat["id"],
                    identity,
                    hashlib.sha256(raw).hexdigest(),
                    parsed["parser"],
                    source_origin,
                    mime,
                ]
            )[:24]
        )
        # One authority serializes storage admission and manifest publication.
        with self.store.tx() as c:
            self.store.get(c, chat["id"], "chat")
            if c.execute("SELECT 1 FROM records WHERE id=?", (vid,)).fetchone():
                source = self.store.get(c, sid, "source")
                current = self.store.get(c, source["current_version_id"], "source_version")
                if source_origin != "search_snippet" or current["origin"] == "search_snippet":
                    source["current_version_id"] = vid
                source["removed"] = False
                self.store.put(c, "source", source)
                return self.store.get(c, vid, "source_version")
            current_size = sum(p['size'] for p in self.files.inventory('source-blobs')) if self.files else sum(
                p.stat().st_size for p in self.root.iterdir() if p.is_file()
            )
            if current_size + len(raw) + len(parsed["text"].encode()) > self.maximum:
                raise DomainError(
                    "Source library storage limit reached; saved sources remain available",
                    413,
                )
            raw_sha, text_sha = self.blob(raw), self.blob(parsed["text"].encode())
            version = {
                "id": vid,
                "mission_id": chat["mission_id"],
                "chat_id": chat["id"],
                "source_id": sid,
                "title": title,
                "url": url,
                "raw_sha256": raw_sha,
                "text_sha256": text_sha,
                "mime": mime,
                "parser": parsed["parser"],
                "coverage": "search_snippet_only"
                if source_origin == "search_snippet"
                else "provider_extracted_text" if (metadata or {}).get("retrieval_method") == "tavily_extract_basic" else parsed["coverage"],
                "limitations": parsed["limitations"]
                + (
                    ["Search-engine snippet only; original webpage not read"]
                    if source_origin == "search_snippet"
                    else ["Provider-extracted page content; complete original page coverage is not independently verified"] if (metadata or {}).get("retrieval_method") == "tavily_extract_basic" else []
                ),
                "truncated": parsed["truncated"],
                "metadata": metadata or {},
                "retrieved_at": now(),
                "text_bytes": len(parsed["text"].encode()),
                "export_policy": "include",
                "origin": source_origin,
            }
            self.store.put(c, "source_version", version)
            previous_vid = (
                self.store.get(c, sid, "source")["current_version_id"]
                if c.execute("SELECT 1 FROM records WHERE id=?", (sid,)).fetchone()
                else None
            )
            current_vid = vid
            if (
                source_origin == "search_snippet"
                and c.execute("SELECT 1 FROM records WHERE id=?", (sid,)).fetchone()
            ):
                prior_source = self.store.get(c, sid, "source")
                prior_version = self.store.get(
                    c, prior_source["current_version_id"], "source_version"
                )
                if prior_version["origin"] != "search_snippet":
                    current_vid = prior_version["id"]
            self.store.put(
                c,
                "source",
                {
                    "id": sid,
                    "mission_id": chat["mission_id"],
                    "chat_id": chat["id"],
                    "title": title,
                    "url": url,
                    "current_version_id": current_vid,
                },
            )
            query_variant = (
                source_origin == "search_snippet"
                and (metadata or {}).get("search_policy") == "per-reply-search/1"
                and previous_vid
                and (prior := self.store.get(c, previous_vid, "source_version"))["origin"] == "search_snippet"
                and prior.get("metadata", {}).get("query") != (metadata or {}).get("query")
            )
            if previous_vid and previous_vid != current_vid and not query_variant:
                self.changed(c, chat, sid, previous_vid, current_vid)
            lines = parsed["text"].splitlines(keepends=True)
            start, block, size = 1, [], 0
            heading, block_heading = "", ""
            for number, line in enumerate(lines + [""], 1):
                if block and (
                    size + len(line.encode()) > 4096 or number == len(lines) + 1
                ):
                    self._chunk(
                        c, version, start, number - 1, "".join(block), block_heading
                    )
                    start, block, size = number, [], 0
                if line:
                    match = re.match(r"^#{1,6}\s+(.+)", line)
                    if match:
                        heading = match.group(1)
                    if not block:
                        block_heading = heading
                    block.append(line)
                    size += len(line.encode())
            self.store.event(
                c,
                chat["mission_id"],
                "library.source_added",
                {"version_id": vid, "source_id": sid, "bytes": version["text_bytes"]},
            )
            return version

    def _chunk(self, c, version, start, end, text, heading=""):
        chunk = {
            "id": "chunk_" + digest([version["id"], start, end, text])[:24],
            "mission_id": version["mission_id"],
            "chat_id": version["chat_id"],
            "version_id": version["id"],
            "line_start": start,
            "line_end": end,
            "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "chunker": "lines/1",
            "heading": heading,
        }
        self.store.put(c, "source_chunk", chunk)
        if self.fts:
            c.execute(
                "INSERT INTO source_fts VALUES(?,?,?,?,?)",
                (
                    version["chat_id"],
                    version["id"],
                    chunk["id"],
                    version["title"] + " " + heading,
                    text,
                ),
            )

    def version(self, c, chat, vid):
        item = self.store.get(c, vid, "source_version")
        if item["chat_id"] != chat["id"]:
            raise DomainError("Source is outside this conversation", 404)
        if item.get("content_forgotten"):
            raise DomainError(
                "Source content was explicitly removed; historical replay is incomplete",
                410,
            )
        return item

    def snapshot(self, c, chat, stage, version_ids=None):
        ids = (
            version_ids
            if version_ids is not None
            else [
                s["current_version_id"]
                for s in self.store.list(c, "source", chat["mission_id"])
                if not s.get("removed")
            ]
        )
        if version_ids is None:
            active_sources = {
                s["id"]
                for s in self.store.list(c, "source", chat["mission_id"])
                if not s.get("removed")
            }
            snippets = []
            for version in self.store.list(c, "source_version", chat["mission_id"]):
                if (
                    version["source_id"] in active_sources
                    and version.get("origin") == "search_snippet"
                    and not version.get("content_forgotten")
                ):
                    snippets.append(version["id"])
            ids = list(ids) + snippets
        for vid in ids:
            self.version(c, chat, vid)
        value = {"chat_id": chat["id"], "stage": stage, "version_ids": sorted(set(ids))}
        identifier = "snapshot_" + digest(value)[:24]
        if not c.execute("SELECT 1 FROM records WHERE id=?", (identifier,)).fetchone():
            self.store.put(
                c,
                "library_snapshot",
                {"id": identifier, "mission_id": chat["mission_id"], **value},
            )
        return self.store.get(c, identifier, "library_snapshot")

    def allowed(self, c, chat, snapshot_id):
        if not snapshot_id:
            return {
                s["id"]
                for s in self.store.list(c, "source_version", chat["mission_id"])
                if not s.get("content_forgotten")
            }
        snap = self.store.get(c, snapshot_id, "library_snapshot")
        if snap["chat_id"] != chat["id"]:
            raise DomainError("Snapshot is outside this conversation", 404)
        return set(snap["version_ids"])

    def search(self, c, chat, query, *, top_k=5, snapshot_id=None, filters=None):
        if (
            not isinstance(query, str)
            or not 1 <= len(query) <= 400
            or type(top_k) is not int
            or not 1 <= top_k <= 5
        ):
            raise DomainError("Local search exceeds its query/result limit", 422)
        ids, filters = self.allowed(c, chat, snapshot_id), filters or {}
        terms = re.findall(r"\w+", query, re.UNICODE)[:20]
        if not terms:
            return {"results": [], "index": "fts5" if self.fts else "bounded_lexical"}
        if self.fts:
            match = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)
            if self.store.remote:
                rows = c.execute(
                    "SELECT chunk_id,-ts_rank_cd(to_tsvector('simple',coalesce(title,'') || ' ' || coalesce(text,'')),websearch_to_tsquery('simple',?)) AS score FROM source_fts WHERE to_tsvector('simple',coalesce(title,'') || ' ' || coalesce(text,'')) @@ websearch_to_tsquery('simple',?) AND chat_id=? ORDER BY score,chunk_id LIMIT 1000",
                    (match, match, chat['id']),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT chunk_id,bm25(source_fts) AS score FROM source_fts WHERE source_fts MATCH ? AND chat_id=? ORDER BY score,chunk_id LIMIT 1000",
                    (match, chat["id"]),
                ).fetchall()
            ranked = [
                (self.store.get(c, r["chunk_id"], "source_chunk"), r["score"])
                for r in rows
            ]
        else:
            chunks = self.store.list(c, "source_chunk", chat["mission_id"])[:1000]
            ranked = sorted(
                (
                    (x, -sum(x["text"].lower().count(t.lower()) for t in terms))
                    for x in chunks
                ),
                key=lambda x: (x[1], x[0]["id"]),
            )
        results = []
        for chunk, score in ranked:
            if chunk["version_id"] not in ids or score >= 0:
                continue
            version = self.version(c, chat, chunk["version_id"])
            if (
                filters.get("heading")
                and filters["heading"].lower()
                not in (
                    chunk.get("heading", "")
                    + " "
                    + " ".join(
                        re.findall(r"^#{1,6}\s+(.+)", chunk["text"], re.MULTILINE)
                    )
                ).lower()
            ):
                continue
            if any(
                str(value).lower() not in str(version.get(key, "")).lower()
                for key, value in filters.items()
                if key in ("title", "url", "id")
            ):
                continue
            results.append(
                {k: chunk[k] for k in ("id", "version_id", "line_start", "line_end")}
                | {
                    "title": version["title"],
                    "url": version["url"],
                    "snippet": chunk["text"][:700],
                    "score": score,
                    "access": "snippet_only",
                }
            )
            if len(results) == top_k:
                break
        return {
            "results": results,
            "index": "postgres_fts" if self.store.remote else "fts5" if self.fts else "bounded_lexical",
            "ranking": "lexical, not semantic",
            "candidate_cap": 1000,
        }

    def read(
        self,
        c,
        chat,
        version_id,
        *,
        line_start=1,
        line_end=None,
        char_start=0,
        snapshot_id=None,
        seat="human",
        logical_turn_id=None,
    ):
        version = self.version(c, chat, version_id)
        if version_id not in self.allowed(c, chat, snapshot_id):
            raise DomainError("Version is outside the allowed source snapshot", 404)
        text = self.read_blob(version["text_sha256"]).decode("utf-8")
        lines = text.splitlines(keepends=True)
        end = len(lines) if line_end is None else line_end
        if (
            type(line_start) is not int
            or type(end) is not int
            or line_start < 1
            or end < line_start
            or end > max(1, len(lines))
        ):
            raise DomainError("Invalid source line range", 422)
        selected = "".join(lines[line_start - 1 : end])
        if type(char_start) is not int or char_start < 0 or char_start > len(selected):
            raise DomainError("Invalid source character offset", 422)
        selected = selected[char_start:]
        output = selected.encode()[:16384].decode("utf-8", errors="ignore")
        truncated = len(output.encode()) < len(selected.encode())
        receipt = {
            "id": uid("read"),
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "version_id": version_id,
            "snapshot_id": snapshot_id,
            "seat": seat,
            "logical_turn_id": logical_turn_id,
            "line_start": line_start,
            "line_end": end,
            "text_sha256": hashlib.sha256(output.encode()).hexdigest(),
            "bytes": len(output.encode()),
            "truncated": truncated,
            "char_start": char_start,
            "next_char_start": char_start + len(output) if truncated else None,
            "source_char_start": sum(len(x) for x in lines[: line_start - 1])
            + char_start,
            "source_char_end": sum(len(x) for x in lines[: line_start - 1])
            + char_start
            + len(output),
            "next_line": line_start + len(output.splitlines()) - 1
            if truncated
            else end + 1
            if end < len(lines)
            else None,
            "access": "passage_read",
            "source_coverage": version["coverage"],
        }
        self.store.put(c, "source_read", receipt)
        return {
            "receipt": receipt,
            "text": output,
            "title": version["title"],
            "url": version["url"],
            "limitations": version["limitations"],
            "untrusted_source": True,
        }

    def cite(
        self,
        c,
        chat,
        version_id,
        quote,
        claim_revision,
        *,
        origin="model_reported",
        support="not_assessed",
    ):
        version = self.version(c, chat, version_id)
        text = self.read_blob(version["text_sha256"]).decode()
        start = text.find(quote) if quote else -1
        binding = {
            "id": uid("citation"),
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "version_id": version_id,
            "claim_revision": claim_revision,
            "quote": quote,
            "char_start": start if start >= 0 else None,
            "char_end": start + len(quote) if start >= 0 else None,
            "quote_match": start >= 0,
            "support_assessment": support,
            "assessment_origin": origin,
            "experimental_verification": False,
        }
        self.store.put(c, "citation_binding", binding)
        return binding

    def bind_message(self, c, chat, message):
        """Existence and actual passage exposure only; no entailment/human-trust upgrade."""
        references = re.findall(
            r"\[source:(version_[0-9a-f]{24}):L(\d+)-L(\d+)\]", message["content"]
        )
        bindings = []
        call = (
            self.store.get(c, message["call_id"], "call")
            if message.get("call_id")
            else {}
        )
        logical = call.get("logical_turn_id", call.get("purpose"))
        for vid, start, end in references[:30]:
            binding = {
                "id": uid("citation"),
                "mission_id": chat["mission_id"],
                "chat_id": chat["id"],
                "message_id": message["id"],
                "version_id": vid,
                "line_start": int(start),
                "line_end": int(end),
                "source_exists": False,
                "span_exists": False,
                "quote_match": "not_assessed",
                "support_assessment": "not_assessed",
                "assessment_origin": "mechanical_source_and_exposure_check",
                "human_assessed": False,
                "experimental_verification": False,
                "exposed_passage": False,
            }
            try:
                version = self.version(c, chat, vid)
                lines = (
                    self.read_blob(version["text_sha256"])
                    .decode()
                    .splitlines(keepends=True)
                )
                binding["source_exists"] = True
                if 1 <= int(start) <= int(end) <= len(lines):
                    char_start, char_end = (
                        sum(len(x) for x in lines[: int(start) - 1]),
                        sum(len(x) for x in lines[: int(end)]),
                    )
                    binding.update(
                        span_exists=True,
                        source_char_start=char_start,
                        source_char_end=char_end,
                    )
                    binding["exposed_passage"] = any(
                        r["version_id"] == vid
                        and r.get("logical_turn_id") == logical
                        and r.get("source_char_start", -1) <= char_start
                        and r.get("source_char_end", -1) >= char_end
                        for r in self.store.list(c, "source_read", chat["mission_id"])
                    )
            except DomainError:
                pass
            self.store.put(c, "citation_binding", binding)
            bindings.append(binding)
        return bindings

    def view(self, c, chat):
        return {
            "sources": self.store.list(c, "source", chat["mission_id"]),
            "versions": self.store.list(c, "source_version", chat["mission_id"]),
            "snapshots": self.store.list(c, "library_snapshot", chat["mission_id"]),
            "receipts": self.store.list(c, "source_read", chat["mission_id"]),
            "citations": self.store.list(c, "citation_binding", chat["mission_id"]),
            "notes": self.store.list(c, "research_note", chat["mission_id"]),
            "index": "fts5" if self.fts else "bounded_lexical",
            "storage_bound_bytes": self.maximum,
            "source_changes": self.pending_changes(c, chat),
        }

    def changed(self, c, chat, source_id, previous, current):
        bindings = [
            b
            for b in self.store.list(c, "citation_binding", chat["mission_id"])
            if b["version_id"] == previous
        ]
        carried = [
            n
            for n in self.store.list(c, "source_dependency_notice", chat["mission_id"])
            if n["source_id"] == source_id and n["state"] == "pending"
        ]
        if not bindings and not carried:
            return
        notice = {
            "id": "sourcechange_" + digest([chat["id"], previous, current])[:24],
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "source_id": source_id,
            "previous_version_id": previous,
            "new_version_id": current,
            "message_ids": sorted(
                {b["message_id"] for b in bindings if b.get("message_id")}
            ),
            "claim_refs": [
                b["claim_revision"] for b in bindings if b.get("claim_revision")
            ],
            "state": "pending",
            "reason": "Referenced source version changed; current conclusions require a new source-aware review",
            "created_review_cycle": chat.get("review_cycle"),
            "original_publications_modified": False,
            "evidence_upgrade": False,
        }
        self.store.put(c, "source_dependency_notice", notice)
        notice["message_ids"] = sorted(
            set(notice["message_ids"])
            | {mid for n in carried for mid in n["message_ids"]}
        )
        notice["claim_refs"] += [
            ref for n in carried for ref in n.get("claim_refs", [])
        ]
        notice["referenced_version_ids"] = sorted(
            {b["version_id"] for b in bindings}
            | {
                v
                for n in carried
                for v in n.get("referenced_version_ids", [n["previous_version_id"]])
            }
        )
        self.store.put(c, "source_dependency_notice", notice)
        for old in carried:
            old.update(state="superseded", superseded_by=notice["id"])
            self.store.put(c, "source_dependency_notice", old)
        self.store.event(
            c,
            chat["mission_id"],
            "library.source_dependency_changed",
            {"notice_id": notice["id"], "source_id": source_id},
        )

    def pending_changes(self, c, chat):
        changes = [
            n
            for n in self.store.list(c, "source_dependency_notice", chat["mission_id"])
            if n["state"] == "pending"
        ]
        claims = [
            x
            for x in self.store.list(c, "review_claim", chat["mission_id"])
            if not chat.get("review_cycle")
            or x.get("review_cycle") == chat["review_cycle"]
        ]
        latest = {}
        for claim in claims:
            key = claim.get("claim_id", claim["id"])
            if key not in latest or claim.get("revision", 0) >= latest[key].get(
                "revision", 0
            ):
                latest[key] = claim
        for notice in changes:
            notice["affected_claims"] = [
                {"claim_id": x.get("claim_id", x["id"]), "revision": x.get("revision")}
                for x in latest.values()
                if any(
                    s.get("message_id") in notice["message_ids"]
                    for s in x.get("source_spans", [])
                )
            ]
        return [
            n
            for n in changes
            if n.get("created_review_cycle", chat.get("review_cycle"))
            == chat.get("review_cycle")
            or n["affected_claims"]
        ]

    def rechecked(self, c, chat, message):
        if (
            message.get("phase") != "recheck"
            or not message.get("call_id")
            or message.get("outdated_context")
        ):
            return
        call = self.store.get(c, message["call_id"], "call")
        if not call.get("context_pack_id"):
            return
        pack = self.store.get(c, call["context_pack_id"], "context_pack")
        read_versions = {p["version_id"] for p in pack["passages"]}
        for notice in self.pending_changes(c, chat):
            if notice["new_version_id"] in read_versions:
                notice.update(
                    state="model_rechecked",
                    recheck_message_id=message["id"],
                    assessment_origin="model_reported",
                    human_assessed=False,
                )
                self.store.put(c, "source_dependency_notice", notice)
                self.store.event(
                    c,
                    chat["mission_id"],
                    "library.source_dependency_rechecked",
                    {
                        "notice_id": notice["id"],
                        "message_id": message["id"],
                        "evidence_upgrade": False,
                    },
                )

    def cleanup_orphans(self):
        """Explicit maintenance only; no TTL deletes immutable published versions."""
        with self.store.tx() as c:
            import json

            versions = [
                json.loads(r[0])
                for r in c.execute(
                    "SELECT body FROM records WHERE kind='source_version'"
                )
            ]
            retained = {
                v[key]
                for v in versions
                for key in ("raw_sha256", "text_sha256")
                if not v.get("content_forgotten")
            }
            removed = 0
            if self.store.remote:
                for item in self.files.inventory('source-blobs'):
                    if item['path'].split('/')[-1] not in retained:
                        self.files.delete(item['path'])
                        removed += 1
                return {'orphan_blobs_removed': removed, 'retained_hashes': len(retained)}
            for path in self.root.iterdir():
                resolved = path.resolve()
                if not resolved.is_relative_to(self.root.resolve()) or not re.fullmatch(
                    "[0-9a-f]{64}", path.name
                ):
                    continue
                if path.name not in retained:
                    path.unlink()
                    removed += 1
            return {"orphan_blobs_removed": removed, "retained_hashes": len(retained)}

    def forget(self, c, chat, source_id):
        source = self.store.get(c, source_id, "source")
        if source["chat_id"] != chat["id"]:
            raise DomainError("Source outside this conversation", 404)
        source["removed"] = True
        self.store.put(c, "source", source)
        for version in self.store.list(c, "source_version", chat["mission_id"]):
            if version["source_id"] == source_id:
                version.update(
                    content_forgotten=True,
                    export_policy="reference_only",
                    replay_limitation="Source content explicitly removed by user",
                )
                self.store.put(c, "source_version", version)
                if self.fts:
                    c.execute(
                        "DELETE FROM source_fts WHERE chat_id=? AND version_id=?",
                        (chat["id"], version["id"]),
                    )
                for chunk in self.store.list(c, "source_chunk", chat["mission_id"]):
                    if chunk["version_id"] == version["id"]:
                        c.execute("DELETE FROM records WHERE id=?", (chunk["id"],))
        self.store.event(
            c,
            chat["mission_id"],
            "library.content_forgotten",
            {"source_id": source_id, "offline_replay_complete": False},
        )
