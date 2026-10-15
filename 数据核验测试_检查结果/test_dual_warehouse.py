import copy
from datetime import datetime, date
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from 功能组件_页面共用代码 import order_state as state, batch_dispatch as dispatch, warehouses
from 功能组件_页面共用代码.batch_solver import solve_batch, route_schedule
from 功能组件_页面共用代码.warehouse_routing import replenishment


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "ORDER_DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "ORDER_DB_PATH", tmp_path/"orders.db")
    monkeypatch.setattr(state, "SETTINGS_PATH", tmp_path/"settings.json")


def orders():
    result = []
    for i, (product, xy) in enumerate([("鲜面条", (104.26, 30.85)), ("鲜面条", (104.0616461, 30.6608656)), ("姜蒜", (104.062, 30.661))]):
        result.append({"订单编号": f"DUAL-{i}", "客户名称": "虚拟测试", "品类": product,
                       "经度": xy[0], "纬度": xy[1], "配送重量_kg": 200,
                       "期望送达日期": "2020-01-02", "期望窗开始_分钟": 480,
                       "期望窗结束_分钟": 1080, "服务时间_分钟": 10, "状态": "方案待确认", "状态序号": 1})
    return result


@pytest.fixture(scope="module")
def plans():
    results = []
    for count in (1, 2):
        plan = solve_batch(orders(), state.pricing_settings(), warehouse_count=count)
        plan["输入指纹"] = dispatch.input_fingerprint(orders())
        results.append(plan)
    return results


def test_exact_selected_depot_and_source_distances(plans):
    single, dual = plans
    assert [d["编号"] for d in dual["仓库"]] == ["D0", "D6"]
    assert dual["仓库"][1]["坐标"] == [104.0616461, 30.6608656]
    assert dual["距离矩阵_m"][0][-1]/1000 == pytest.approx(35.17166409121595, abs=.001)
    assert dual["距离矩阵_m"][-1][0]/1000 == pytest.approx(35.25939792070599, abs=.001)
    assert len(single["距离矩阵_m"]) == 4 and len(dual["距离矩阵_m"]) == 5
    for plan in plans:
        dispatch.validate_result(plan, orders())
        assert len({a["订单编号"] for a in plan["订单结果"]}) == 3
    assert {a["仓库编号"] for a in dual["订单结果"]} == {"D0", "D6"}


def test_costs_close_and_unknown_site_not_zero(plans):
    single, dual = plans
    c = dual["成本"]
    assert c["补货运输费_元"] == pytest.approx(2 * 4 * (35.17166409121595 + 35.25939792070599), abs=.01)
    assert c["补货固定费_元"] == 800
    assert c["新增场地费_元"] is None and c["含新增场地总费用_元"] is None
    assert c["配送车辆固定费_元"] == single["成本"]["配送车辆固定费_元"] == 2400
    parts = ["配送车辆固定费_元", "末端运输费_元", "末端制冷费_元", "时间窗罚金_元", "货损费_元", "补货固定费_元", "补货运输费_元", "补货制冷费_元", "新增点处理费_元"]
    assert c["未含新增场地费_元"] == pytest.approx(sum(c[k] for k in parts))
    # 少量订单双仓不一定便宜，不能套用线下固定节省比例。
    assert c["未含新增场地费_元"] > single["成本"]["未含新增场地费_元"]


def test_mode_change_invalidates_pending_but_preserves_orders(database, plans):
    for o in orders():
        state.save_order_record(o)
    dispatch.save_draft(plans[0])
    assert len(dispatch.calculation_groups("2020-01-02")[1]) == 3
    warehouses.save_selection("2020-01-02", 2)
    assert len(dispatch.calculation_groups("2020-01-02")[0]) == 3
    with pytest.raises(ValueError, match="仓库模式"):
        dispatch.confirm_batch(plans[0], datetime(2020, 1, 2, 6))
    dispatch.save_draft(plans[1])
    dispatch.confirm_batch(plans[1], datetime(2020, 1, 2, 6))
    with pytest.raises(ValueError, match="锁定"):
        warehouses.save_selection("2020-01-02", 1)
    assert {o["仓库编号"] for o in state.load_order_records()} == {"D0", "D6"}
    assert len(state.load_order_records()) == 3


