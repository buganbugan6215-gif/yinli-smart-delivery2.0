"""一次计算整日有向最短距离矩阵，再构造满足载重、续航、时间窗的配送线路。

道路最短路是 Dijkstra 精确结果；多车线路采用可行插入启发式，不宣称全局最优。
"""
from __future__ import annotations

from functools import lru_cache
import gzip
import json
import math
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

DEPOT = [104.26104981303031, 30.851137170192068]
ROAD_FILE = Path(__file__).resolve().parents[1] / "路网数据" / "chengdu_truck.json.gz"


@lru_cache(maxsize=1)
def load_graph():
    with gzip.open(ROAD_FILE, "rt", encoding="utf-8") as f:
        data = json.load(f)
    nodes, edges = {}, {}
    for u, v, length, direction, coords in data["edges"]:
        if not math.isfinite(length) or length < 0:
            raise ValueError("路网含非法边权。")
        nodes.setdefault(u, coords[0])
        nodes.setdefault(v, coords[-1])
        candidates = []
        if direction in {"no", "yes"}:
            candidates.append((u, v, coords))
        if direction in {"no", "-1"}:
            candidates.append((v, u, coords[::-1]))
        for a, b, geometry in candidates:
            if (a, b) not in edges or length < edges[a, b][0]:
                edges[a, b] = (length, geometry)
    ids = sorted(nodes)
    index = {node: i for i, node in enumerate(ids)}
    edge_map = {(index[a], index[b]): value for (a, b), value in edges.items()}
    rows, cols = zip(*edge_map)
    graph = csr_matrix(([item[0] for item in edge_map.values()], (rows, cols)), shape=(len(ids), len(ids)))
    coordinates = np.array([nodes[node] for node in ids])
    # 成都局部等距近似，仅用于最近节点索引；吸附距离用球面距离复核。
    scale = np.array([math.cos(math.radians(30.7)), 1.0])
    return graph, edge_map, coordinates, cKDTree(coordinates * scale), scale, data["source_sha256"]


