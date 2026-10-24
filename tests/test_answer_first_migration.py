"""Additive protocol adoption preserves historical publications and source attribution."""

from copy import deepcopy

from test_council_chat import drain
from test_unified_council import create

from zerowall.review_exports import export_review, verify_review_pack


def test_explicit_new_cycle_adopts_answer_first_without_reinterpreting_v3(
    client, app, tmp_path
):
    first = create(client, review_protocol="reviewed_v3")
    cid = first["chat"]["id"]
    drain(app)
    previous = deepcopy(client.get("/api/chats/" + cid).json())
    r = app.state.research
    with r.store.tx() as c:
        publication = deepcopy(
            r.store.list(c, "review_publication", first["chat"]["mission_id"])[0]
        )
    response = client.post(
        "/api/chats/" + cid + "/messages",
        headers={"Idempotency-Key": "adopt-answer-first-on-explicit-followup"},
        json={
            "review_protocol": "reviewed_v4",
            "text": "Reconsider portability under the same constraints.",
        },
    )
    assert response.is_success, response.text
    with r.store.tx() as c:
        chat = r.store.get(c, cid, "chat")
        prompt, _ids = r.chat.prompt(chat, r.chat.messages(c, chat), r.chat.next_turn(chat, r.chat.messages(c, chat), c), c)
        assert previous["messages"][-1]["content"] in __import__("json").loads(prompt)["conversation_checkpoint"]["prior_answer"]["text"]
        assert "not current-cycle evidence" in prompt
    drain(app)
    current = client.get("/api/chats/" + cid).json()
    assert current["chat"]["protocol"]["version"] == "reviewed_v4"
    assert current["chat"]["status"] == "completed"
    assert current["messages"][: len(previous["messages"])] == previous["messages"]
    assert (
        current["chat"]["protocol_history"][0]["protocol"]
        == previous["chat"]["protocol"]
    )
    with r.store.tx() as c:
        assert r.store.get(c, publication["id"], "review_publication") == publication
        packed = export_review(r, c, current["chat"])
    path = tmp_path / "mixed-history.zip"
    path.write_bytes(packed)
    assert verify_review_pack(path)["reproduced"] is True