def test_replenishment_capacity_and_product_separation(plans):
    data = orders()
    data[1]["配送重量_kg"] = 7001
    rows = replenishment(data, [{"depot": 4, "sequence": [2, 3]}], plans[1]["距离矩阵_m"], state.pricing_settings(), 2)
    assert {r["品类"]: r["补货车数"] for r in rows} == {"鲜面条": 2, "姜蒜": 1}
    assert all(r["就绪分钟"] > r["发车分钟"] for r in rows)


def test_delivery_waits_for_replenishment_and_shared_fleet(plans):
    plan = solve_batch(orders(), state.pricing_settings(), departure=0, warehouse_count=2)
    ready = plan["补货"][0]["就绪分钟"]
    assert all(r["发车时间_分钟"] >= ready for r in plan["线路"] if r["仓库编号"] == "D6")
    limited = {**state.pricing_settings(), "小型冷藏车数量": 1, "大型冷藏车数量": 0}
    with pytest.raises(ValueError, match="全部订单"):
        solve_batch(orders(), limited, warehouse_count=2)
    for a in plans[1]["订单结果"]:
        assert a["路线GeoJSON"]["features"][0]["geometry"]["coordinates"][0] == a["仓库坐标"]
        assert all(o["订单编号"] not in str(a["路线GeoJSON"]) for o in orders())


def test_single_dual_ui_switch_recalculates_shared_views(database, monkeypatch):
    # 地图数据正确性由独立测试检验；此处聚焦真实页面状态转换，避免重复输出整份路网。
    from 功能组件_页面共用代码 import warehouse_ui
    monkeypatch.setattr(warehouse_ui, "render_map", lambda *a, **k: None)
    for o in orders():
        state.save_order_record(o)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/"app.py"), default_timeout=60).run()
    app.session_state["staff_authenticated"] = True
    app.switch_page("pages/企业工作台.py").run()
    assert not any(widget.label == "最早发车时间" for widget in app.time_input)
    app.selectbox[0].select("其他日期").run()
    app.date_input[0].set_value(date(2020, 1, 2)).run()
    next(b for b in app.button if b.label == "立即计算路径").click().run()
    assert not app.exception
    next(r for r in app.radio if r.label == "配送仓库").set_value(2).run()
    assert not app.exception
    assert dispatch.get_draft("2020-01-02")["仓库数量"] == 2
    assert next(m.value for m in app.metric if m.label == "待计算订单") == "0"
    next(r for r in app.radio if r.label == "配送仓库").set_value(1).run()
    assert not app.exception and dispatch.get_draft("2020-01-02")["仓库数量"] == 1


def test_map_contains_only_two_warehouse_markers_and_expanded_bounds(plans):
    from 功能组件_页面共用代码.maps import plan_map
    import folium
    m = plan_map(plans[1])
    markers = [v for v in m._children.values() if isinstance(v, folium.Marker) and not isinstance(v, folium.CircleMarker)]
    assert len(markers) == 2
    assert {tuple(v.location) for v in markers} == {(30.851137170192068, 104.26104981303031), (30.6608656, 104.0616461)}


def test_staff_map_uses_route_motion_and_stop_dwell(plans):
    import json
    from 功能组件_页面共用代码.maps import plan_map, AnimatedVehicle, PlaybackControl
    from 功能组件_页面共用代码.vehicle_simulator import plan_route_motion

    plan = plans[1]
    fmap = plan_map(plan, orders=orders())
    assert sum(isinstance(child, AnimatedVehicle) for child in fmap._children.values()) == len(plan["线路"])
    first_departure = min(route["发车时间_分钟"] for route in plan["线路"])
    animations = [child for child in fmap._children.values() if isinstance(child, AnimatedVehicle)]
    for route, animation in zip(plan["线路"], animations):
        offset = (route["发车时间_分钟"] - first_departure) * 60
        timeline = json.loads(animation.timeline_json)
        assert timeline[0][2] == 0
        if offset:
            assert timeline[1][:2] == timeline[0][:2]
            assert timeline[1][2] == offset
    assert any(isinstance(child, PlaybackControl) for child in fmap._children.values())
    assert len(fmap.staff_pause_rows) == len(plan["订单结果"])
    for route in plan["线路"]:
        timeline, pauses = plan_route_motion(plan, route, orders())
        assert timeline and len(pauses) == len(route["订单编号列表"])
        assert all(pause["departure_seconds"] >= pause["arrival_seconds"] for pause in pauses)
    assert "yinli-playback" in fmap.get_root().render()
