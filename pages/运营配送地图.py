import folium
import streamlit as st
from streamlit_folium import st_folium

from 功能组件_页面共用代码.batch_dispatch import get_batch, day_orders
from 功能组件_页面共用代码.order_state import init_orders
from 功能组件_页面共用代码.maps import add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar, require_staff_access

inject_css()
render_sidebar()
require_staff_access()
page_title("运营配送地图", "按配送日查看已统一确认的全部线路，仅工作人员可见")
days = sorted({str(o["期望送达日期"]) for o in init_orders(include_saved=True)}, reverse=True)
if not days:
    st.info("暂无客户订单。")
    st.stop()
day = st.selectbox("配送日期", days)
batch = get_batch(day)
if not batch:
    st.info("该配送日尚未统一确认，请先到「订单与参数」计算并确认整批方案。")
    st.stop()
fmap, minor_layer = create_chengdu_map(zoom_start=10)
colors = ["#1750df", "#e77620", "#178465", "#a349a4", "#9f3444", "#557422"]
for i, route in enumerate(batch["线路"]):
    color = colors[i % len(colors)]
    folium.GeoJson(route["路线GeoJSON"], name=route["线路编号"],
                   style_function=lambda _, c=color: {"color": c, "weight": 4, "opacity": .9},
                   tooltip=f"{route['线路编号']} · {route['车辆编号']}").add_to(fmap)
for order in day_orders(day):
    folium.CircleMarker([order["纬度"], order["经度"]], radius=5,
                        tooltip=f"{order['订单编号']} · 第{order['配送顺序']}站", fill=True).add_to(fmap)
add_zoom_detail_behavior(fmap, minor_layer, threshold=13)
folium.LayerControl(collapsed=False).add_to(fmap)
st_folium(fmap, use_container_width=True, height=650, returned_objects=[])
st.caption("各色线路为本配送日已确认的道路路径；包含返回配送中心路段。此地图不展示实时 GPS。")
