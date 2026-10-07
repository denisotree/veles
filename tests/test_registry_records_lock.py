"""Install records are read-modify-write; concurrent writers (two installs, an
install and `module approve`) must not lose each other's records."""

from __future__ import annotations

import threading
import time

from veles.core.registry import records
from veles.core.registry.records import InstallRecord, load_records, put_record


def test_concurrent_put_record_loses_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    real_save = records._save

    def slow_save(recs):  # widen the read→write window
        time.sleep(0.01)
        real_save(recs)

    monkeypatch.setattr(records, "_save", slow_save)

    def writer(i: int) -> None:
        for j in range(5):
            put_record(
                InstallRecord(name=f"m{i}-{j}", kind="module", path=f"/x/{i}/{j}", tree_sha256="h")
            )

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(load_records()) == 20
