from test_workflow import reviewed, post, experiment


def test_challenge_groups_revisions_and_related_suggestions(client, app):
    v = reviewed(client, app)
    sid = v["steps"][0]["id"]
    hid = v["hypotheses"][0]["id"]
    g = post(
        client,
        f"/steps/{sid}/challenge-groups",
        {
            "expected_revision": 1,
            "title": "Physical-mechanism controls",
            "hypothesis_ids": [hid],
            "review_ids": [v["rounds"][0]["reviews"][0]["id"]],
        },
    )
    updated = post(
        client,
        f"/steps/{sid}/challenge-groups",
        {
            "expected_revision": 1,
            "title": "Updated mechanism group",
            "hypothesis_ids": [hid],
            "group_id": g["id"],
            "group_revision": 1,
        },
    )
    assert updated["revision"] == 2
    post(
        client,
        f"/steps/{sid}/challenge-groups",
        {
            "expected_revision": 1,
            "title": "Stale group overwrite",
            "hypothesis_ids": [hid],
            "group_id": g["id"],
            "group_revision": 1,
        },
        409,
    )
    assert isinstance(client.get(f"/api/steps/{sid}/related-hypotheses").json(), list)


def test_falsified_hypotheses_remain_in_negative_index(client, app):
    v = experiment(client, app, reviewed(client, app))
    sid = v["steps"][0]["id"]
    hid = v["hypotheses"][0]["id"]
    post(
        client,
        f"/steps/{sid}/reframes",
        {
            "expected_revision": 1,
            "reason": "The test contradicts the proposed broad physical interpretation",
            "interpretation": "Retain only the arithmetic result and reject the unsupported broader mechanism",
            "prediction_comparison": "The test does not support the broader physical interpretation",
            "changed_assumptions": ["Narrow the claim to arithmetic only"],
            "alternative_explanations": [
                "Client workflow overhead may explain the observations"
            ],
            "next_action": "Design a separate client workflow control",
            "evidence_ids": [v["evidences"][0]["id"]],
            "hypothesis_states": {hid: "falsified"},
        },
    )
    index = client.get(f"/api/missions/{v['mission']['id']}/negative-results").json()
    assert index[0]["hypothesis"]["id"] == hid
    assert index[0]["hypothesis"]["protocol_hash"]
    assert index[0]["experiments"][0]["plan_hash"]
    rnd = post(
        client, f"/steps/{sid}/rounds", {"expected_revision": 1, "mode": "fixture"}
    )
    with app.state.research.store.tx() as c:
        stored = app.state.research.store.get(c, rnd["id"], "round")
        assert any(
            h["id"] == hid and h["status"] == "falsified"
            for h in stored["context"]["research_memory"]["hypothesis"]
        )
        assert stored["context"]["research_memory"]["reframe"][0][
            "interpretation"
        ].startswith("Retain only")
