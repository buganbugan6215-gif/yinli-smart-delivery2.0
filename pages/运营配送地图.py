from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

import folium
import streamlit as st
from streamlit_folium import st_folium

from 功能组件_页面共用代码.batch_dispatch import get_batch, day_orders
from 功能组件_页面共用代码.order_state import init_orders
from 功能组件_页面共用代码.live_operations import select_delivery_day, PRODUCT_COLORS
from 功能组件_页面共用代码.maps import add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar, require_staff_access

inject_css()
render_sidebar()
require_staff_access()
page_title("运营配送地图", "按配送日查看已统一确认的全部线路，仅工作人员可见")
day = select_delivery_day(st, historical=True)
batch = get_batch(day)
if not batch:
    st.info("该配送日尚未统一确认，请先到「统一调度」计算并确认整批方案。")
    st.stop()
fmap, minor_layer = create_chengdu_map(zoom_start=10)
st.caption("蓝色：鲜面条 · 橙色：姜蒜。不同品类分别用车。")
products = {o["订单编号"]: o["品类"] for o in day_orders(day)}
for i, route in enumerate(sorted(batch["线路"], key=lambda r: (r.get("品类") or products.get(r["订单编号列表"][0])) == "姜蒜")):
    color = PRODUCT_COLORS.get(route.get("品类") or products.get(route["订单编号列表"][0]), "#555555")
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
