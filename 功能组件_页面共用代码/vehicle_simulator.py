"""沿已确认 Dijkstra 路线生成车辆位置、剩余里程和动态 ETA。"""
from __future__ import annotations

RELEASE_VERSION = "2026-10-15-smooth-stops-v39"

from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any

from 功能组件_页面共用代码.delivery_calendar import as_beijing
from 功能组件_页面共用代码.formal_dispatch import is_dijkstra_route


def route_coordinates(route_geojson: dict[str, Any] | None) -> list[list[float]]:
    """按 GeoJSON 顺序展开 LineString/MultiLineString，并去掉相邻重复点。"""
    coordinates: list[list[float]] = []
    if not isinstance(route_geojson, dict):
        return coordinates
    for feature in route_geojson.get("features", []):
        geometry = feature.get("geometry", {}) if isinstance(feature, dict) else {}
        geometry_type = geometry.get("type")
        if geometry_type == "LineString":
            lines = [geometry.get("coordinates", [])]
        elif geometry_type == "MultiLineString":
            lines = geometry.get("coordinates", [])
        else:
            continue
        for line in lines:
            for point in line:
                try:
                    normalized = [float(point[0]), float(point[1])]
                except (IndexError, TypeError, ValueError):
                    continue
                if not coordinates or normalized != coordinates[-1]:
                    coordinates.append(normalized)
    return coordinates


def _haversine_km(first: list[float], second: list[float]) -> float:
    lon1, lat1, lon2, lat2 = map(radians, (first[0], first[1], second[0], second[1]))
    dlon, dlat = lon2 - lon1, lat2 - lat1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(value))


def _cumulative_distances(coordinates: list[list[float]]) -> list[float]:
    cumulative = [0.0]
    for start, end in zip(coordinates, coordinates[1:]):
        cumulative.append(cumulative[-1] + _haversine_km(start, end))
    return cumulative


def route_motion_plan(order: dict[str, Any], stops: list[dict[str, Any]] | None = None) -> tuple[list[list[float]], list[dict[str, Any]]]:
    """道路行驶与逐站等待、服务共用一条时间轴。"""
    if not is_dijkstra_route(order):
        return [], []
    from 功能组件_页面共用代码.batch_solver import travel_minutes
    from 功能组件_页面共用代码.order_state import pricing_settings

    rates = order.get("行驶参数") or pricing_settings()
    normal = float(rates["平均速度_kmh"])
    peak = float(rates["早高峰速度_kmh"])
    coordinates = route_coordinates(order.get("路线GeoJSON"))
    if len(coordinates) < 2 or min(normal, peak) <= 0:
        return [], []
    stops = stops or []
    clock = float(stops[0].get("departure_minute", order.get("计划发车_分钟", 0))) if stops else float(order.get("计划发车_分钟", 0))
    elapsed_seconds = 0.0
    timeline = [[coordinates[0][1], coordinates[0][0], 0.0]]
    next_stop = 0
    pauses = []
    leg_end = 0
    leg_km = None
    leg_minutes = leg_geometry_km = 0.0
    for index, (start, end) in enumerate(zip(coordinates, coordinates[1:]), 1):
        if next_stop < len(stops) and index > leg_end:
            leg_end = next((j for j in range(index, len(coordinates))
                            if coordinates[j] == stops[next_stop]["coordinate"]), 0)
            leg_km = stops[next_stop].get("leg_km")
            if leg_end and leg_km is not None:
                leg_geometry_km = sum(_haversine_km(coordinates[j - 1], coordinates[j])
                                      for j in range(index, leg_end + 1))
                leg_minutes = travel_minutes(float(leg_km), clock, normal, peak)
        geometry_km = _haversine_km(start, end)
        minutes = (leg_minutes * geometry_km / leg_geometry_km
                   if leg_end and leg_km is not None and leg_geometry_km > 0
                   else travel_minutes(geometry_km, clock, normal, peak))
        elapsed_seconds += minutes * 60
        clock += minutes
        timeline.append([end[1], end[0], elapsed_seconds])
        if next_stop < len(stops) and end == stops[next_stop]["coordinate"]:
            stop = stops[next_stop]
            wait = max(0.0, float(stop["earliest"]) - clock)
            service = max(0.0, float(stop["service"]))
            dwell = wait + service
            pauses.append({"number": int(stop["number"]), "coordinate": end,
                           "wait_minutes": wait, "service_minutes": service,
                           "arrival_seconds": elapsed_seconds, "departure_seconds": elapsed_seconds + dwell * 60})
            if dwell:
                elapsed_seconds += dwell * 60
                clock += dwell
                timeline.append([end[1], end[0], elapsed_seconds])
            next_stop += 1
            leg_end = 0
    return timeline, pauses