def haversine_m(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 12742017.6 * math.asin(min(1.0, math.sqrt(value)))


def travel_minutes(km, start, normal=60.0, peak=30.0):
    if min(normal, peak) <= 0:
        raise ValueError("速度必须大于零。")
    remaining, now = float(km), float(start)
    while remaining > 1e-10:
        day = math.floor(now / 1440) * 1440
        local = now - day
        if local < 420:
            speed, end = normal, day + 420
        elif local < 540:
            speed, end = peak, day + 540
        else:
            speed, end = normal, day + 1440
        covered = min(remaining, (end - now) * speed / 60)
        now += covered * 60 / speed
        remaining -= covered
    return now - start


def route_schedule(sequence, orders, matrix, vehicle, departure, rates):
    load = sum(float(orders[i-1]["配送重量_kg"]) for i in sequence)
    if load > vehicle["capacity"] + 1e-8:
        return None
    km, clock, previous, arrivals = 0.0, departure, 0, []
    for i in sequence:
        order = orders[i-1]
        distance = matrix[previous][i] / 1000
        clock += travel_minutes(distance, clock, rates["平均速度_kmh"], rates["早高峰速度_kmh"])
        clock = max(clock, float(order["期望窗开始_分钟"]))
        if clock > float(order["期望窗结束_分钟"]) + 1e-8:
            return None
        arrivals.append(clock)
        clock += float(order["服务时间_分钟"])
        km += distance
        previous = i
    km += matrix[previous][0] / 1000
    clock += travel_minutes(matrix[previous][0] / 1000, clock, rates["平均速度_kmh"], rates["早高峰速度_kmh"])
    if km > vehicle["range"] + 1e-8 or clock > 1440:
        return None
    return {"km": km, "load": load, "arrivals": arrivals, "return_minute": clock}


def assign_routes(orders, matrix, rates, departure=360):
    vehicles = []
    for kind in ("小型冷藏车", "大型冷藏车"):
        for i in range(int(rates[kind + "数量"])):
            vehicles.append({"id": f"{kind}-{i+1:02d}", "capacity": rates[kind + "载重_kg"],
                             "range": rates[kind + "续航_km"], "fixed": rates[kind + "固定成本_元"],
                             "per_km": rates[kind + "单位运输成本_元每km"], "sequence": []})
    for customer in sorted(range(1, len(orders)+1), key=lambda i: (orders[i-1]["期望窗结束_分钟"], -float(orders[i-1]["配送重量_kg"]))):
        best = None
        for vi, vehicle in enumerate(vehicles):
            old = route_schedule(vehicle["sequence"], orders, matrix, vehicle, departure, rates)
            for pos in range(len(vehicle["sequence"])+1):
                trial = vehicle["sequence"][:pos] + [customer] + vehicle["sequence"][pos:]
                schedule = route_schedule(trial, orders, matrix, vehicle, departure, rates)
                if schedule is None:
                    continue
                increment = (schedule["km"] - old["km"]) * vehicle["per_km"] + (vehicle["fixed"] if not vehicle["sequence"] else 0)
                if best is None or increment < best[0]:
                    best = (increment, vi, trial)
        if best is None:
            raise ValueError(f"未找到覆盖全部订单的可行方案：{orders[customer-1]['订单编号']} 无法插入现有车辆线路。请核对车辆、载重、续航和时间窗；未发布任何部分结果。")
        vehicles[best[1]]["sequence"] = best[2]
    return [v for v in vehicles if v["sequence"]]


def solve_batch(orders, rates, departure=360, progress=None):
    if not orders:
        raise ValueError("本批次没有订单。")
    if not 0 <= departure < 1440:
        raise ValueError("计划发车时间应在配送日内。")
    days = {str(o["期望送达日期"]) for o in orders}
    ids = [str(o["订单编号"]) for o in orders]
    if len(days) != 1 or len(set(ids)) != len(ids):
        raise ValueError("订单日期混杂或订单编号重复。")
    for o in orders:
        if not math.isfinite(float(o["配送重量_kg"])) or float(o["配送重量_kg"]) <= 0:
            raise ValueError("订单重量必须大于零。")
    points = [DEPOT] + [[float(o["经度"]), float(o["纬度"])] for o in orders]
    if any(not all(math.isfinite(v) for v in p) or not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90) for p in points):
        raise ValueError("订单包含非法坐标。")
    graph, edge_map, coords, tree, scale, source_hash = load_graph()
    _, nodes = tree.query(np.array(points)*scale)
    snaps = [haversine_m(p, coords[n]) for p, n in zip(points, nodes)]
    if max(snaps) > 3000:
        raise ValueError("存在距离已知货车路网超过 3 km 的收货点，请先核对地址。")
    labels = ["配送中心"] + ids
    matrix, predecessors = [], []
    for i, node in enumerate(nodes):
        lengths, pred = dijkstra(graph, directed=True, indices=int(node), return_predecessors=True)
        row = [0.0 if points[i] == points[j] else float(lengths[target] + snaps[i] + snaps[j]) for j, target in enumerate(nodes)]
        if not all(math.isfinite(v) for v in row):
            raise ValueError(f"{labels[i]} 与某些订单点在有向货车路网上不可达，请核对坐标和路网。")
        matrix.append(row)
        predecessors.append(pred)
        if progress:
            progress((i+1)/(len(nodes)+1), f"已计算 {i+1}/{len(nodes)} 个业务点的最短路径")
    vehicles = assign_routes(orders, matrix, rates, departure)

    def leg(a, b):
        if points[a] == points[b]:
            return [points[a], points[b]]
        current, source = int(nodes[b]), int(nodes[a])
        path = [current]
        while current != source:
            current = int(predecessors[a][current])
            if current < 0 or len(path) > graph.shape[0]:
                raise ValueError("道路路径重建失败。")
            path.append(current)
        path.reverse()
        result = [points[a], coords[source].tolist()]
        for u, v in zip(path, path[1:]):
            result.extend(edge_map[u, v][1])
        result.append(points[b])
        result = [p for i, p in enumerate(result) if i == 0 or p != result[i-1]]
        return result if len(result) > 1 else result * 2

    day = next(iter(days))
    routes, assignments = [], []
    for vi, vehicle in enumerate(vehicles, 1):
        sequence = vehicle["sequence"]
        route_id = f"YL-{day.replace('-', '')}-{vi:02d}"
        schedule = route_schedule(sequence, orders, matrix, vehicle, departure, rates)
        features, prefix, cumulative, previous = [], [], 0.0, 0
        for stop, i in enumerate(sequence, 1):
            geometry = leg(previous, i)
            prefix.extend(geometry if not prefix else geometry[1:])
            cumulative += matrix[previous][i]/1000
            features.append({"type": "Feature", "properties": {"线路编号": route_id, "订单编号": ids[i-1], "route_mode": "Dijkstra路网最短路径"}, "geometry": {"type": "LineString", "coordinates": geometry}})
            # 客户只获得到自身收货点的道路及自身信息，不携带其他客户标识/站点表。
            own_route = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"线路编号": route_id, "route_mode": "Dijkstra路网最短路径"}, "geometry": {"type": "LineString", "coordinates": list(prefix)}}]}
            assignments.append({"订单编号": ids[i-1], "配送日期": day, "线路编号": route_id,
                                "车辆编号": vehicle["id"], "配送顺序": stop, "计划到达_分钟": schedule["arrivals"][stop-1],
                                "路线GeoJSON": own_route, "路网最短距离_km": cumulative})
            previous = i
        features.append({"type": "Feature", "properties": {"线路编号": route_id, "route_mode": "Dijkstra路网最短路径"}, "geometry": {"type": "LineString", "coordinates": leg(previous, 0)}})
        routes.append({"线路编号": route_id, "车辆编号": vehicle["id"], "订单编号列表": [ids[i-1] for i in sequence],
                       "总重量_kg": schedule["load"], "总里程_km": schedule["km"], "返回时间_分钟": schedule["return_minute"],
                       "路线GeoJSON": {"type": "FeatureCollection", "features": features}})
    if progress:
        progress(1.0, "整日距离矩阵和配送线路已生成")
    return {"配送日期": day, "矩阵标签": labels, "距离矩阵_m": matrix, "线路": routes, "订单结果": assignments,
            "发车分钟": departure, "参数": rates, "路网指纹": source_hash,
            "算法": "有向 Dijkstra 最短路径矩阵 + 载重/续航/时间窗可行插入（非全局最优）"}
