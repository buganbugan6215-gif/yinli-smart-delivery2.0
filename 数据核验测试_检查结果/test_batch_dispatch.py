import copy
from datetime import datetime, timezone
import json

import pytest

from 功能组件_页面共用代码 import order_state as state
from 功能组件_页面共用代码 import batch_dispatch as batch
from 功能组件_页面共用代码.delivery_calendar import delivery_day, batch_closed
from 功能组件_页面共用代码.batch_solver import solve_batch, assign_routes, travel_minutes


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "ORDER_DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "ORDER_DB_PATH", tmp_path / "orders.db")
    monkeypatch.setattr(state, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(state.st, "session_state", {})


def samples():
    result = []
    for i, coord in enumerate([(104.26, 30.85), (104.25, 30.84), (104.24, 30.83)], 1):
        result.append({"订单编号": f"TEST-{i}", "客户名称": f"虚拟客户{i}", "联系电话": f"0000000{i:04d}",
                       "经度": coord[0], "纬度": coord[1], "品类": "鲜面条", "配送重量_kg": 50,
                       "期望送达日期": "2026-09-24", "期望窗开始_分钟": 480, "期望窗结束_分钟": 1080,
                       "服务时间_分钟": 15, "状态": "方案待确认", "状态序号": 1})
    return result


@pytest.mark.parametrize("instant,day", [
    ("2026-09-23T19:59:00+08:00", "2026-09-24"),
    ("2026-09-23T19:59:59+08:00", "2026-09-24"),
    ("2026-09-23T20:00:00+08:00", "2026-09-25"),
    ("2026-09-23T20:01:00+08:00", "2026-09-25"),
    ("2026-09-23T12:01:00+00:00", "2026-09-25"),
    ("2026-12-31T19:59:59+08:00", "2027-01-01"),
    ("2026-12-31T20:00:00+08:00", "2027-01-02"),
])
def test_cutoff(instant, day):
    assert str(delivery_day(datetime.fromisoformat(instant))) == day


def test_deadline_and_peak_boundaries():
    assert not batch_closed("2026-09-24", datetime(2026, 9, 23, 19, 59, 59))
    assert batch_closed("2026-09-24", datetime(2026, 9, 23, 20, 0, 0))
    assert travel_minutes(20, 410) == pytest.approx(30)
    assert travel_minutes(20, 530) == pytest.approx(25)


def test_creation_ignores_client_date(isolated, monkeypatch):
    monkeypatch.setattr(state, "beijing_now", lambda: datetime(2026, 9, 23, 12, 1, tzinfo=timezone.utc))
    order = state.create_order({"品类": "鲜面条", "配送重量_kg": 30, "经度": 104.26, "纬度": 30.85,
                                "最早到达": "08:00", "最晚到达": "18:00", "期望送达日期": "2000-01-01"})
    assert order["期望送达日期"] == "2026-09-25"
    assert order["期望送达"].startswith("2026-09-25")


@pytest.fixture(scope="module")
def real_plan():
    orders = samples()
    plan = solve_batch(orders, state.pricing_settings())
    plan["输入指纹"] = batch.input_fingerprint(orders)
    return plan


def test_real_road_matrix_and_customer_projection(real_plan):
    batch.validate_result(real_plan, samples())
    assert len(real_plan["距离矩阵_m"]) == 4
    assert sum(len(r["订单编号列表"]) for r in real_plan["线路"]) == 3
    assert len(real_plan["线路"]) < 3  # 多单合并到配送线路，不是三次独立直达配送。
    for own in real_plan["订单结果"]:
        text = json.dumps(own["路线GeoJSON"], ensure_ascii=False)
        assert "虚拟客户" not in text and "TEST-" not in text and "联系电话" not in text
        assert own["路线GeoJSON"]["features"][0]["geometry"]["coordinates"][-1] == list(next((o["经度"], o["纬度"]) for o in samples() if o["订单编号"] == own["订单编号"]))


def test_atomic_confirm_and_progress(isolated, real_plan):
    orders = samples()
    for o in orders:
        state.save_order_record(o)
    before = datetime(2026, 9, 23, 19, 59, 59)
    now = datetime(2026, 9, 24, 6)
    with pytest.raises(ValueError, match="截止"):
        batch.confirm_batch(real_plan, before)
    bad = copy.deepcopy(real_plan)
    bad["订单结果"].pop()
    with pytest.raises(ValueError, match="覆盖"):
        batch.confirm_batch(bad, now)
    assert batch.get_batch("2026-09-24") is None
    assert {o["状态"] for o in state.load_order_records()} == {"方案待确认"}
    batch.confirm_batch(real_plan, now)
    with pytest.raises(ValueError, match="重复"):
        batch.confirm_batch(real_plan, now)
    assert {o["状态"] for o in state.load_order_records()} == {"仓库备货中"}
    batch.advance_batch("2026-09-24", "配送途中", now)
    assert {o["状态"] for o in state.load_order_records()} == {"配送途中"}
    batch.advance_batch("2026-09-24", "已送达", now)
    assert {o["状态"] for o in state.load_order_records()} == {"已送达"}


def test_customer_isolation_refresh_and_receipt(isolated, real_plan):
    orders = samples()
    for o in orders:
        state.save_order_record(o)
    state.st.session_state["customer_orders"] = [copy.deepcopy(orders[0])]
    assert state.customer_order("TEST-2") is None
    assert state.verify_customer_order("TEST-2", "9999") is None
    assert [o["订单编号"] for o in state.init_orders()] == ["TEST-1"]
    batch.confirm_batch(real_plan, datetime(2026, 9, 24, 6))
    assert state.customer_order("TEST-1")["状态"] == "仓库备货中"  # 旧会话不再覆盖新状态
    with pytest.raises(ValueError):
        state.customer_update("TEST-2", {}, receipt=True)
    with pytest.raises(ValueError):
        state.customer_update("TEST-1", {}, receipt=True)
    batch.advance_batch("2026-09-24", "配送途中")
    batch.advance_batch("2026-09-24", "已送达")
    state.st.session_state["customer_orders"] = []  # 新会话重新核验后同样可以签收。
    assert state.verify_customer_order("TEST-1", "0001")
    state.customer_update("TEST-1", {}, receipt=True)
    assert state.customer_order("TEST-1")["状态"] == "签收完成"
    assert state.customer_order("TEST-2") is None
    assert state.find_order("TEST-2", include_saved=True)["状态"] == "已送达"


def test_new_order_after_computation_rejects_stale_plan(isolated, real_plan):
    orders = samples()
    for o in orders:
        state.save_order_record(o)
    extra = dict(orders[0], 订单编号="TEST-4")
    state.save_order_record(extra)
    with pytest.raises(ValueError, match="变化"):
        batch.confirm_batch(real_plan, datetime(2026, 9, 24, 6))
    assert batch.get_batch("2026-09-24") is None


def test_no_partial_dispatch_when_capacity_insufficient():
    orders = samples()
    orders[0]["配送重量_kg"] = 999999
    rates = state.pricing_settings()
    matrix = [[0 if i == j else 1000 for j in range(4)] for i in range(4)]
    with pytest.raises(ValueError, match="全部订单"):
        assign_routes(orders, matrix, rates)
