import folium
import streamlit as st
from streamlit_folium import st_folium

from 功能组件_页面共用代码.maps import add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.formal_dispatch import is_dijkstra_route
from 功能组件_页面共用代码.order_state import DEPOT_LAT, DEPOT_LON, STATUS_FLOW, find_order, init_orders
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

order = find_order(str(active), include_saved=True)
if not order:
    st.warning("未找到该订单，请先在“订单追踪”使用订单号和联系电话后四位查询。")
    st.stop()
st.session_state["active_order_id"] = order["订单编号"]

st.markdown(f"""
<div class="map-order-head motion-focus">
  <div><span>当前订单</span><b>{order['订单编号']}</b></div>
  <div><span>配送品类</span><b>{order['品类']}</b></div>
  <div><span>当前状态</span><b>{order['状态']}</b></div>
</div>
""", unsafe_allow_html=True)

fmap, minor_layer = create_chengdu_map(zoom_start=10)
route = order.get("路线GeoJSON")
status_index = int(order.get("状态序号", 0))
if status_index < STATUS_FLOW.index("配送途中"):
    st.info("车辆尚未发出。工作人员点击“车辆发出，开始配送”后，路线和车辆位置将在这里显示。")
elif route and is_dijkstra_route(order):
    folium.GeoJson(
        route,
        name="本订单配送路线",
        style_function=lambda _: {"color": "#1750df", "weight": 5, "opacity": 0.9},
        tooltip="本订单配送路线",
    ).add_to(fmap)
    # 此标记用于演示订单处于配送中的进度，不表示司机 GPS 实时定位。
    try:
        destination = route["features"][0]["geometry"]["coordinates"][-1]
        if order.get("状态") == "配送途中":
            vehicle_lon = (DEPOT_LON + float(destination[0])) / 2
            vehicle_lat = (DEPOT_LAT + float(destination[1])) / 2
            position_note = "配送途中 · 路线中段示意位置"
        else:
            vehicle_lon, vehicle_lat = float(destination[0]), float(destination[1])
            position_note = "已送达 · 订单收货点"
        folium.Marker(
            [vehicle_lat, vehicle_lon],
            tooltip=f"{order.get('车辆编号', '配送车辆')} · {position_note}",
            popup=f"<b>{order.get('车辆编号', '配送车辆')}</b><br>{position_note}<br>订单：{order['订单编号']}",
            icon=folium.Icon(color="orange", icon="truck", prefix="fa"),
        ).add_to(fmap)
    except (KeyError, IndexError, TypeError, ValueError):
        pass
else:
    st.info("该订单尚未导入 Dijkstra 路网精算结果，暂不显示路线。请由工作人员完成本机精算后上传 formal_result.json。")

add_zoom_detail_behavior(fmap, minor_layer, threshold=13)
folium.LayerControl(collapsed=True, position="topright").add_to(fmap)
st_folium(fmap, use_container_width=True, height=650, returned_objects=[])
st.caption("蓝线为本订单基于货车路网节点计算的 Dijkstra 路径；橙色车辆为配送进度示意，不是司机 GPS 实时定位。")
