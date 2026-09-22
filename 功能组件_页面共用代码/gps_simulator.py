"""沿已确认 Dijkstra 路线生成车辆位置、剩余里程和动态 ETA。"""
from __future__ import annotations

from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any

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
    speed_kmh: float = 30.0,
    demo_factor: float = 60.0,
) -> dict[str, Any] | None:
    """返回配送快照；仅接受正式 Dijkstra 路线，不伪造无路线订单的位置。"""
    if not order or not is_dijkstra_route(order):
        return None
    coordinates = route_coordinates(order.get("路线GeoJSON"))
    if len(coordinates) < 2 or speed_kmh <= 0 or demo_factor <= 0:
        return None
    try:
        departed_at = datetime.fromisoformat(str(order["发车时间"]))
    except (KeyError, TypeError, ValueError):
        return None

    current_time = now or datetime.now()
    cumulative = _cumulative_distances(coordinates)
    total_km = cumulative[-1]
    if total_km <= 0:
        return None

    status = str(order.get("状态", ""))
    if status in {"已送达", "签收完成"}:
        progress = 1.0
    elif status != "配送途中":
        return None
    else:
        simulated_hours = max(0.0, (current_time - departed_at).total_seconds()) / 3600 * demo_factor
        progress = min(1.0, simulated_hours * speed_kmh / total_km)

    travelled_km = total_km * progress
    remaining_km = max(0.0, total_km - travelled_km)
    remaining_minutes = remaining_km / speed_kmh * 60
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
