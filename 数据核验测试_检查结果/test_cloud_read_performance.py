"""云端读取缓存与连接池回归。"""
from __future__ import annotations

from contextlib import contextmanager
import json
from types import SimpleNamespace

from 功能组件_页面共用代码 import order_state, storage


def test_cloud_orders_cache_reuses_read_and_keeps_local_reads_fresh(monkeypatch, tmp_path):
    calls = []

    class FakeConnection:
        def __enter__(self):
            calls.append(1)
            return self

        def __exit__(self, *_):
            pass

        def execute(self, *_):
            return SimpleNamespace(fetchall=lambda: [(json.dumps({"订单编号": "A"}),)])

    monkeypatch.setattr(storage, "database_url", lambda: "postgresql://cache-test")
    monkeypatch.setattr(order_state, "_db_connection", FakeConnection)
    order_state._cached_cloud_orders.clear()
    try:
        assert order_state.load_order_records() == [{"订单编号": "A"}]
        assert order_state.load_order_records() == [{"订单编号": "A"}]
        assert len(calls) == 1
        monkeypatch.setattr(storage, "database_url", lambda: None)
        order_state.load_order_records()
        assert len(calls) == 2
    finally:
        order_state._cached_cloud_orders.clear()


def test_pricing_write_clears_cloud_cache(monkeypatch):
    calls = []
    saved = {}

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, params=()):
            if sql.startswith("SELECT payload"):
                calls.append(1)
                return SimpleNamespace(fetchone=lambda: (saved["payload"],) if saved else None)
            if sql.startswith("INSERT OR REPLACE"):
                saved["payload"] = params[1]
            return SimpleNamespace(fetchone=lambda: None)

    monkeypatch.setattr(storage, "database_url", lambda: "postgresql://pricing-cache-test")
    monkeypatch.setattr(order_state, "_db_connection", FakeConnection)
    order_state._cached_cloud_pricing.clear()
    try:
        initial = order_state.pricing_settings()
        assert order_state.pricing_settings() == initial
        assert len(calls) == 1
        changed = {**initial, "起步价_元": 15.0}
        order_state.save_pricing_settings(changed)
        assert order_state.pricing_settings()["起步价_元"] == 15.0
        assert len(calls) == 2
    finally:
        order_state._cached_cloud_pricing.clear()


def test_cloud_connection_returns_lease_to_pool(monkeypatch):
    events = []

    class FakeRawConnection:
        def execute(self, *_):
            return SimpleNamespace(fetchall=lambda: [])

    @contextmanager
    def lease():
        events.append("checkout")
        try:
            yield FakeRawConnection()
        finally:
            events.append("return")

    class FakePool:
        def connection(self):
            return lease()

    monkeypatch.setattr(storage, "_cloud_pool", lambda _url: FakePool())
    with storage.CloudConnection("postgresql://pool-test") as conn:
        conn.execute("SELECT 1")
    assert events == ["checkout", "return"]


def test_legacy_excel_is_not_reimported_on_each_staff_refresh(monkeypatch, tmp_path):
    import pandas as pd

    monkeypatch.setattr(storage, "database_url", lambda: None)
    monkeypatch.setattr(order_state, "ROOT", tmp_path)
    monkeypatch.setattr(order_state, "ORDER_DATA_DIR", tmp_path)
    monkeypatch.setattr(order_state, "ORDER_DB_PATH", tmp_path / "orders.db")
    pd.DataFrame([{"订单编号": "LEGACY-1", "提交时间": "2026-10-14T10:00:00"}]).to_excel(tmp_path / "old.xlsx", index=False)
    original = pd.read_excel
    calls = []

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(order_state.pd, "read_excel", counted)
    try:
        assert len(order_state.init_orders(include_saved=True)) == 1
        assert len(order_state.init_orders(include_saved=True)) == 1
        assert len(calls) == 1
    finally:
        order_state._MIGRATED_EXCEL_KEYS.clear()
