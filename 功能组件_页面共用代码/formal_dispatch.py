"""本机 Dijkstra 精算任务的导出、导入与结果校验。"""
from __future__ import annotations

from io import BytesIO
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
    """生成供企业电脑本机求解器读取的任务压缩包，不包含任何地图密钥。"""
    columns = ["订单编号", "客户名称", "收货地址", "经度", "纬度", "品类", "配送重量_kg", "期望送达日期", "最早到达", "最晚到达", "服务时间_分钟"]
    row = {column: order.get(column, "") for column in columns}
    manifest = {
        "任务类型": "Dijkstra 路网最短路",
        "订单编号": order.get("订单编号"),
        "说明": "使用 7.0-修复孤立客户拓扑节点.gpkg；结果必须写为 formal_result.json。",
        "禁止事项": "不得使用坐标直线距离替代路网最短路径。",
    }
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        xlsx = BytesIO()
        pd.DataFrame([row]).to_excel(xlsx, index=False)
        archive.writestr("orders.xlsx", xlsx.getvalue())
        archive.writestr("job.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("运行说明.txt", "运行：python 路网Dijkstra订单求解.py --orders orders.xlsx --road-gpkg 7.0-修复孤立客户拓扑节点.gpkg --output result\n完成后上传 result/formal_result.json。\n")
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
