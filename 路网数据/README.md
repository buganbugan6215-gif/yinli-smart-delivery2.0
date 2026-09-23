# 云端货车路网

`chengdu_truck.json.gz` 来自现有竞赛文件 `7.0-修复孤立客户拓扑节点.gpkg` 的 lines 图层，保留 134007 条道路的节点、方向、长度和道路几何。只含道路，不含客户姓名、电话或订单。

坐标系 EPSG:4326，边权单位米。文件内包含原始文件 SHA-256。压缩后约 6.7 MB；云端通过 SciPy 的有向 Dijkstra 计算所有业务点的完整距离矩阵，节点吸附连接段长度另行计入，不用客户间直线距离替代道路距离。

道路底图归属 © OpenStreetMap contributors，ODbL 1.0。参见 https://www.openstreetmap.org/copyright 。竞赛路网的预处理与客户点接入沿用已有成果。

重新提取：`python 制作工具/build_road_graph.py --source 路网文件.gpkg --output 路网数据/chengdu_truck.json.gz`（该离线制作步骤需要 GeoPandas；网页运行无需 GeoPandas）。
