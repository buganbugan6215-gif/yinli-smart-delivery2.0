# 云端货车路网

chengdu_truck.json.gz 包含道路节点、方向、长度和几何，不含客户姓名、电话或订单。当前路网来源及范围以同目录的 路网来源.json 为准；计算路网与地图展示路网由 制作工具/build_expanded_network.py 从该来源生成。

坐标系 EPSG:4326，边权单位米。云端通过 SciPy 的有向 Dijkstra 计算业务点道路距离，节点吸附连接段长度另行计入，不用客户间直线距离替代道路距离。

道路底图归属 © OpenStreetMap contributors，ODbL 1.0。参见 https://www.openstreetmap.org/copyright 。离线重新生成需要 GeoPandas；网站运行不需要。
