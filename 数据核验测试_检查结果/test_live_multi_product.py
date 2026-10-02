import copy
from datetime import date, datetime
import json

import pytest
from streamlit.testing.v1 import AppTest

from 功能组件_页面共用代码 import order_state as state
from 功能组件_页面共用代码 import batch_dispatch as dispatch
from 功能组件_页面共用代码 import delivery_calendar as calendar
from 功能组件_页面共用代码 import live_operations as live
from 功能组件_页面共用代码.batch_solver import solve_batch, assign_routes
from 功能组件_页面共用代码.ui import STAFF_PAGES
from test_batch_ui import ROOT, button


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "ORDER_DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "ORDER_DB_PATH", tmp_path / "orders.db")
    monkeypatch.setattr(state, "SETTINGS_PATH", tmp_path / "settings.json")
    return tmp_path


def payload():
    return {"客户名称": "测试门店", "联系人": "测试", "联系电话": "00000001234", "收货地址": "测试地址",
            "鲜面需求量_kg": 25, "生姜需求量_kg": 40, "大蒜需求量_kg": 50,
            "经度": 104.25, "纬度": 30.84, "最早到达": "08:00", "最晚到达": "18:00"}


def test_atomic_split_clock_quote_and_permissions(database, monkeypatch):
    monkeypatch.setattr(state.st, "session_state", {})
    calls = []
    def clock():
        calls.append(1)
        return datetime(2026, 10, 2, 19, 59, 59)
    monkeypatch.setattr(state, "beijing_now", clock)
    orders = state.create_order_group(payload())
    assert len(calls) == 1
    assert len(orders) == 2
    assert {o["期望送达日期"] for o in orders} == {"2026-10-03"}
    assert len({o["总单编号"] for o in orders}) == 1
    assert {o["配送重量_kg"] for o in orders} == {25, 90}
    assert {o["服务时间_分钟"] for o in orders} == {10}
    for o in orders:
        assert o["预估费用_元"] == state.estimate_delivery_fee(o["品类"], o["配送重量_kg"], o["经度"], o["纬度"])["预估费用_元"]
    other = state.create_order_group({**payload(), "联系电话": "99999991234"})
    state.st.session_state.clear()
    assert state.verify_customer_order(orders[0]["总单编号"], "9999") is None
    assert state.init_orders() == []
    assert state.verify_customer_order(orders[0]["总单编号"], "1234")
    assert {o["订单编号"] for o in state.init_orders()} == {o["订单编号"] for o in orders}
    assert state.customer_order(other[0]["订单编号"]) is None
    state.st.session_state.clear()
    assert state.verify_customer_order(orders[1]["订单编号"], "1234")
    assert len(state.init_orders()) == 2


def test_split_rolls_back_all_children(database, monkeypatch):
    monkeypatch.setattr(state.st, "session_state", {})
    with state._db_connection() as connection:
        connection.execute("CREATE TRIGGER fail_ginger BEFORE INSERT ON orders WHEN json_extract(NEW.payload, '$.品类') = '姜蒜' BEGIN SELECT RAISE(ABORT, 'test rollback'); END")
    with pytest.raises(Exception, match="test rollback"):
        state.create_order_group(payload())
    assert state.load_order_records() == []
    assert not state.st.session_state.get("customer_orders")
    assert not list(database.glob("*.xlsx"))


def test_single_product_and_invalid_weights(database, monkeypatch):
    monkeypatch.setattr(state.st, "session_state", {})
    for key in ("鲜面需求量_kg", "生姜需求量_kg", "大蒜需求量_kg"):
        with pytest.raises(ValueError):
            state.create_order_group({**payload(), key: float("nan")})
    orders = state.create_order_group({**payload(), "鲜面需求量_kg": 0})
    assert len(orders) == 1 and orders[0]["品类"] == "姜蒜"


def test_solver_and_confirmation_reject_mixed_vehicle(database, monkeypatch):
    monkeypatch.setattr(state.st, "session_state", {})
    orders = state.create_order_group(payload())
    plan = solve_batch(orders, state.pricing_settings())
    plan["输入指纹"] = dispatch.input_fingerprint(orders)
    dispatch.validate_result(plan, orders)
    assert len(plan["线路"]) == 2
    assert len({r["车辆编号"] for r in plan["线路"]}) == 2
    assert {r["品类"] for r in plan["线路"]} == {"鲜面条", "姜蒜"}
    limited = {**state.pricing_settings(), "小型冷藏车数量": 1, "大型冷藏车数量": 0}
    with pytest.raises(ValueError, match="未找到"):
        assign_routes(orders, plan["距离矩阵_m"], limited)
    tampered = copy.deepcopy(plan)
    tampered["线路"][0]["订单编号列表"] += tampered["线路"].pop()["订单编号列表"]
    with pytest.raises(ValueError, match="混装"):
        dispatch.validate_result(tampered, orders)
    result = live.compare_strategies(orders, plan)
    assert all(r["车辆数"] == 2 for r in result["结果"])
    rows = live.plan_metrics(plan)
    assert len(rows) == 2
    assert all(r["固定及里程成本_元"] > 0 for r in rows)


