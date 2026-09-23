import streamlit as st

from 功能组件_页面共用代码.gps_simulator import get_tracking_snapshot
from 功能组件_页面共用代码.order_state import STATUS_FLOW, find_order, init_orders
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar


inject_css()
render_sidebar()
orders = init_orders()
page_title("订单追踪", "查看订单从提交、备货到配送签收的当前进度")

own_tab, lookup_tab = st.tabs(["本次访问的订单", "使用订单号查询"])
order = None
with own_tab:
    if orders:
        ids = [item["订单编号"] for item in orders]
        default_id = st.session_state.get("active_order_id", ids[0])
        selected = st.selectbox("选择订单", ids, index=ids.index(default_id) if default_id in ids else 0)
        # 优先读取共享记录，保证工作人员发车后的新状态会显示给客户。
        order = find_order(selected, include_saved=True)
    else:
        st.info("当前浏览器还没有提交过订单，可切换到“使用订单号查询”。")
with lookup_tab:
    q1, q2 = st.columns([1.4, .6])
    query_id = q1.text_input("订单编号", placeholder="例如：YL20260918123000ABCD").strip().upper()
    phone_tail = q2.text_input("联系电话后四位", max_chars=4, placeholder="用于核验").strip()
    if st.button("查询订单", type="primary", use_container_width=True):
        candidate = find_order(query_id, include_saved=True) if query_id else None
        stored_phone = str(candidate.get("联系电话", "")) if candidate else ""
        if candidate and len(phone_tail) == 4 and stored_phone.endswith(phone_tail):
            order = candidate
            st.session_state["active_order_id"] = query_id
            st.session_state["lookup_order_id"] = query_id
        else:
            st.error("未找到匹配订单，请检查订单编号和联系电话后四位。")
    elif st.session_state.get("lookup_order_id"):
        order = find_order(st.session_state["lookup_order_id"], include_saved=True)

if not order:
    st.markdown("<div class='empty-stage motion-focus'><h2>输入订单号即可继续查看。</h2><p>订单号会在提交成功后显示，请同时准备联系电话后四位。</p></div>", unsafe_allow_html=True)
    if st.button("创建配送订单", use_container_width=True):
        st.switch_page("pages/客户下单.py")
    st.stop()

st.session_state["active_order_id"] = order["订单编号"]
if st.button("刷新最新状态", use_container_width=True):
    st.rerun()
index = int(order.get("状态序号", 0))


@st.fragment(run_every="10s")
def render_live_eta() -> None:
    current = find_order(str(order["订单编号"]), include_saved=True) or order
    snapshot = get_tracking_snapshot(current, demo_factor=60.0)
    if not snapshot:
        return
    st.markdown("### 车辆定位仿真与动态 ETA")
    c1, c2, c3 = st.columns(3)
    c1.metric("路程完成度", f"{snapshot['progress']:.0%}")
    c2.metric("剩余里程", f"{snapshot['remaining_km']:.2f} km")
    c3.metric("预计到达", snapshot["eta"].strftime("%H:%M"))
    st.progress(snapshot["progress"])
    st.info(f"预计到达区间：{snapshot['eta_earliest']:%H:%M} - {snapshot['eta_latest']:%H:%M}")
    st.caption("位置与 ETA 根据已确认的 Dijkstra 路线、发车时间和仿真速度计算，不是车载 GPS 实时数据；客户原预约时间窗不会被修改。")

st.markdown(f"""
<div class="tracking-head motion-focus">
  <div><span>订单编号</span><h2>{order['订单编号']}</h2><p>{order['客户名称']} · {order['品类']} · {order['配送重量_kg']:,.0f} kg</p></div>
  <div class="tracking-state"><i></i><b>{order['状态']}</b><small>{order['数据模式']}</small></div>
</div>
<div class="delivery-track" style="--track:{index / (len(STATUS_FLOW)-1) * 100:.0f}%">
  <div class="delivery-track-fill"></div>
  {''.join(f'<div class="delivery-node {"done" if i <= index else ""}"><span>{i+1}</span><b>{label}</b></div>' for i, label in enumerate(STATUS_FLOW))}
</div>
""", unsafe_allow_html=True)

render_live_eta()

left, right = st.columns([1.2, .8], gap="large")
with left:
    st.markdown("### 配送信息")
    st.markdown(f"""
    <div class="detail-sheet motion-reveal">
      <div><span>收货地址</span><b>{order['收货地址']}</b></div>
      <div><span>期望送达</span><b>{order['期望送达']}</b></div>
      <div><span>最晚送达</span><b>{order['最晚送达']}</b></div>
      <div><span>预估费用</span><b>¥ {float(order.get('预估费用_元', 0)):,.2f}</b></div>
      <div><span>服务时间</span><b>{int(order.get('服务时间_分钟', 0))} 分钟</b></div>
      <div><span>允许送达窗口</span><b>期望时间前后各放宽 30 分钟</b></div>
      <div><span>配送安排</span><b>{'等待工作人员确认后展示' if index < 2 else '方案已确认，可查看配送地图'}</b></div>
    </div>
    """, unsafe_allow_html=True)
with right:
    st.markdown("### 配送查看")
    st.info("演示模式下可查看订单状态与调度线；正式运行时将以调度系统的车辆和到达信息为准。")
    st.page_link("pages/配送网络地图.py", label="查看我的配送地图", use_container_width=True)
    if order.get("状态") == "已送达" and st.button("完成电子签收", type="primary", use_container_width=True):
        st.switch_page("pages/电子签收.py")

st.markdown("<div class='demo-banner motion-reveal'><b>车辆定位仿真</b><span>车辆位置和动态 ETA 基于真实 Dijkstra 路线与发车时间计算，不代表车载 GPS 实时上报，也不展示温度数据。</span></div>", unsafe_allow_html=True)
