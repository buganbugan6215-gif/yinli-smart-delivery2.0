"""本机 Dijkstra 精算任务的导出、导入与结果校验。"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import json
from typing import Any
import zipfile

import pandas as pd


def is_dijkstra_route(order: dict[str, Any]) -> bool:
    route = order.get("路线GeoJSON") or {}
    features = route.get("features") if isinstance(route, dict) else None
    if not features:
        return False
    return all(str(feature.get("properties", {}).get("route_mode", "")).startswith("Dijkstra") for feature in features)


def build_formal_job(order: dict[str, Any]) -> bytes:
    """兼容旧离线单单导出；当前企业工作台使用整日批次计算。"""
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        xlsx = BytesIO()
        pd.DataFrame([order]).to_excel(xlsx, index=False)
        archive.writestr("orders.xlsx", xlsx.getvalue())
        solver = Path(__file__).resolve().parents[1] / "本机正式求解器" / "路网Dijkstra订单求解.py"
        archive.write(solver, "solver.py")
        archive.writestr("运行说明.txt", "旧版离线道路核验工具。当前客户调度请在企业工作台按配送日统一计算。\n解压后运行：python solver.py --orders orders.xlsx --road-gpkg 路网文件.gpkg --output result\n需安装 geopandas、networkx、pandas、openpyxl。\n".encode("utf-8-sig"))
    return output.getvalue()


def parse_formal_result(raw: bytes, filename: str) -> dict[str, Any]:
    """读取本机求解器 formal_result.json，拒绝演示直线结果。"""
    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = archive.namelist()
            name = next((item for item in names if item.endswith("formal_result.json")), None)
            if not name:
                raise ValueError("压缩包中缺少 formal_result.json。")
            payload = json.loads(archive.read(name).decode("utf-8"))
    else:
        payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("正式结果必须是 JSON 对象。")
    route = payload.get("路线GeoJSON")
    if not isinstance(route, dict) or not route.get("features"):
        raise ValueError("正式结果缺少路线GeoJSON。")
    candidate = {"路线GeoJSON": route}
    if not is_dijkstra_route(candidate):
        raise ValueError("路线不是 Dijkstra 路网结果，不能用于发车。")
    return payload
