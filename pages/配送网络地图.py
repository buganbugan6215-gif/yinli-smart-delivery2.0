from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

import folium
import copy
import hashlib
import json
import streamlit as st
from 功能组件_页面共用代码.ui import display_table
from streamlit_folium import st_folium

from 功能组件_页面共用代码.maps import add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.formal_dispatch import is_dijkstra_route
from 功能组件_页面共用代码.live_operations import PRODUCT_COLORS
from 功能组件_页面共用代码.gps_simulator import get_tracking_snapshot
from 功能组件_页面共用代码.order_state import customer_order, init_orders
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
if len(own_orders) > 1:
    ids = [o["订单编号"] for o in own_orders]
    labels = {o["订单编号"]: f"{o['品类']} · {o['订单编号']}" for o in own_orders}
    chosen = st.selectbox("选择配送订单", ids, index=ids.index(active) if active in ids else 0, format_func=lambda oid: labels[oid])
    if chosen != active:
        st.session_state["active_order_id"] = chosen
        st.rerun()
group = [o for o in own_orders if order.get("总单编号") and o.get("总单编号") == order["总单编号"]] or [order]
st.caption("蓝色实线：鲜面条 · 橙色虚线：姜蒜。两种品类分车配送，可在图层菜单单独查看。")
display_table([{"品类": o["品类"], "订单编号": o["订单编号"], "线路": o.get("线路编号", "等待确认"), "状态": o["状态"]} for o in group], hide_index=True, use_container_width=True)
st.caption("仅展示本总单获准查看的配送子单，不显示其他客户姓名、电话、订单号或站点。")

if st.button("更新订单状态", key="refresh_tracking_status"):
    st.rerun()

# 会话内只保留当前订单的底图；车辆移动不改变底图脚本或组件标识。
routes = [(o["订单编号"], o["品类"], o.get("路线GeoJSON")) for o in group if is_dijkstra_route(o) and o.get("线路编号")]
routes.sort(key=lambda item: item[1] == "姜蒜")
map_key = (order.get("总单编号") or str(active), hashlib.sha256(json.dumps(routes, sort_keys=True).encode()).hexdigest())
cached = st.session_state.get("tracking_base_map")
if cached is None or cached[0] != map_key:
    fmap, minor_layer = create_chengdu_map(zoom_start=10)
    for oid, product, route in routes:
        color = PRODUCT_COLORS[product]
        style = {"color": color, "weight": 7 if product == "鲜面条" else 4, "opacity": 0.9, "dashArray": "8 8" if product == "姜蒜" else None}
        folium.GeoJson(route, name=f"{product} · {oid}", style_function=lambda _, s=style: s, tooltip=f"本单{product}配送路线").add_to(fmap)
    add_zoom_detail_behavior(fmap, minor_layer, threshold=13)
    folium.LayerControl(collapsed=True, position="topright").add_to(fmap)
    fmap.get_root().render()
    st.session_state["tracking_base_map"] = (map_key, fmap)
fmap = st.session_state["tracking_base_map"][1]
moving = any(o.get("状态") == "配送途中" for o in group)


@st.fragment(run_every="10s" if moving else None)
def render_live_tracking() -> None:
    latest = [customer_order(o["订单编号"]) for o in group]
    if any(o is None for o in latest):
        st.warning("订单当前不可访问，请重新查询。")
        return
    if any(current.get("状态") != old.get("状态") for current, old in zip(latest, group)):
        st.rerun()
    vehicles = folium.FeatureGroup(name="车辆位置")
    for current in latest:
        if not current.get("线路编号"):
            st.info(f"{current['品类']}：等待工作人员统一确认。")
            continue
        snapshot = get_tracking_snapshot(current, demo_factor=60.0)
        if snapshot:
            note = "已送达" if current.get("状态") in {"已送达", "签收完成"} else f"配送途中 · 路程完成 {snapshot['progress']:.0%}"
            folium.Marker([snapshot["latitude"], snapshot["longitude"]],
                tooltip=f"{current['品类']} · {current.get('车辆编号', '配送车辆')} · {note}",
                icon=folium.Icon(color="blue" if current["品类"] == "鲜面条" else "orange", icon="truck", prefix="fa"),
            ).add_to(vehicles)
    # 组件会修改传入对象的内部 ID 和图层，使用副本保护缓存底图。
    st_folium(copy.deepcopy(fmap), use_container_width=True, height=650, returned_objects=[], key=f"tracking-map-{map_key[0]}", feature_group_to_add=vehicles, render=False)
    if all(o.get("状态") in {"已送达", "签收完成"} for o in latest):
        st.caption("车辆已到达，自动更新已停止；地图保留在当前页面，可继续缩放查看。")
    elif moving:
        st.caption("配送途中每 10 秒更新车辆位置，保留地图视角；工作人员确认送达后停止自动更新。")
    else:
        st.caption("当前地图不自动更新。需要查看最新调度或发车状态时，点击“更新订单状态”。")
    st.caption("蓝色鲜面条、橙色姜蒜路线均为已确认的 道路最短路径。车辆位置为演示仿真，不是车载定位实时数据。")


render_live_tracking()
