import folium
import streamlit as st
from streamlit_folium import st_folium

from 功能组件_页面共用代码.maps import add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.order_state import find_order, init_orders
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar


inject_css()
render_sidebar()
orders = init_orders()
page_title("我的配送地图", "仅显示当前订单的配送路线；放大地图后自动显示细支道路")

if not orders:
    st.markdown("<div class='empty-stage motion-focus'><h2>还没有可查看路线的订单。</h2><p>提交配送订单后，调度确认的路线会显示在这里。</p></div>", unsafe_allow_html=True)
    if st.button("前往客户下单", type="primary", use_container_width=True):
        st.switch_page("pages/客户下单.py")
    st.stop()

ids = [item["订单编号"] for item in orders]
active = st.session_state.get("active_order_id", ids[0])
selected = st.selectbox("查看订单", ids, index=ids.index(active) if active in ids else 0)
order = find_order(selected)
st.session_state["active_order_id"] = selected

st.markdown(f"""
<div class="map-order-head motion-focus">
  <div><span>当前订单</span><b>{order['订单编号']}</b></div>
  <div><span>配送品类</span><b>{order['品类']}</b></div>
  <div><span>当前状态</span><b>{order['状态']}</b></div>
</div>
""", unsafe_allow_html=True)

fmap, minor_layer = create_chengdu_map(zoom_start=10)
route = order.get("路线GeoJSON")
if int(order.get("状态序号", 0)) < 2:
    st.info("工作人员确认配送方案后，本订单路线将在这里显示。")
elif route and route.get("features"):
    folium.GeoJson(
        route,
        name="本订单配送路线",
        style_function=lambda _: {"color": "#1750df", "weight": 5, "opacity": 0.9},
        tooltip="本订单配送路线",
    ).add_to(fmap)
else:
    st.info("该订单尚未取得坐标，暂不能生成演示调度线。请返回订单页补充经纬度。")

add_zoom_detail_behavior(fmap, minor_layer, threshold=13)
folium.LayerControl(collapsed=True, position="topright").add_to(fmap)
st_folium(fmap, use_container_width=True, height=650, returned_objects=[])
st.caption("地图使用团队整理的道路数据。蓝线为本订单的演示调度线，用于串联订单流程，不等同于正式 Dijkstra 路网最短路径。")
