import folium
import streamlit as st
from streamlit_folium import st_folium

from 功能组件_页面共用代码.maps import add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.formal_dispatch import is_dijkstra_route
from 功能组件_页面共用代码.gps_simulator import get_tracking_snapshot
from 功能组件_页面共用代码.order_state import STATUS_FLOW, customer_order, init_orders
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar


inject_css()
render_sidebar()
own_orders = init_orders()
page_title("我的配送地图", "仅显示当前订单的配送路线；放大地图后自动显示细支道路")

active = st.session_state.get("active_order_id")
if not active and own_orders:
    active = own_orders[0]["订单编号"]

if not active:
    st.markdown("<div class='empty-stage motion-focus'><h2>还没有可查看路线的订单。</h2><p>提交配送订单后，调度确认的路线会显示在这里。</p></div>", unsafe_allow_html=True)
    if st.button("前往客户下单", type="primary", use_container_width=True):
        st.switch_page("pages/客户下单.py")
    st.stop()

order = customer_order(str(active))
if not order:
    st.warning("未找到该订单，请先在“订单追踪”使用订单号和联系电话后四位查询。")
    st.stop()
st.session_state["active_order_id"] = order["订单编号"]
st.info(f"所属线路：{order.get('线路编号', '尚未统一确认')} · 配送日：{order['期望送达日期']}")
st.caption("仅展示沿已分配线路到本收货点的道路，不显示其他客户姓名、电话、订单号或站点标记。")

st.markdown(f"""
<div class="map-order-head motion-focus">
  <div><span>当前订单</span><b>{order['订单编号']}</b></div>
  <div><span>配送品类</span><b>{order['品类']}</b></div>
  <div><span>当前状态</span><b>{order['状态']}</b></div>
</div>
""", unsafe_allow_html=True)

@st.fragment(run_every="10s")
def render_live_tracking() -> None:
    current = customer_order(str(active)) or order
    fmap, minor_layer = create_chengdu_map(zoom_start=10)
    route = current.get("路线GeoJSON")
    status_index = int(current.get("状态序号", 0))
    if not current.get("线路编号"):
        st.info("等待工作人员统一确认本配送日，确认后即可查看本单所属线路。")
    elif route and is_dijkstra_route(current):
        folium.GeoJson(route, name="本订单配送路线", style_function=lambda _: {"color": "#1750df", "weight": 5, "opacity": 0.9}, tooltip="本订单配送路线").add_to(fmap)
        snapshot = get_tracking_snapshot(current, demo_factor=60.0)
        if snapshot:
            note = "已送达 · 订单收货点" if current.get("状态") != "配送途中" else f"配送途中 · 路程完成 {snapshot['progress']:.0%}"
            folium.Marker(
                [snapshot["latitude"], snapshot["longitude"]],
                tooltip=f"{current.get('车辆编号', '配送车辆')} · {note} · 剩余 {snapshot['remaining_km']:.2f} km",
                popup=(f"<b>{current.get('车辆编号', '配送车辆')}</b><br>{note}<br>"
                       f"ETA：{snapshot['eta']:%H:%M}<br>预计区间：{snapshot['eta_earliest']:%H:%M} - {snapshot['eta_latest']:%H:%M}"),
                icon=folium.Icon(color="orange", icon="truck", prefix="fa"),
            ).add_to(fmap)
    else:
        st.info("该订单尚未导入 Dijkstra 路网精算结果，暂不显示路线。请由工作人员完成本机精算后上传 formal_result.json。")
    add_zoom_detail_behavior(fmap, minor_layer, threshold=13)
    folium.LayerControl(collapsed=True, position="topright").add_to(fmap)
    st_folium(fmap, use_container_width=True, height=650, returned_objects=[], key=f"tracking-map-{current['订单编号']}")
    st.caption("蓝色路线为已确认的 Dijkstra 路线。橙色车辆为根据发车时间和仿真速度生成的演示位置，不是车载 GPS 实时数据。")


render_live_tracking()
