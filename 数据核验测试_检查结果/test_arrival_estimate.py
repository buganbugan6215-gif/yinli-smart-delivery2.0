"""用可手算线路验证预测，含旧批次、等待、高峰、双仓和客户页面。"""
import copy
import json
from datetime import datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.runtime.state.session_state_proxy import SessionStateProxy

from 功能组件_页面共用代码 import order_state as state
from 功能组件_页面共用代码.arrival_estimate import arrival_window, estimate_from_plan
from 功能组件_页面共用代码.batch_dispatch import _tables


def fixture_route():
    orders = [{"订单编号": oid, "线路编号": "R1", "车辆编号": "测试车", "配送顺序": i,
               "期望送达日期": "2026-10-16", "计划发车_分钟": 270,
               "计划到达_分钟": earliest, "期望窗开始_分钟": earliest,
               "期望窗结束_分钟": 600, "服务时间_分钟": service, "状态": "仓库备货中",
               "状态序号": 2, "品类": "鲜面条", "配送重量_kg": 25,
               "客户名称": "虚拟客户", "联系电话": "00000001234", "收货地址": "测试地址",
               "最早到达": "05:23", "最晚到达": "10:00", "期望送达": "2026-10-16 05:23",
               "最晚送达": "2026-10-16 10:00", "数据模式": "测试"}
              for i, (oid, earliest, service) in enumerate((("A", 300, 15), ("B", 360, 10)), 1)]
    plan = {"配送日期": "2026-10-16", "发车分钟": 270,
            "参数": {"平均速度_kmh": 60, "早高峰速度_kmh": 30},
            "矩阵标签": ["配送中心", "A", "B"],
            "距离矩阵_m": [[0, 20000, 500000], [21000, 0, 10000], [30000, 12000, 0]],
            "线路": [{"线路编号": "R1", "仓库编号": "D0", "发车时间_分钟": 270,
                      "订单编号列表": ["A", "B"]}]}
    return plan, orders


def test_arrival_is_not_clamped_to_0523_and_service_is_separate():
    plan, orders = fixture_route()
    orders[0]["期望窗开始_分钟"] = orders[0]["计划到达_分钟"] = 323
    result = estimate_from_plan(orders[0], plan, orders)
    # 同一车还有后续订单，发车推迟至05:10，前站不再提前等待33分钟。
    assert result["发车"] == "10月16日 05:10"
    assert result["标签"] == "10月16日 05:30"
    assert result["开始服务"] == "10月16日 05:30"
    assert result["完成交付"] == "10月16日 05:45"
    assert result["本站等待_分钟"] == 0
    assert result["道路里程_km"] == 20


def test_second_stop_uses_route_legs_and_previous_wait_and_service():
    plan, orders = fixture_route()
    result = estimate_from_plan(orders[1], plan, orders)
    # 按整条线路调整发车，第二站只提前约5分钟到达。
    assert result["标签"] == "10月16日 05:55"
    assert result["道路里程_km"] == 30  # 不是仓库直接到B的500km，也不是返程距离。
    assert result["行驶_分钟"] == 30
    assert result["前站等待_分钟"] == 0
    assert result["本站等待_分钟"] <= 5
    assert result["前站服务_分钟"] == 15
    assert result["完成交付"] == "10月16日 06:10"
    changed = copy.deepcopy(orders)
    changed[0]["服务时间_分钟"] += 7
    assert estimate_from_plan(changed[1], plan, changed)["发车"] < result["发车"]
    plan["距离矩阵_m"][1][2] += 5000
    assert estimate_from_plan(orders[1], plan, orders)["道路里程_km"] == 35


def test_actual_departure_recomputes_rush_hour_and_absorbed_wait():
    plan, orders = fixture_route()
    plan["线路"][0]["发车时间_分钟"] = 410  # 06:50
    assert estimate_from_plan(orders[0], plan, orders)["标签"] == "10月16日 07:20"
    orders[0]["发车时间"] = "2026-10-16T07:10:00+08:00"
    assert estimate_from_plan(orders[0], plan, orders)["标签"] == "10月16日 07:50"
    plan, orders = fixture_route()
    orders[0]["期望窗开始_分钟"] = 480
    before = estimate_from_plan(orders[1], plan, orders)
    orders[1]["发车时间"] = "2026-10-16T05:30:00+08:00"
    after = estimate_from_plan(orders[1], plan, orders)
    assert before["标签"] == after["标签"] == "10月16日 08:35"
    assert before["前站等待_分钟"] <= 5
    assert after["前站等待_分钟"] > 100


def test_second_warehouse_and_demo_date_and_missing_input():
    plan, orders = fixture_route()
    plan["矩阵标签"].append("新增配送点")
    for row in plan["距离矩阵_m"]:
        row.append(1000)
    plan["距离矩阵_m"].append([1000, 5000, 5000, 0])
    plan["仓库"] = [{"编号": "D0"}, {"编号": "D6"}]
    plan["线路"][0]["仓库编号"] = "D6"
    orders[0].update({"演示发车": True, "状态": "配送途中", "发车时间": "2026-10-15T11:00:00+08:00"})
    result = estimate_from_plan(orders[0], plan, orders, datetime(2026, 10, 15, 11))
    assert result["标签"] == "10月16日 05:30"
    assert result["道路里程_km"] == 5
    assert "演示" in result["来源"]
    assert not result["临近"]
    assert estimate_from_plan(orders[1], plan, [orders[1]]) is None
    plan["距离矩阵_m"][3][1] = float("nan")
    assert estimate_from_plan(orders[0], plan, orders) is None


def test_old_confirmed_batch_and_customer_ui_use_recalculated_eta(tmp_path, monkeypatch):
    monkeypatch.delenv("YL_DATABASE_URL", raising=False)
    monkeypatch.setattr(state, "ORDER_DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "ORDER_DB_PATH", tmp_path / "orders.db")
    monkeypatch.setattr(state, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(state.st, "session_state", SessionStateProxy())
    plan, orders = fixture_route()
    orders[0]["期望窗开始_分钟"] = orders[0]["计划到达_分钟"] = 323
    for order in orders:
        state.save_order_record(order)
    # 存入只有旧字段的已确认批次；不重新计算/确认，也不改写用户预约。
    with state._db_connection() as conn:
        _tables(conn)
        conn.execute("INSERT INTO delivery_batches VALUES (?, ?)", (plan["配送日期"], json.dumps(plan)))
    assert arrival_window(orders[0])["标签"] == "10月16日 05:30"
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    app.session_state["verified_order_ids"] = ["A"]
    app.switch_page("pages/订单追踪.py").run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label == "预计到达时间") == "10月16日 05:30"
    assert any("05:30" in c.value and "05:45" in c.value for c in app.caption)
    assert "00000001234" not in str(app.get("markdown"))
    assert state.find_order("A", include_saved=True)["期望窗开始_分钟"] == 323
