from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

import folium
import copy
import hashlib
import json
from datetime import datetime, timezone
import streamlit as st
from 功能组件_页面共用代码.ui import display_table
from streamlit_folium import st_folium

from 功能组件_页面共用代码.maps import AnimatedVehicle, PlaybackControl, ResponsiveFitBounds, add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.formal_dispatch import is_dijkstra_route
from 功能组件_页面共用代码.live_operations import PRODUCT_COLORS
from 功能组件_页面共用代码.gps_simulator import route_motion_plan, route_stop_data
from 功能组件_页面共用代码.order_state import customer_order, init_orders
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar


inject_css()
render_sidebar()
own_orders = init_orders()
page_title("我的配送地图", "仅显示本订单路线；需要时可加载路线周边的细支道路")

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
if order.get("状态") == "已取消":
    st.info("这笔配送子单已取消，没有配送路线。可在上方切换同一总单的其他子单。")
    st.stop()
group = [o for o in own_orders if o.get("状态") != "已取消" and order.get("总单编号") and o.get("总单编号") == order["总单编号"]] or [order]
st.caption("蓝色实线：鲜面条 · 橙色虚线：姜蒜。两种品类分车配送，可在图层菜单单独查看。")
display_table([{"品类": o["品类"], "订单编号": o["订单编号"], "线路": o.get("线路编号", "等待确认"), "状态": o["状态"]} for o in group], hide_index=True, use_container_width=True)
st.caption("仅展示本总单获准查看的配送子单，不显示其他客户姓名、电话、订单号或站点。")

if st.button("更新订单状态", key="refresh_tracking_status"):
    st.rerun()

# 会话内只保留当前订单的底图；车辆移动不改变底图脚本或组件标识。
routes = [(o["订单编号"], o["品类"], o.get("路线GeoJSON")) for o in group if is_dijkstra_route(o) and o.get("线路编号")]
routes.sort(key=lambda item: item[1] == "姜蒜")
if not routes:
    st.info("线路尚未确认，确认后会显示本单配送地图。")
    st.stop()
detailed = st.toggle("显示细支道路（加载更多地图数据）", key="customer-map-roads")
static_map = st.toggle("地图加载异常时使用备用地图", key="customer-map-static")
demo_orders = any(o.get("演示发车") for o in group)
st.caption("地图标记按已确认道路路线的逐段距离、平均车速和早高峰车速连续移动；"
           + ("可在地图内连续调节演示倍率或从起点重播。" if demo_orders else "")
           + "缩放地图时，屏幕位移随比例尺改变。")
points = [p for _, _, route in routes for feature in route["features"] for p in feature["geometry"]["coordinates"]]
road_bounds = (min(p[0] for p in points), min(p[1] for p in points),
               max(p[0] for p in points), max(p[1] for p in points))
network_margin = 0.12
network_bounds = (road_bounds[0] - network_margin, road_bounds[1] - network_margin,
                  road_bounds[2] + network_margin, road_bounds[3] + network_margin)
