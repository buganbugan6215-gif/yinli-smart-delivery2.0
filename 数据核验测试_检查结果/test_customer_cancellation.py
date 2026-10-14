import json

import pytest
import pandas as pd

from 功能组件_页面共用代码 import batch_dispatch as batch, order_state as state
from 功能组件_页面共用代码.maps import nearby_roads, load_geojson


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("YL_DATABASE_URL", raising=False)
    monkeypatch.setattr(state, "ORDER_DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "ORDER_DB_PATH", tmp_path / "orders.db")
    monkeypatch.setattr(state.st, "session_state", {})
    state._cached_cloud_orders.clear()


def sample(oid, product):
    return {"订单编号": oid, "总单编号": "YG-1", "联系电话": "00000001234", "品类": product,
            "期望送达日期": "2026-10-16", "配送重量_kg": 20, "状态": "方案待确认",
            "状态序号": 1, "提交时间": "2026-10-14T10:00:00+08:00"}


def test_cancel_one_child_removes_it_from_dispatch_but_preserves_history(isolated):
    for order in (sample("YL-1", "鲜面条"), sample("YL-2", "姜蒜")):
        state.save_order_record(order)
    state.verify_customer_order("YG-1", "1234")
    with state._db_connection() as conn:
        batch._tables(conn)
        conn.execute("INSERT INTO delivery_drafts VALUES (?, ?)", ("2026-10-16", json.dumps({"旧方案": 1})))
    state.cancel_customer_order("YL-1")
    records = {o["订单编号"]: o for o in state.load_order_records()}
    assert records["YL-1"]["状态"] == "已取消"
    assert records["YL-1"]["取消时间"]
    assert [o["订单编号"] for o in batch.day_orders("2026-10-16")] == ["YL-2"]
    assert batch.get_draft("2026-10-16") is None
    with pytest.raises(ValueError, match="已经取消"):
        state.cancel_customer_order("YL-1")


def test_cancel_requires_customer_access_and_removes_confirmed_routes(isolated):
    state.save_order_record(sample("YL-3", "鲜面条"))
    with pytest.raises(ValueError, match="核验"):
        state.cancel_customer_order("YL-3")
    state.verify_customer_order("YL-3", "1234")
    second = sample("YL-4", "姜蒜")
    second.update({"状态": "仓库备货中", "状态序号": 2, "线路编号": "R2", "路线GeoJSON": {"features": []}})
    state.save_order_record(second)
    first = next(o for o in state.load_order_records() if o["订单编号"] == "YL-3")
    first.update({"状态": "仓库备货中", "状态序号": 2, "线路编号": "R1", "路线GeoJSON": {"features": []}})
    state.save_order_record(first)
    with state._db_connection() as conn:
        batch._tables(conn)
        conn.execute("INSERT INTO delivery_batches VALUES (?, ?)", ("2026-10-16", json.dumps({"订单结果": [{"订单编号": "YL-3"}, {"订单编号": "YL-4"}]})))
    state.cancel_customer_order("YL-3")
    records = {o["订单编号"]: o for o in state.load_order_records()}
    assert records["YL-3"]["状态"] == "已取消" and not records["YL-3"].get("线路编号")
    assert records["YL-4"]["状态"] == "方案待确认" and records["YL-4"]["路线GeoJSON"] is None
    assert batch.get_batch("2026-10-16") is None


def test_cancel_rejects_departed_batch(isolated):
    order = sample("YL-5", "鲜面条")
    order["状态"] = "配送途中"
    state.save_order_record(order)
    state.verify_customer_order("YL-5", "1234")
    with pytest.raises(ValueError, match="已发出"):
        state.cancel_customer_order("YL-5")


def test_staff_clear_all_orders_and_plans(isolated):
    state.save_order_record(sample("YL-6", "鲜面条"))
    with state._db_connection() as conn:
        batch._tables(conn)
        conn.execute("INSERT INTO delivery_drafts VALUES (?, ?)", ("2026-10-16", "{}"))
        conn.execute("INSERT INTO delivery_batches VALUES (?, ?)", ("2026-10-16", "{}"))
    with pytest.raises(ValueError, match="权限"):
        batch.clear_all_order_data()
    state.st.session_state["staff_authenticated"] = True
    assert batch.clear_all_order_data() == 1
    assert not state.load_order_records()
    assert batch.get_draft("2026-10-16") is None
    assert batch.get_batch("2026-10-16") is None
    pd.DataFrame([sample("OLD-EXCEL", "鲜面条")]).to_excel(state.ORDER_DATA_DIR / "历史订单.xlsx", index=False)
    assert not state.init_orders(include_saved=True)


def test_confirmed_day_rejects_late_order_atomically(isolated):
    with state._db_connection() as conn:
        batch._tables(conn)
        conn.execute("INSERT INTO delivery_batches VALUES (?, ?)", ("2026-10-16", "{}"))
    with pytest.raises(ValueError, match="已提前确认"):
        state._commit_orders([sample("YL-7", "鲜面条"), sample("YL-8", "姜蒜")])
    assert not state.load_order_records()


def test_nearby_road_payload_is_smaller_than_full_network():
    bounds = (103.72, 30.65, 103.74, 30.67)
    for name in ("road_major.geojson", "road_minor.geojson"):
        full = load_geojson(name)
        local = nearby_roads(name, bounds)
        assert local["features"]
        assert len(json.dumps(local)) < len(json.dumps(full)) / 4
