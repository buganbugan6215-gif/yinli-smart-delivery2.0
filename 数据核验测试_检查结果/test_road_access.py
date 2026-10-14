"""都江堰校区附近的孤立道路不得让可配送地址误报不可达。"""

import numpy as np
from scipy.sparse.csgraph import dijkstra

from 功能组件_页面共用代码.batch_solver import (
    DEPOT, haversine_m, load_graph, routable_nodes,
)


def test_dujiangyan_campus_snaps_to_round_trip_road_network():
    # 四川农业大学都江堰校区附近的 WGS84 坐标；只验证路网吸附，不代替订单地理编码。
    campus = np.array([103.620588, 31.006894])
    graph, _, coords, all_tree, scale, _ = load_graph()
    depot = int(all_tree.query(np.asarray(DEPOT) * scale)[1])
    nearest = int(all_tree.query(campus * scale)[1])
    available, route_tree = routable_nodes()
    routed = int(available[route_tree.query(campus * scale)[1]])

    assert haversine_m(campus, coords[routed]) < 3000
    assert nearest != routed  # 最近的原始节点在孤立路段上。
    assert np.isfinite(dijkstra(graph, directed=True, indices=depot)[routed])
    assert np.isfinite(dijkstra(graph, directed=True, indices=routed)[depot])
