import pytest

from zerowall.cloud_migration import cutover, inventory, snapshot
from zerowall.db import DomainError, Store


def source(path):
    path.mkdir()
    store = Store(path / "zerowall.sqlite3")
    with store.tx() as c:
        store.put(
            c,
            "sample",
            {
                "id": "private-history",
                "mission_id": "mission",
                "content": "A private original question",
            },
        )
        c.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
            ("known", "mission", "call1", 100000, 40000, "settled", "{}"),
        )
        c.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
            ("unknown", "mission", "call2", 230000, None, "unknown", "{}"),
        )
        store.set_setting(c, "live_verification", {"existing_credit_usd": 25})
        store.set_setting(
            c,
            "token_factory_spending_authority",
            {"user_testing_authorized": True, "authorized_cap_usd": 24},
        )
    (path / "source-blobs").mkdir()
    (path / "source-blobs" / "example").write_bytes(b"private bytes")
    return store


@pytest.mark.parametrize("history", [False, True])
def test_cutover_preserves_paid_and_unknown_amounts_and_disables_old_authority(
    pg, tmp_path, history
):
    old = source(tmp_path / "local")
    before = inventory(*snapshot(tmp_path / "local"))
    assert before["committed_microusd_all_providers"] == 270000
    report = cutover(tmp_path / "local", pg, include_history=history)
    assert report["snapshot_sha256"] == before["snapshot_sha256"]
    with old.tx() as c:
        assert not old.setting(c, "live_verification")
        assert not old.setting(c, "token_factory_spending_authority")[
            "user_testing_authorized"
        ]
        assert old.get(c, "private-history")["content"]
    with pg.tx() as c:
        assert (
            c.execute(
                "SELECT SUM(CASE WHEN state='settled' THEN actual_microusd ELSE maximum_microusd END) FROM reservations"
            ).fetchone()[0]
            == 270000
        )
        assert bool(c.execute("SELECT 1 FROM records").fetchone()) == history
        assert bool(c.execute("SELECT 1 FROM blob_files").fetchone()) == history
        assert (
            pg.setting(c, "cloud_ledger_ready")["includes_private_history"] == history
        )
        assert not pg.setting(c, "live_verification")
    with pytest.raises(DomainError, match="empty destination"):
        cutover(tmp_path / "local", pg)