def test_customer_dual_submit_and_staff_live_pages(database, monkeypatch):
    monkeypatch.setattr(calendar, "beijing_now", lambda: datetime(2026, 10, 2, 10))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.switch_page("pages/客户下单.py").run()
    for label, value in (("客户名称", "测试门店"), ("联系人", "测试"), ("收货地址", "测试地址"), ("联系电话", "00000001234")):
        next(i for i in app.text_input if i.label == label).input(value)
    app.multiselect[0].set_value(["鲜面条", "姜蒜"]).run()
    app.date_input[0].set_value(date(2026, 10, 4)).run()
    next(i for i in app.number_input if i.label.startswith("经度")).set_value(104.25)
    next(i for i in app.number_input if i.label.startswith("纬度")).set_value(30.84)
    button(app, "提交配送订单").click().run()
    assert not app.exception
    assert len(state.load_order_records()) == 2
    assert {o["期望送达日期"] for o in state.load_order_records()} == {"2026-10-04"}
    assert any("共 2 个配送子单" in item.value for item in app.success)
    app.session_state["staff_authenticated"] = True
    app.switch_page("pages/订单与需求.py").run()
    assert not app.exception
    assert any("暂无实际订单" in i.value for i in app.info)
    app.selectbox[0].select("其他日期").run()
    app.date_input[0].set_value(date(2026, 10, 4)).run()
    assert len(app.dataframe[0].value) == 2
    app.switch_page("pages/成本与绩效.py").run()
    app.selectbox[0].select("其他日期").run()
    app.date_input[0].set_value(date(2026, 10, 4)).run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label == "配送子单") == "2"
    button(app, "计算本配送日方案对比").click().run()
    assert not app.exception
    assert any("方案" in df.value.columns for df in app.dataframe)
    # 新订单进入后旧对比不可继续显示为实时结果。
    existing = state.load_order_records()[0]
    state.save_order_record({**existing, "订单编号": "NEW-TEST"})
    app.run()
    assert any("原对比失效" in w.value for w in app.warning)
    assert len(STAFF_PAGES) == 5 and len(set(p for p, _ in STAFF_PAGES)) == 5
    for path, _ in STAFF_PAGES:
        assert "load_site_data" not in (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("instant,selected,accepted", [
    ("2026-10-03T19:59:59+08:00", "2026-10-04", True),
    ("2026-10-03T19:59:59+08:00", "2026-10-05", True),
    ("2026-10-03T20:00:00+08:00", "2026-10-04", False),
    ("2026-10-03T20:00:00+08:00", "2026-10-05", True),
    ("2026-10-03T12:00:00+00:00", "2026-10-04", False),
    ("2026-12-31T10:00:00+08:00", "2027-01-02", True),
])
def test_requested_day_rechecked_atomically(database, monkeypatch, instant, selected, accepted):
    monkeypatch.setattr(state.st, "session_state", {})
    monkeypatch.setattr(state, "beijing_now", lambda: datetime.fromisoformat(instant))
    if not accepted:
        with pytest.raises(ValueError, match="已截止"):
            state.create_order_group({**payload(), "期望送达日期": selected})
        assert state.load_order_records() == []
    else:
        orders = state.create_order_group({**payload(), "期望送达日期": selected})
        assert {o["期望送达日期"] for o in orders} == {selected}
        assert all(o["期望送达"] == f"{selected} 08:00" and o["最晚送达"] == f"{selected} 18:00" for o in orders)


def test_group_map_colors_privacy_and_stop_timer(monkeypatch):
    import streamlit as st
    import streamlit_folium
    from test_gps_simulator import _order
    first, _ = _order("已送达")
    first.update({"订单编号": "MAP-N", "总单编号": "GROUP", "品类": "鲜面条", "线路编号": "RN", "期望送达日期": "2026-10-03"})
    second = {**copy.deepcopy(first), "订单编号": "MAP-G", "品类": "姜蒜", "线路编号": "RG", "状态": "配送途中"}
    unrelated = {**copy.deepcopy(first), "订单编号": "OTHER-PRIVATE", "总单编号": "OTHER"}
    orders = [first, second, unrelated]
    monkeypatch.setattr(state, "init_orders", lambda *a, **k: copy.deepcopy(orders))
    monkeypatch.setattr(state, "customer_order", lambda oid: copy.deepcopy(next(o for o in orders if o["订单编号"] == oid)))
    components, intervals = [], []
    original_fragment = st.fragment
    def fragment(*a, **kw):
        intervals.append(kw.get("run_every"))
        return original_fragment(*a, **kw)
    monkeypatch.setattr(st, "fragment", fragment)
    monkeypatch.setattr(streamlit_folium, "_component_func", lambda **kw: components.append(kw))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.session_state["active_order_id"] = "MAP-N"
    app.switch_page("pages/配送网络地图.py").run()
    assert not app.exception
    assert intervals[-1] == "10s"
    script = components[-1]["script"]
    assert "#1750df" in script and "#bd5800" in script and "8 8" in script
    assert "OTHER-PRIVATE" not in script
    assert len(app.dataframe[0].value) == 2
    second["状态"] = "已送达"
    app.run()
    assert not app.exception and intervals[-1] is None
    assert any("自动更新已停止" in c.value for c in app.caption)


def test_open_form_crossing_cutoff_requires_date_confirmation(database, monkeypatch):
    clock = [datetime(2026, 10, 3, 19, 59, 59)]
    monkeypatch.setattr(calendar, "beijing_now", lambda: clock[0])
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.switch_page("pages/客户下单.py").run()
    for label, value in (("客户名称", "测试"), ("联系人", "测试"), ("收货地址", "测试地址"), ("联系电话", "00000001234")):
        next(i for i in app.text_input if i.label == label).input(value)
    next(i for i in app.number_input if i.label.startswith("经度")).set_value(104.25)
    next(i for i in app.number_input if i.label.startswith("纬度")).set_value(30.84)
    clock[0] = datetime(2026, 10, 3, 20, 0)
    button(app, "提交配送订单").click().run()
    assert not app.exception
    assert state.load_order_records() == []
    assert any("本次未创建订单" in e.value for e in app.error)
    button(app, "提交配送订单").click().run()
    assert not app.exception
    assert {o["期望送达日期"] for o in state.load_order_records()} == {"2026-10-05"}