map_key = ("nearby-v27", order.get("总单编号") or str(active), hashlib.sha256(json.dumps([
    routes, detailed,
    [(o["订单编号"], o.get("状态"), o.get("发车时间"), o.get("行驶参数")) for o in group],
], sort_keys=True).encode()).hexdigest())
cached = st.session_state.get("tracking_base_map")
if cached is None or cached[0] != map_key:
    warehouses = {o.get("仓库编号", "D0"): {"编号": o.get("仓库编号", "D0"), "名称": o.get("出发仓库", "原配送中心"), "坐标": o.get("仓库坐标", [104.26104981303031, 30.851137170192068])} for o in group}
    fmap, minor_layer = create_chengdu_map(zoom_start=10, warehouses=list(warehouses.values()), road_bounds=network_bounds, detailed=detailed)
    # 初始视角包含线路周边路网，避免首帧地图尺寸未确定时偏离范围。
    fmap.location = [(road_bounds[1] + road_bounds[3]) / 2, (road_bounds[0] + road_bounds[2]) / 2]
    view_bounds = [[network_bounds[1], network_bounds[0]], [network_bounds[3], network_bounds[2]]]
    fmap.fit_bounds(view_bounds, padding=(20, 20), max_zoom=14)
    ResponsiveFitBounds(view_bounds).add_to(fmap)
    for oid, product, route in routes:
        color = PRODUCT_COLORS[product]
        style = {"color": color, "weight": 7 if product == "鲜面条" else 4, "opacity": 0.9, "dashArray": "8 8" if product == "姜蒜" else None}
        folium.GeoJson(route, name=f"{product} · {oid}", style_function=lambda _, s=style: s, tooltip=f"本单{product}配送路线").add_to(fmap)
    started_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if demo_orders:
        PlaybackControl().add_to(fmap)
    pause_rows = []
    for current in group:
        stops = route_stop_data(current) if current.get("状态") == "配送途中" else []
        timeline, pauses = route_motion_plan(current, stops)
        if not timeline or current.get("状态") not in {"配送途中", "已送达", "签收完成"}:
            continue
        product = current["品类"]
        for pause in pauses:
            wait, service = pause["wait_minutes"], pause["service_minutes"]
            pause_rows.append({"品类": product, "站点": f"第 {pause['number']} 站",
                               "等待_分钟": round(wait, 1), "服务_分钟": round(service, 1),
                               "停留合计_分钟": round(wait + service, 1)})
            lon, lat = pause["coordinate"]
            folium.CircleMarker([lat, lon], radius=5, color=PRODUCT_COLORS[product],
                                fill=True, fill_opacity=1,
                                tooltip=f"{product} · 第{pause['number']}站 · 停留{wait + service:.1f}分钟").add_to(fmap)
        completed = current.get("状态") in {"已送达", "签收完成"}
        marker = folium.Marker(
            timeline[-1][:2] if completed else timeline[0][:2],
            tooltip=f"{product} · {current.get('车辆编号', '配送车辆')} · {'已送达' if completed else '行驶模拟'}",
            icon=folium.Icon(color="blue" if product == "鲜面条" else "orange", icon="truck", prefix="fa"),
        ).add_to(fmap)
        if completed:
            continue
        try:
            actual_start = int(datetime.fromisoformat(str(current["发车时间"])).timestamp() * 1000)
        except (KeyError, TypeError, ValueError):
            continue
        demo = bool(current.get("演示发车"))
        AnimatedVehicle(marker, timeline, started_ms if demo else actual_start,
                        10 if demo else 1, demo=demo).add_to(fmap)
    add_zoom_detail_behavior(fmap, minor_layer, threshold=13)
    folium.LayerControl(collapsed=True, position="topright").add_to(fmap)
    fmap.get_root().render()
    st.session_state["tracking_base_map"] = (map_key, fmap, pause_rows)
fmap = st.session_state["tracking_base_map"][1]
moving = any(o.get("状态") == "配送途中" for o in group)


@st.fragment(run_every="30s" if moving else None)
def render_live_status() -> None:
    latest = [customer_order(o["订单编号"]) for o in group]
    if any(o is None for o in latest):
        st.warning("订单当前不可访问，请重新查询。")
        return
    if any(current.get("状态") != old.get("状态") for current, old in zip(latest, group)):
        st.rerun()
    for current in latest:
        if not current.get("线路编号"):
            st.info(f"{current['品类']}：等待工作人员统一确认。")
            continue
        from 功能组件_页面共用代码.arrival_estimate import arrival_window
        window = arrival_window(current)
        if window:
            st.info(f"{current['品类']} · 预计到达 {window['标签']}")


render_live_status()
# 状态轮询只刷新文字；地图保持挂载，避免重新渲染路网和重置动画。
display_map = copy.deepcopy(fmap)
if static_map:
    st.components.v1.html(display_map.get_root().render(), height=800, scrolling=False)
else:
    st_folium(display_map, use_container_width=True, height=800, returned_objects=[], key=f"tracking-map-{map_key[1]}-{map_key[2][:8]}", render=False)
pause_rows = st.session_state["tracking_base_map"][2]
if pause_rows:
    with st.expander("查看车辆各站停留"):
        display_table(pause_rows, hide_index=True, use_container_width=True)
if all(o.get("状态") in {"已送达", "签收完成"} for o in group):
    st.caption("车辆已到达，自动更新已停止；地图保留在当前页面，可继续缩放查看。")
elif moving:
    st.caption("车辆按逐站等待和服务时间停靠；每 30 秒核对订单状态。")
else:
    st.caption("当前地图不自动更新。需要查看最新调度或发车状态时，点击“更新订单状态”。")
st.caption("蓝色鲜面条、橙色姜蒜路线均为已确认的道路最短路径。前序站点只显示序号与停留时长；车辆位置为演示仿真，并非车载定位。")
