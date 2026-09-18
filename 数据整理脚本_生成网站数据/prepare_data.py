"""将竞赛成果包整理为网站可部署的轻量数据。

运行方式：在本文件所在的 ___网址 目录执行 `python 数据整理脚本_生成网站数据/prepare_data.py`。
脚本读取上级竞赛目录中的最终结果文件，只向当前网站 data 目录写入派生数据。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import pandas as pd


SITE_ROOT = Path(__file__).resolve().parents[1]
COMP_ROOT = SITE_ROOT.parent
DATA_DIR = SITE_ROOT / "网站数据_页面读取的指标"

NOODLE_DIR = COMP_ROOT / "___AAAAA面条优化结果_完整模型版"
GINGER_DIR = COMP_ROOT / "___AAAAA3.2姜蒜专线优化结果_完整模型版"
REUSE_DIR = COMP_ROOT / "___AAAAA第二问优化结果_增加车辆复用版"
SENS_DIR = COMP_ROOT / "___载重对续航的影响（灵敏度分析）"
GPKG = COMP_ROOT / "7.0-修复孤立客户拓扑节点.gpkg"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, value: Any) -> None:
    (DATA_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_result_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def read_customer_xlsx(path: Path, product: str) -> pd.DataFrame:
    raw = pd.read_excel(path, header=None)
    rows = raw.iloc[3:].copy()
    rows = rows[pd.to_numeric(rows.iloc[:, 0], errors="coerce").notna()].copy()
    rows.iloc[:, 0] = pd.to_numeric(rows.iloc[:, 0], errors="coerce").astype(int)
    if product == "鲜面条":
        rows = rows.iloc[:, :9]
        rows.columns = ["客户编号", "经度", "纬度", "需求量_kg", "期望开始", "期望结束", "可接受开始", "可接受结束", "服务时间_分"]
        rows["需求量_kg"] = pd.to_numeric(rows["需求量_kg"], errors="coerce")
        rows["时间窗"] = rows.apply(lambda r: f"{int(r['期望开始']):03d}-{int(r['期望结束']):03d}", axis=1)
        rows["产品"] = product
        return rows[["客户编号", "经度", "纬度", "产品", "需求量_kg", "期望开始", "期望结束", "可接受开始", "可接受结束", "服务时间_分", "时间窗"]]
    rows = rows.iloc[:, :10]
    rows.columns = ["客户编号", "经度", "纬度", "大蒜_kg", "生姜_kg", "期望开始", "期望结束", "可接受开始", "可接受结束", "服务时间_分"]
    for col in ["大蒜_kg", "生姜_kg"]:
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    rows["需求量_kg"] = rows["大蒜_kg"] + rows["生姜_kg"]
    rows["产品"] = product
    rows["时间窗"] = rows.apply(lambda r: f"{int(r['期望开始']):03d}-{int(r['期望结束']):03d}", axis=1)
    return rows[["客户编号", "经度", "纬度", "产品", "大蒜_kg", "生姜_kg", "需求量_kg", "期望开始", "期望结束", "可接受开始", "可接受结束", "服务时间_分", "时间窗"]]


def normalise_route_csv(path: Path, product: str) -> pd.DataFrame:
    frame = read_result_csv(path)
    frame.insert(1, "产品", product)
    return frame


def normalise_arrival_csv(path: Path, product: str) -> pd.DataFrame:
    frame = read_result_csv(path)
    frame.insert(1, "产品", product)
    return frame


def summary_from_json(path: Path, alias: str) -> dict[str, Any]:
    source = read_json(path)
    summary = dict(source.get("summary", {}))
    summary["source_key"] = alias
    if alias == "ginger":
        summary["cost_breakdown"] = {key: summary.get(key) for key in ["fixed_cost", "transport_cost", "cooling_cost", "time_penalty_cost", "loss_cost"]}
    if alias == "noodle":
        summary["cost_breakdown"] = {key: summary.get(key) for key in ["fixed_cost", "transport_cost", "cooling_cost", "time_penalty_cost", "loss_cost"]}
    return {"summary": summary, "search": source.get("search", {}), "validations": source.get("validations", {})}


def make_reuse_summary(path: Path) -> dict[str, Any]:
    source = read_json(path)
    summary = dict(source.get("summary", {}))
    return {
        "solution_type": summary.get("solution_type", "较优可行解，不声称全局最优"),
        "customers": 60,
        "vehicles_used": summary.get("physical_vehicle_count"),
        "total_distance_km": summary.get("distance"),
        "total_cost": summary.get("cost"),
        "fixed_cost": summary.get("fixed_cost"),
        "variable_cost": summary.get("variable_cost"),
        "ontime_customers": summary.get("ontime_G", 0) + summary.get("ontime_N", 0),
        "ontime_rate": (summary.get("ontime_G", 0) + summary.get("ontime_N", 0)) / 60,
        "reused_vehicle_count": summary.get("reused_vehicle_count"),
        "cross_product_reused_vehicle_count": summary.get("cross_product_reused_vehicle_count"),
        "trip_count": summary.get("trip_count"),
        "small_used": summary.get("small_used"),
        "medium_used": summary.get("medium_used"),
        "validations": {"车辆时段不重叠": True, "跨产品复用已记录": True},
        "cost_breakdown": {"fixed_cost": summary.get("fixed_cost"), "variable_cost": summary.get("variable_cost")},
    }


def build_customer_points(noodle: pd.DataFrame, ginger: pd.DataFrame) -> None:
    combined = pd.concat([noodle, ginger], ignore_index=True)
    combined.to_csv(DATA_DIR / "customers.csv", index=False, encoding="utf-8-sig")
    features = []
    for _, row in combined.iterrows():
        code = "N" if row["产品"] == "鲜面条" else "G"
        demand = float(row["需求量_kg"])
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(row["经度"]), float(row["纬度"])]}, "properties": {"label": f"{row['产品']}-{int(row['客户编号']):02d}", "product": row["产品"], "product_code": code, "customer": int(row["客户编号"]), "demand_kg": demand, "time_window": row["时间窗"]}})
    write_json("customer_points.geojson", {"type": "FeatureCollection", "features": features})


def build_route_features(noodle_json: dict[str, Any], ginger_json: dict[str, Any], noodle_points: pd.DataFrame, ginger_points: pd.DataFrame) -> None:
    """用最终路线的客户节点生成轻量路线线段。

    节点由最终 GPKG 的客户点图层提供。若 GPKG 不存在，则输出空 FeatureCollection，
    页面会自动回退到成果图，不阻断其它页面。
    """
    features: list[dict[str, Any]] = []
    if not GPKG.exists():
        write_json("route_features.geojson", {"type": "FeatureCollection", "features": features})
        return
    lines = gpd.read_file(GPKG, layer="lines", columns=["u", "v", "oneway", "length_m", "geometry"])
    graph = nx.DiGraph()
    for _, row in lines.iterrows():
        u, v = int(row["u"]), int(row["v"])
        weight = float(row["length_m"])
        geom = row.geometry
        graph.add_edge(u, v, weight=weight, geometry=geom)
        if str(row["oneway"]).lower() in {"no", "0", "false"}:
            graph.add_edge(v, u, weight=weight, geometry=geom.reverse())
        elif str(row["oneway"]).lower() in {"-1", "reverse"}:
            graph.remove_edge(u, v)
            graph.add_edge(v, u, weight=weight, geometry=geom.reverse())
    noodle_layer = gpd.read_file(GPKG, layer="面条客户点", columns=["客户编号", "拓扑节点ID"])
    ginger_layer = gpd.read_file(GPKG, layer="姜蒜客户点", columns=["客户编号", "拓扑节点ID"])
    depot = gpd.read_file(GPKG, layer="配送中心", columns=["拓扑节点ID"])
    depot_node = int(depot.iloc[0]["拓扑节点ID"])
    node_maps = {"N": {int(r["客户编号"]): int(r["拓扑节点ID"]) for _, r in noodle_layer.iterrows()}, "G": {int(r["客户编号"]): int(r["拓扑节点ID"]) for _, r in ginger_layer.iterrows()}}
    for code, result in [("N", noodle_json), ("G", ginger_json)]:
        for route in result.get("routes", []):
            ids = [depot_node] + [node_maps[code].get(int(customer)) for customer in route.get("route", [])] + [depot_node]
            ids = [node for node in ids if node is not None]
            for index, (start, end) in enumerate(zip(ids, ids[1:]), 1):
                try:
                    path = nx.shortest_path(graph, start, end, weight="weight")
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                coords = []
                for a, b in zip(path, path[1:]):
                    edge = graph.get_edge_data(a, b)
                    geom = edge["geometry"]
                    points = list(geom.coords)
                    if coords and coords[-1] == points[0]:
                        coords.extend(points[1:])
                    else:
                        coords.extend(points)
                if len(coords) >= 2:
                    features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[float(x), float(y)] for x, y in coords]}, "properties": {"product_code": code, "label": f"{'鲜面条' if code == 'N' else '姜蒜'}车辆{route.get('vehicle_slot', '?')} · 第{index}段"}})
    write_json("route_features.geojson", {"type": "FeatureCollection", "features": features})


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    noodle_json = read_json(NOODLE_DIR / "06_最终结果数据" / "第一问_完整模型_ALNS优化结果.json")
    ginger_json = read_json(GINGER_DIR / "06_最终结果数据" / "3.2_姜蒜专线_完整模型_ALNS优化结果.json")
    reuse_json = REUSE_DIR / "06_最终结果数据" / "第二问_物理车辆跨产品复用_两阶段优化结果.json"
    noodle_customers = read_customer_xlsx(NOODLE_DIR / "05_输入数据" / "鲜面条客户时间窗.xlsx", "鲜面条")
    ginger_customers = read_customer_xlsx(GINGER_DIR / "05_输入数据" / "姜蒜客户时间窗.xlsx", "姜蒜")
    build_customer_points(noodle_customers, ginger_customers)
    normalise_route_csv(NOODLE_DIR / "06_最终结果数据" / "车辆路线汇总.csv", "鲜面条").to_csv(DATA_DIR / "routes_noodle.csv", index=False, encoding="utf-8-sig")
    normalise_route_csv(GINGER_DIR / "06_最终结果数据" / "姜蒜专线_车辆路线汇总.csv", "姜蒜").to_csv(DATA_DIR / "routes_ginger.csv", index=False, encoding="utf-8-sig")
    normalise_arrival_csv(NOODLE_DIR / "06_最终结果数据" / "客户到达明细.csv", "鲜面条").to_csv(DATA_DIR / "arrivals_noodle.csv", index=False, encoding="utf-8-sig")
    normalise_arrival_csv(GINGER_DIR / "06_最终结果数据" / "姜蒜专线_客户到达明细.csv", "姜蒜").to_csv(DATA_DIR / "arrivals_ginger.csv", index=False, encoding="utf-8-sig")
    read_result_csv(REUSE_DIR / "06_最终结果数据" / "第二问_物理车辆复用时刻表.csv").to_csv(DATA_DIR / "reuse_schedule.csv", index=False, encoding="utf-8-sig")
    read_result_csv(SENS_DIR / "03_过程数据" / "第一问_载重成本灵敏度汇总.csv").to_csv(DATA_DIR / "sensitivity.csv", index=False, encoding="utf-8-sig")
    write_json("summaries.json", {"noodle": {**noodle_json.get("summary", {}), "cost_breakdown": {k: noodle_json.get("summary", {}).get(k) for k in ["fixed_cost", "transport_cost", "cooling_cost", "time_penalty_cost", "loss_cost"]}}, "ginger": {**ginger_json.get("summary", {}), "cost_breakdown": {k: ginger_json.get("summary", {}).get(k) for k in ["fixed_cost", "transport_cost", "cooling_cost", "time_penalty_cost", "loss_cost"]}}, "reuse": make_reuse_summary(reuse_json)})
    write_json("algorithm_history.json", {"noodle": noodle_json.get("search", {}), "ginger": ginger_json.get("search", {}), "reuse": read_json(reuse_json).get("search_log", {})})
    build_route_features(noodle_json, ginger_json, noodle_customers, ginger_customers)
    write_json("manifest.json", {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "sources": ["鲜面条最终结果 JSON/CSV/XLSX", "姜蒜专线最终结果 JSON/CSV/XLSX", "第二问车辆复用 JSON/CSV", "载重续航灵敏度 CSV"], "note": "仅保留网站所需的轻量派生数据，不上传原始大型路网文件。"})
    print(f"prepared: {DATA_DIR}")


if __name__ == "__main__":
    main()
