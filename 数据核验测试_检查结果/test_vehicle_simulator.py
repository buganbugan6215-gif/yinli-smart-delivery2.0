from datetime import datetime, timedelta
import json
import sqlite3
import pytest

from 功能组件_页面共用代码.vehicle_simulator import arrival_risk, get_tracking_snapshot, route_coordinates, route_motion_plan, route_motion_timeline, route_stop_data
from 功能组件_页面共用代码.batch_solver import travel_minutes


def _order(status="配送途中"):
    departed = datetime(2026, 9, 23, 10, 0, 0)
    return {
        "状态": status,
        "发车时间": departed.isoformat(sep=" "),
        "服务时间_分钟": 10,
        "期望窗结束_分钟": 12 * 60,
        "允许窗结束_分钟": 12 * 60 + 30,
        "路线GeoJSON": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"route_mode": "Dijkstra路网最短路径"},
                "geometry": {"type": "LineString", "coordinates": [[104.0, 30.0], [104.1, 30.0]]},
            }],
        },
    }, departed


def test_route_coordinates_supports_multiline_and_deduplicates():
    route = {"features": [{"geometry": {"type": "MultiLineString", "coordinates": [[[1, 2], [2, 3]], [[2, 3], [3, 4]]]}}]}
    assert route_coordinates(route) == [[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]]


def test_snapshot_moves_forward_and_remaining_distance_falls():
    order, departed = _order()
    first = get_tracking_snapshot(order, now=departed, demo_factor=60)
    later = get_tracking_snapshot(order, now=departed + timedelta(seconds=10), demo_factor=60)
    assert first and later
    assert later["progress"] > first["progress"]
    assert later["remaining_km"] < first["remaining_km"]


def test_motion_timeline_uses_road_length_and_peak_speed():
    order, departed = _order()
    order["计划发车_分钟"] = 419
    order["行驶参数"] = {"平均速度_kmh": 60, "早高峰速度_kmh": 30}
    timeline = route_motion_timeline(order)
    snapshot = get_tracking_snapshot(order, now=departed, speed_kmh=60, peak_speed_kmh=30, demo_factor=1)
    assert timeline[0][2] == 0
    assert timeline[-1][2] == pytest.approx(travel_minutes(snapshot["total_km"], 419, 60, 30) * 60)
    assert timeline[-1][:2] == [30.0, 104.1]


def test_motion_pauses_at_each_station_for_wait_and_service():
    order, _ = _order()
    order["计划发车_分钟"] = 360
    order["行驶参数"] = {"平均速度_kmh": 60, "早高峰速度_kmh": 30}
    order["路线GeoJSON"]["features"][0]["geometry"]["coordinates"] = [[104.0, 30.0], [104.05, 30.0], [104.1, 30.0]]
    stops = [{"number": 1, "coordinate": [104.05, 30.0], "earliest": 375, "service": 8},
             {"number": 2, "coordinate": [104.1, 30.0], "earliest": 0, "service": 12}]
    timeline, pauses = route_motion_plan(order, stops)
    assert len(pauses) == 2
    assert pauses[0]["wait_minutes"] > 0
    assert pauses[0]["service_minutes"] == 8
    assert timeline[1][:2] == timeline[2][:2]
    assert timeline[2][2] - timeline[1][2] == pytest.approx(60 * (pauses[0]["wait_minutes"] + 8))
    assert timeline[-1][2] - timeline[-2][2] == pytest.approx(12 * 60)


def test_stop_data_uses_confirmed_route_without_customer_identity(monkeypatch, tmp_path):
    from 功能组件_页面共用代码 import order_state

    db = tmp_path / "orders.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE delivery_batches (delivery_day TEXT, payload TEXT)")
        conn.execute("CREATE TABLE orders (order_id TEXT, payload TEXT)")
        route = {"线路编号": "R1", "订单编号列表": ["A", "B"], "路线GeoJSON": {"features": [
            {"geometry": {"coordinates": [[104.0, 30.0], [104.05, 30.0]]}},
            {"geometry": {"coordinates": [[104.05, 30.0], [104.1, 30.0]]}},
        ]}}
        conn.execute("INSERT INTO delivery_batches VALUES (?, ?)", ("2026-10-16", json.dumps({"线路": [route]})))
        for oid, service in (("A", 8), ("B", 12)):
            conn.execute("INSERT INTO orders VALUES (?, ?)", (oid, json.dumps({"订单编号": oid, "客户名称": oid,
                "期望窗开始_分钟": 360, "服务时间_分钟": service})))
    monkeypatch.setattr(order_state, "_read_db_connection", lambda: sqlite3.connect(db))
    stops = route_stop_data({"订单编号": "B", "线路编号": "R1", "配送顺序": 2, "期望送达日期": "2026-10-16"})
    assert [stop["service"] for stop in stops] == [8, 12]
    assert [stop["number"] for stop in stops] == [1, 2]
    assert all("客户名称" not in stop and "订单编号" not in stop for stop in stops)


def test_non_dijkstra_route_is_rejected():
    order, departed = _order()
    order["路线GeoJSON"]["features"][0]["properties"]["route_mode"] = "演示坐标连线"
    assert get_tracking_snapshot(order, now=departed) is None


def test_delivered_vehicle_is_fixed_at_destination():
    order, departed = _order(status="已送达")
    snapshot = get_tracking_snapshot(order, now=departed)
    assert snapshot and snapshot["progress"] == 1.0 and snapshot["remaining_km"] == 0.0


def test_arrival_risk_uses_service_completion_time():
    order, departed = _order()
    snapshot = {"eta_latest": departed.replace(hour=12, minute=25)}
    level, _ = arrival_risk(order, snapshot)
    assert level == "error"


@pytest.mark.parametrize("hour,minute,distance", [(6,59,1.5), (7,0,1.0), (8,59,1.5), (9,0,2.0)])
def test_tracking_uses_split_peak_speed(hour, minute, distance):
    order, departed = _order()
    departed = departed.replace(hour=hour, minute=minute)
    order["发车时间"] = departed.isoformat()
    snapshot = get_tracking_snapshot(order, now=departed+timedelta(minutes=2), speed_kmh=60, peak_speed_kmh=30, demo_factor=1)
    assert snapshot["travelled_km"] == pytest.approx(distance, abs=1e-6)
