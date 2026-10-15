"""识别已确认订单是否使用 Dijkstra 道路路线。"""
from __future__ import annotations

from typing import Any


def is_dijkstra_route(order: dict[str, Any]) -> bool:
    route = order.get("路线GeoJSON") or {}
    features = route.get("features") if isinstance(route, dict) else None
    if not features:
        return False
    return all(str(feature.get("properties", {}).get("route_mode", "")).startswith("Dijkstra") for feature in features)
