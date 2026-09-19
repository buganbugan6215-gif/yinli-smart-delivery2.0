import folium
import streamlit as st
from streamlit_folium import st_folium

from 功能组件_页面共用代码.maps import add_customer_points, add_route_features, add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.data_loader import load_site_data
from 功能组件_页面共用代码.formal_dispatch import is_dijkstra_route
from 功能组件_页面共用代码.order_state import DEPOT_LAT, DEPOT_LON, init_orders
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar, require_staff_access


inject_css()
render_sidebar()
require_staff_access()
page_title("运营配送地图", "查看竞赛方案的全量配送网络，并叠加本机演示订单调度线")

data = load_site_data()
orders = init_orders(include_saved=True)
fmap, minor_layer = create_chengdu_map(zoom_start=10)
add_route_features(fmap, data.geojson.get("routes", {}))
add_customer_points(fmap, data.geojson.get("customers", {}))
for order in orders:
    route = order.get("路线GeoJSON")
    if route and is_dijkstra_route(order):
        folium.GeoJson(route, name=f"Dijkstra订单 {order['订单编号']}", style_function=lambda _: {"color": "#ff8133", "weight": 4, "opacity": 0.9}, tooltip=f"Dijkstra订单：{order['订单编号']}").add_to(fmap)
        if order.get("状态") == "配送途中":
            try:
                destination = route["features"][0]["geometry"]["coordinates"][-1]
                folium.Marker(
                    [(DEPOT_LAT + float(destination[1])) / 2, (DEPOT_LON + float(destination[0])) / 2],
                    tooltip=f"{order.get('车辆编号', '配送车辆')} · 配送途中示意位置",
                    icon=folium.Icon(color="orange", icon="truck", prefix="fa"),
                ).add_to(fmap)
            except (KeyError, IndexError, TypeError, ValueError):
                pass
add_zoom_detail_behavior(fmap, minor_layer, threshold=13)
folium.LayerControl(collapsed=True).add_to(fmap)
st_folium(fmap, use_container_width=True, height=650, returned_objects=[])
st.caption("蓝色线路为题目数据中的配送网络，橙色线路为已导入的 Dijkstra 订单路径。车辆图标是配送进度示意，不表示实时 GPS。")
