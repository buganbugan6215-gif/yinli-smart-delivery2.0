from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

import streamlit as st

from 功能组件_页面共用代码.arrival_estimate import arrival_window
from 功能组件_页面共用代码.order_state import STATUS_FLOW, CANCELLED_STATUS, cancel_customer_order, customer_order, init_orders, verify_customer_order
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
        labels = {o["订单编号"]: f"{o['品类']} · {o['订单编号']}" for o in orders}
        selected = st.selectbox("选择配送子单", ids, index=ids.index(default_id) if default_id in ids else 0, format_func=lambda oid: labels[oid])
        # 优先读取共享记录，保证工作人员发车后的新状态会显示给客户。
        order = customer_order(selected)
    else:
        st.info("当前浏览器还没有提交过订单，可切换到“使用订单号查询”。")
with lookup_tab:
    q1, q2 = st.columns([1.4, .6])
    query_id = q1.text_input("订单编号", placeholder="总单号 YG… 或配送子单号 YL…").strip().upper()
    phone_tail = q2.text_input("联系电话后四位", max_chars=4, placeholder="用于核验").strip()
    if st.button("查询订单", type="primary", use_container_width=True):
        candidate = verify_customer_order(query_id, phone_tail) if query_id else None
        if candidate:
            order = candidate
            st.session_state["active_order_id"] = candidate["订单编号"]
            st.session_state["lookup_order_id"] = candidate["订单编号"]
            st.rerun()
        else:
            order = None
            st.error("未找到匹配订单，请检查订单编号和联系电话后四位。")

if not order:
    st.markdown("<div class='empty-stage motion-focus'><h2>输入订单号即可继续查看。</h2><p>订单号会在提交成功后显示，请同时准备联系电话后四位。</p></div>", unsafe_allow_html=True)
    if st.button("创建配送订单", use_container_width=True):
        st.switch_page("pages/客户下单.py")
    st.stop()

st.session_state["active_order_id"] = order["订单编号"]
if order.get("总单编号"):
    st.caption(f"总单编号：{order['总单编号']} · 每个品类独立配送与签收")
if st.button("刷新最新状态", use_container_width=True):
    st.rerun()
if order.get("状态") == CANCELLED_STATUS:
    st.info("该配送子单已取消，不再参与线路计算。历史记录仍可通过订单编号查询。")
    st.caption(f"取消时间：{str(order.get('取消时间', '—'))[:19].replace('T', ' ')}")
    st.stop()
if order.get("状态") in STATUS_FLOW[:3]:
    with st.expander("取消此配送子单"):
        st.caption("若线路已确认但尚未发车，取消会撤销该配送日全部旧线路，其他订单等待工作人员重新计算。")
        confirm_cancel = st.checkbox("我确认取消此配送子单", key="confirm_cancel_" + order["订单编号"])
        if st.button("确认取消订单", disabled=not confirm_cancel, key="cancel_" + order["订单编号"]):
            try:
                cancel_customer_order(order["订单编号"])
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
index = int(order.get("状态序号", 0))
st.caption(f"配送日期：{order['期望送达日期']} · 按前一日 20:00 截止收单")
if order.get("线路编号"):
    route_cols = st.columns(3)
    route_cols[0].metric("我的配送线路", order["线路编号"])
    route_cols[1].metric("配送车辆", order["车辆编号"])
    route_cols[2].metric("本单配送顺序", f"第 {order['配送顺序']} 站")
else:
    st.info("本配送日尚未统一确认，确认后将显示您的线路编号和车辆。")


@st.fragment(run_every="15s" if order.get("状态") not in {"已送达", "签收完成"} else None)
def render_live_eta() -> None:
    current = customer_order(str(order["订单编号"]))
    if not current:
        st.warning("订单当前不可访问，请重新核验。")
        return
    if current.get("状态") != order.get("状态"):
        st.rerun()
    window = arrival_window(current)
    if window:
        st.metric("预计到达时间", window["标签"])
        st.caption(window["来源"] + f"；预计 {window['开始服务']} 开始服务，{window['完成交付']} 完成交付。")
        if window["本站等待_分钟"] > 0:
            st.info(f"车辆预计提前到站，等待约 {window['本站等待_分钟']:.0f} 分钟后，按您的收货时间开始服务。")
        with st.expander("查看预计时间的计算"):
            st.write(f"发车：{window['发车']} · 本单为第 {window['配送顺序']} 站 · 到本站累计道路里程 {window['道路里程_km']:.2f} 公里")
            st.write(f"预计行驶 {window['行驶_分钟']:.1f} 分钟 + 前站等待 {window['前站等待_分钟']:.1f} 分钟 + 前站服务 {window['前站服务_分钟']:.1f} 分钟")
            st.caption(f"平均车速 {window['平均速度_kmh']:g} 公里/小时；07:00–09:00 按 {window['早高峰速度_kmh']:g} 公里/小时分段计算。本单服务 {window['本站服务_分钟']:g} 分钟计入完成交付时间。")
        if window["已过期"]:
            st.warning("预计时间已过，工作人员尚未登记送达，请刷新查看最新状态。")
    elif current.get("状态") not in {"已送达", "签收完成"}:
        st.info("该线路缺少完整的逐站距离或服务数据，暂时无法计算预计到达时间，请工作人员检查线路。" if current.get("线路编号") else "线路确认后显示预计到达时间。")


st.markdown(f"""
<div class="tracking-head motion-focus">
  <div><span>订单编号</span><h2>{order['订单编号']}</h2><p>{order['客户名称']} · {order['品类']} · {order['配送重量_kg']:,.0f} 千克</p></div>
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
      <div><span>预约最早收货</span><b>{order['期望送达']}</b></div>
      <div><span>预约最晚收货</span><b>{order['最晚送达']}</b></div>
      <div><span>预估费用</span><b>¥ {float(order.get('预估费用_元', 0)):,.2f}</b></div>
      <div><span>服务时间</span><b>{int(order.get('服务时间_分钟', 0))} 分钟</b></div>
      <div><span>允许送达窗口</span><b>{order.get('最早到达', '—')}—{order.get('最晚到达', '—')}</b></div>
      <div><span>配送安排</span><b>{'等待工作人员确认后展示' if index < 2 else '方案已确认，可查看配送地图'}</b></div>
    </div>
    """, unsafe_allow_html=True)
with right:
    st.markdown("### 配送查看")
    st.info("演示模式下可查看订单状态与调度线；正式运行时将以调度系统的车辆和到达信息为准。")
    st.page_link("pages/配送网络地图.py", label="查看我的配送地图", use_container_width=True)
    if order.get("状态") == "已送达" and st.button("完成电子签收", type="primary", use_container_width=True):
        st.switch_page("pages/电子签收.py")

st.markdown("<div class='demo-banner motion-reveal'><b>车辆定位仿真</b><span>车辆位置和预计到达时间基于已确认的道路最短路径与发车时间计算，不代表车载定位实时上报，也不展示温度数据。</span></div>", unsafe_allow_html=True)
