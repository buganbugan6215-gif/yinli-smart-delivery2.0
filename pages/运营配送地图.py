import folium
import streamlit as st
from streamlit_folium import st_folium

from 功能组件_页面共用代码.maps import add_customer_points, add_route_features, add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.data_loader import load_site_data
from 功能组件_页面共用代码.order_state import init_orders
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar, require_staff_access


inject_css()
render_sidebar()
require_staff_access()
page_title("运营配送地图", "查看竞赛方案的全量配送网络，并叠加本机演示订单调度线")

data = load_site_data()
orders = init_orders(include_saved=True)
fmap, minor_layer = create_chengdu_map(zoom_start=10)
add_route_features(fmap, data.route_features)
add_customer_points(fmap, data.customer_points)
for order in orders:
    route = order.get("路线GeoJSON")
    if route and route.get("features"):
        folium.GeoJson(route, name=f"演示订单 {order['订单编号']}", style_function=lambda _: {"color": "#ff8133", "weight": 4, "opacity": 0.9}, tooltip=f"演示订单：{order['订单编号']}").add_to(fmap)
add_zoom_detail_behavior(fmap, minor_layer, threshold=13)
folium.LayerControl(collapsed=True).add_to(fmap)
st_folium(fmap, use_container_width=True, height=650, returned_objects=[])
st.caption("蓝色线路为题目数据中的配送网络，橙色线路为本机演示订单的坐标调度线。两者均不表示实时车辆位置。")
