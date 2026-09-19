"""按订单坐标吸附到既有货车路网节点，并计算配送中心至订单点的 Dijkstra 最短路。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import Point

DEPOT_LON, DEPOT_LAT = 104.26104981303031, 30.851137170192068


def make_graph(lines: gpd.GeoDataFrame) -> tuple[nx.DiGraph, dict[int, tuple[float, float]]]:
    graph = nx.DiGraph()
    coordinates: dict[int, tuple[float, float]] = {}
    for row in lines.itertuples(index=False):
        u, v, length = int(row.u), int(row.v), float(row.length_m)
        coords = list(row.geometry.coords)
        coordinates.setdefault(u, coords[0]); coordinates.setdefault(v, coords[-1])
        direction = str(row.oneway).strip().lower()
        if direction in {"yes", "no"}:
            graph.add_edge(u, v, weight=length, geometry=coords)
        if direction in {"-1", "no"}:
            graph.add_edge(v, u, weight=length, geometry=list(reversed(coords)))
    return graph, coordinates


def nearest_node(point: Point, coordinates: dict[int, tuple[float, float]], crs) -> tuple[int, float]:
    nodes = gpd.GeoDataFrame({"node_id": list(coordinates)}, geometry=[Point(value) for value in coordinates.values()], crs=crs).to_crs(3857)
    projected = gpd.GeoSeries([point], crs=crs).to_crs(3857).iloc[0]
    distances = nodes.geometry.distance(projected)
    idx = distances.idxmin()
    return int(nodes.at[idx, "node_id"]), float(distances.at[idx])


def route_coordinates(graph: nx.DiGraph, node_path: list[int], start: Point, end: Point) -> list[tuple[float, float]]:
    output = [(start.x, start.y)]
    for u, v in zip(node_path[:-1], node_path[1:]):
        coords = graph[u][v]["geometry"]
        output.extend(coords if output[-1] != coords[0] else coords[1:])
    output.append((end.x, end.y))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", required=True)
    parser.add_argument("--road-gpkg", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    orders = pd.read_excel(args.orders)
    required = {"订单编号", "经度", "纬度"}
    missing = required - set(orders.columns)
    if missing:
        raise ValueError(f"orders.xlsx 缺少字段：{', '.join(sorted(missing))}")
    lines = gpd.read_file(args.road_gpkg, layer="lines")
    graph, coordinates = make_graph(lines)
    depot = Point(DEPOT_LON, DEPOT_LAT)
    depot_node, depot_snap = nearest_node(depot, coordinates, lines.crs)
    labels = ["配送中心"] + orders["订单编号"].astype(str).tolist()
    business_points = [depot] + [Point(float(row["经度"]), float(row["纬度"])) for _, row in orders.iterrows()]
    business_nodes = [depot_node]
    snap_distances = [depot_snap]
    for point in business_points[1:]:
        node, snap_distance = nearest_node(point, coordinates, lines.crs)
        business_nodes.append(node)
        snap_distances.append(snap_distance)
    matrix = [[0.0 for _ in labels] for _ in labels]
    # 对每一个业务点跑一次单源 Dijkstra，构成有向完整距离矩阵。
    for source_index, source_node in enumerate(business_nodes):
        lengths = nx.single_source_dijkstra_path_length(graph, source_node, weight="weight")
        for target_index, target_node in enumerate(business_nodes):
            if source_index == target_index:
                continue
            if target_node not in lengths:
                raise RuntimeError(f"从 {labels[source_index]} 到 {labels[target_index]} 在货车路网中不可达")
            matrix[source_index][target_index] = float(lengths[target_node] + snap_distances[source_index] + snap_distances[target_index])
    features = []
    results = []
    for position, row in orders.reset_index(drop=True).iterrows():
        target = business_points[position + 1]
        target_node, target_snap = business_nodes[position + 1], snap_distances[position + 1]
        try:
            distance, path = nx.single_source_dijkstra(graph, depot_node, target_node, weight="weight")
        except nx.NetworkXNoPath as exc:
            raise RuntimeError(f"订单 {row['订单编号']} 无法通过货车路网到达") from exc
        total_m = float(distance + depot_snap + target_snap)
        geometry = {"type": "LineString", "coordinates": route_coordinates(graph, path, depot, target)}
        feature = {"type": "Feature", "properties": {"订单编号": str(row["订单编号"]), "route_mode": "Dijkstra路网最短路径", "路网最短距离_m": round(total_m, 1), "配送中心吸附距离_m": round(depot_snap, 1), "客户吸附距离_m": round(target_snap, 1)}, "geometry": geometry}
        features.append(feature)
        results.append({"订单编号": str(row["订单编号"]), "路线GeoJSON": {"type": "FeatureCollection", "features": [feature]}, "路网最短距离_km": round(total_m / 1000, 3), "求解模式": "Dijkstra路网最短路径", "路网节点": {"配送中心": depot_node, "客户": target_node}})
    output = {"求解模式": "Dijkstra路网最短路径", "订单结果": results, "路线GeoJSON": {"type": "FeatureCollection", "features": features}}
    if len(results) == 1:
        output.update(results[0])
    (out / "formal_result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    frame = pd.DataFrame(matrix, index=labels, columns=labels)
    frame.to_excel(out / "distance_matrix.xlsx", sheet_name="Dijkstra距离矩阵")
    (out / "route_map.geojson").write_text(json.dumps(output["路线GeoJSON"], ensure_ascii=False), encoding="utf-8")
    print(f"完成：{len(results)} 个订单，结果目录：{out}")


if __name__ == "__main__":
    main()