def route_motion_timeline(order: dict[str, Any], stops: list[dict[str, Any]] | None = None) -> list[list[float]]:
    return route_motion_plan(order, stops)[0]


def route_stop_data(order: dict[str, Any]) -> list[dict[str, Any]]:
    """从已确认线路读取到本单为止的站点，仅返回序号、坐标和时长。"""
    if not order.get("线路编号") or not order.get("配送顺序"):
        return []
    import json
    from 功能组件_页面共用代码.order_state import _read_db_connection

    with _read_db_connection() as conn:
        row = conn.execute("SELECT payload FROM delivery_batches WHERE delivery_day=?",
                           (str(order["期望送达日期"]),)).fetchone()
        if not row:
            return []
        plan = json.loads(row[0])
        route = next((r for r in plan.get("线路", []) if r["线路编号"] == order["线路编号"]), None)
        if not route or order["订单编号"] not in route["订单编号列表"]:
            return []
        route_ids = route["订单编号列表"]
        limit = route_ids.index(order["订单编号"]) + 1
        ids = route_ids[:limit]
        placeholders = ",".join("?" for _ in route_ids)
        records = {item["订单编号"]: item for (payload,) in conn.execute(
            f"SELECT payload FROM orders WHERE order_id IN ({placeholders})", tuple(route_ids)).fetchall()
            if (item := json.loads(payload))}
    features = route.get("路线GeoJSON", {}).get("features", [])
    if len(features) < limit or any(oid not in records for oid in ids):
        return []
    from 功能组件_页面共用代码.arrival_estimate import estimate_from_plan

    estimate = estimate_from_plan(order, plan, list(records.values()))
    departure = estimate["发车_分钟"] if estimate else float(order.get("计划发车_分钟", 0))
    labels = {label: index for index, label in enumerate(plan.get("矩阵标签", []))}
    previous = 0 if route.get("仓库编号", "D0") == "D0" else labels.get("新增配送点")
    stops = []
    for number, (oid, feature) in enumerate(zip(ids, features), 1):
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if not coordinates:
            return []
        stop = {"number": number, "coordinate": list(map(float, coordinates[-1][:2])),
                "earliest": float(records[oid]["期望窗开始_分钟"]),
                "service": float(records[oid]["服务时间_分钟"]), "departure_minute": departure}
        index = labels.get(oid)
        if previous is not None and index is not None:
            try:
                stop["leg_km"] = float(plan["距离矩阵_m"][previous][index]) / 1000
            except (KeyError, IndexError, TypeError, ValueError):
                pass
        previous = index
        stops.append(stop)
    return stops


def _position_at_distance(
    coordinates: list[list[float]], cumulative: list[float], target_km: float
) -> tuple[float, float]:
    if target_km <= 0:
        return coordinates[0][0], coordinates[0][1]
    if target_km >= cumulative[-1]:
        return coordinates[-1][0], coordinates[-1][1]
    for index in range(1, len(cumulative)):
        if target_km <= cumulative[index]:
            segment = cumulative[index] - cumulative[index - 1]
            ratio = 0.0 if segment <= 0 else (target_km - cumulative[index - 1]) / segment
            lon1, lat1 = coordinates[index - 1]
            lon2, lat2 = coordinates[index]
            return lon1 + ratio * (lon2 - lon1), lat1 + ratio * (lat2 - lat1)
    return coordinates[-1][0], coordinates[-1][1]


