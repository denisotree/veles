"""M214 — proactive delivery audit log."""

from __future__ import annotations

from veles.core.proactive.delivery_log import DeliveryLog


def test_record_and_recent_newest_first():
    log = DeliveryLog(":memory:")
    log.record(target="telegram:1", dedup_key="a", ok=False, reason="no_target_yet", now=10)
    log.record(target="telegram:1", dedup_key="a", ok=True, reason=None, now=20)
    recent = log.recent(limit=10)
    assert [a.ok for a in recent] == [True, False]  # newest first
    assert recent[0].target == "telegram:1"
    assert recent[1].reason == "no_target_yet"
    log.close()


def test_recent_respects_limit():
    log = DeliveryLog(":memory:")
    for i in range(5):
        log.record(target="telegram:1", dedup_key=str(i), ok=True, now=float(i))
    assert len(log.recent(limit=3)) == 3
    log.close()
