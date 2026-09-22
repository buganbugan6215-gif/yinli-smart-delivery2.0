from datetime import datetime, timedelta

from 功能组件_页面共用代码.gps_simulator import arrival_risk, get_tracking_snapshot, route_coordinates


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
