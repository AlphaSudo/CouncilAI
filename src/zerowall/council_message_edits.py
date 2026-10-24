"""Explicit question revisions: append history, replace the active context path."""

from .db import DomainError, now, uid


def on_path(council, c, chat, messages, branch_id=None):
    branch_id = branch_id if branch_id is not None else chat.get("context_branch_id")
    prefix = set()
    if branch_id:
        branch = council.store.get(c, branch_id, "chat_message_branch")
        prefix = set(branch["prefix_message_ids"])
    return [
        m
        for m in messages
        if m["id"] in prefix or m.get("context_branch_id") == branch_id
    ]


def root_question(council, c, chat):
    return next(
        (
            m["content"]
            for m in on_path(council, c, chat, council.messages(c, chat))
            if m["role"] == "user" and m["phase"] == "prompt"
        ),
        chat["original_prompt"],
    )


def regenerate(council, c, cid, mid, body):
    chat = council.store.get(c, cid, "chat")
    council.store.check(chat, body.expected_revision)
    message = council.store.get(c, mid, "chat_message")
    if message.get("chat_id") != cid or message["role"] != "user":
        raise DomainError(
            "Only your own messages in this conversation can be edited", 422
        )
    if (
        chat.get("active_turn")
        or chat["status"] in ("running", "waiting")
        or c.execute(
            "SELECT COUNT(*) FROM jobs WHERE target_id=? AND state='running'", (cid,)
        ).fetchone()[0]
    ):
        raise DomainError(
            "Pause the council and wait for the current response before regenerating. Your edit can stay open.",
            409,
        )
    if any(
        x["state"] == "dispatching"
        for x in council.store.list(c, "call", chat["mission_id"])
    ):
        raise DomainError("Wait for the active request before regenerating", 409)
    if chat["provider"] == "nebius_token_factory":
        unknown = any(
            x["state"] == "unknown"
            for x in council.store.list(c, "call", chat["mission_id"])
        )
        if unknown and not body.authorize_retry_with_unknown_charge:
            raise DomainError(
                "Confirm that the earlier unknown charge stays counted before regenerating",
                409,
            )
    messages = council.messages(c, chat)
    # A historical message can itself be revised. Reconstruct its own path,
    # rather than accidentally including later answers from the current branch.
    source_chat = {**chat, "context_branch_id": message.get("context_branch_id")}
    prefix = [
        m
        for m in on_path(council, c, source_chat, messages)
        if m["sequence"] < message["sequence"]
    ]
    text = council.research.artifacts.redact(body.text.strip())
    root = next(
        (
            m["content"]
            for m in prefix
            if m["role"] == "user" and m["phase"] == "prompt"
        ),
        None,
    )
    question = root + "\n\nCurrent director request:\n" + text if root else text
    checkpoint = {
        "version": "message-revision-context/1",
        "prior_messages": [
            {
                k: m[k]
                for k in ("id", "role", "content", "phase", "name", "model")
                if k in m
            }
            for m in prefix
        ],
        "rule": "Only these earlier public messages precede the edited request. Later messages on the previous revision are saved history, not current instructions or evidence. Prior assessments remain historical and must be re-evaluated.",
    }
    branch = {
        "id": uid("message_branch"),
        "chat_id": cid,
        "mission_id": chat["mission_id"],
        "prefix_message_ids": [m["id"] for m in prefix],
        "edited_from_message_id": mid,
        "source_branch_id": message.get("context_branch_id"),
        "created_at": now(),
    }
    council.store.put(c, "chat_message_branch", branch)
    chat["context_branch_id"] = branch["id"]
    if not root:
        chat["title"] = text.splitlines()[0][:120]
    c.execute(
        "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state IN ('queued','waiting')",
        (cid,),
    )
    # This releases only unused finishing holds, never settled or unknown calls.
    from .answer_budget import release

    release(council, c, chat)
    for item in council.store.list(c, "chat_steering", chat["mission_id"]):
        if item["state"] == "queued":
            item["state"] = "superseded"
            council.store.put(c, "chat_steering", item)
    for key in (
        "pending_request_recovery",
        "pending_output_recovery",
        "completion_reason",
    ):
        chat.pop(key, None)
    context = {"question": question, "checkpoint": checkpoint}
    metadata = {
        "phase": "intervention" if root else "prompt",
        "edited_from_message_id": mid,
    }
    if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
        council.review.engine(chat).new_cycle(
            c, chat, text, context_override=context, message_metadata=metadata
        )
    else:
        council.review.adopt_scoped(
            c,
            chat,
            text,
            "reviewed_v4",
            context_override=context,
            message_metadata=metadata,
        )
    revised = next(
        m
        for m in council.messages(c, chat)
        if m.get("context_branch_id") == branch["id"] and m["role"] == "user"
    )
    branch["message_id"] = revised["id"]
    council.store.put(c, "chat_message_branch", branch)
    council.store.event(
        c,
        chat["mission_id"],
        "chat.message_revised",
        {
            "chat_id": cid,
            "original_message_id": mid,
            "revised_message_id": revised["id"],
            "branch_id": branch["id"],
            "review_cycle": chat["review_cycle"],
            "prior_charges_retained": True,
        },
    )
    return council.view(c, cid)