def get_tracking_snapshot(
    order: dict[str, Any],
    *,
    now: datetime | None = None,
    speed_kmh: float | None = None,
    peak_speed_kmh: float | None = None,
    demo_factor: float = 60.0,
) -> dict[str, Any] | None:
    """返回配送快照；仅接受正式 Dijkstra 路线，不伪造无路线订单的位置。"""
    if not order or not is_dijkstra_route(order):
        return None
    from 功能组件_页面共用代码.order_state import pricing_settings
    from 功能组件_页面共用代码.batch_solver import travel_minutes
    if speed_kmh is None:
        rates = order.get("行驶参数") or pricing_settings()
        speed_kmh = rates["平均速度_kmh"]
        peak_speed_kmh = rates["早高峰速度_kmh"] if peak_speed_kmh is None else peak_speed_kmh
    elif peak_speed_kmh is None:
        peak_speed_kmh = speed_kmh
    coordinates = route_coordinates(order.get("路线GeoJSON"))
    if len(coordinates) < 2 or min(speed_kmh, peak_speed_kmh) <= 0 or demo_factor <= 0:
        return None
    try:
        departed_at = datetime.fromisoformat(str(order["发车时间"]))
    except (KeyError, TypeError, ValueError):
        return None

    current_time = as_beijing(now)
    departed_at = as_beijing(departed_at)
    cumulative = _cumulative_distances(coordinates)
    total_km = cumulative[-1]
    if total_km <= 0:
        return None

    status = str(order.get("状态", ""))
    start_minute = departed_at.hour * 60 + departed_at.minute + departed_at.second / 60
    elapsed = max(0.0, (current_time - departed_at).total_seconds()) / 60 * demo_factor
    if status in {"已送达", "签收完成"}:
        progress = 1.0
    elif status != "配送途中":
        return None
    else:
        duration = travel_minutes(total_km, start_minute, speed_kmh, peak_speed_kmh)
        if elapsed >= duration:
            progress = 1.0
        else:
            low, high = 0.0, total_km
            for _ in range(35):
                mid = (low + high) / 2
                if travel_minutes(mid, start_minute, speed_kmh, peak_speed_kmh) <= elapsed:
                    low = mid
                else:
                    high = mid
            progress = low / total_km

    travelled_km = total_km * progress
    remaining_km = max(0.0, total_km - travelled_km)
    remaining_minutes = travel_minutes(remaining_km, start_minute + elapsed, speed_kmh, peak_speed_kmh)
    eta = current_time + timedelta(minutes=remaining_minutes / demo_factor)
    uncertainty_minutes = max(3.0, min(15.0, 2.0 + remaining_minutes * 0.25))
    longitude, latitude = _position_at_distance(coordinates, cumulative, travelled_km)
    return {
        "longitude": longitude,
        "latitude": latitude,
        "progress": progress,
        "total_km": total_km,
        "travelled_km": travelled_km,
        "remaining_km": remaining_km,
        "remaining_minutes": remaining_minutes,
        "eta": eta,
        "eta_earliest": eta - timedelta(minutes=uncertainty_minutes),
        "eta_latest": eta + timedelta(minutes=uncertainty_minutes),
        "uncertainty_minutes": uncertainty_minutes,
        "is_demo": demo_factor != 1.0,
    }


def arrival_risk(order: dict[str, Any], snapshot: dict[str, Any]) -> tuple[str, str]:
    """按“完成服务”的口径比较动态 ETA 与客户时间窗。"""
    service_minutes = int(float(order.get("服务时间_分钟", 0) or 0))
    completion = snapshot["eta_latest"] + timedelta(minutes=service_minutes)
    completion_minutes = completion.hour * 60 + completion.minute
    preferred_end = int(float(order.get("期望窗结束_分钟", 1439) or 1439))
    acceptable_end = int(float(order.get("允许窗结束_分钟", 1439) or 1439))
    if completion_minutes > acceptable_end:
        return "error", "预计完成服务时间存在超出客户可接受时间窗的风险，请联系客户或调整安排。"
    if completion_minutes > preferred_end:
        return "warning", "预计可能无法在客户期望时间窗内完成服务，但仍处于可接受范围。"
    return "success", "当前预计可在客户期望时间窗内完成服务。"
