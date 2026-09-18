import streamlit as st

from 功能组件_页面共用代码.order_state import STATUS_FLOW, find_order, init_orders
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar


inject_css()
render_sidebar()
orders = init_orders()
page_title("订单追踪", "查看订单从提交、备货到配送签收的当前进度")

if not orders:
    st.markdown("<div class='empty-stage motion-focus'><h2>还没有可追踪的订单。</h2><p>先提交配送需求，订单进度会显示在这里。</p></div>", unsafe_allow_html=True)
    if st.button("创建配送订单", type="primary", use_container_width=True):
        st.switch_page("pages/客户下单.py")
    st.stop()

ids = [item["订单编号"] for item in orders]
default_id = st.session_state.get("active_order_id", ids[0])
selected = st.selectbox("选择订单", ids, index=ids.index(default_id) if default_id in ids else 0)
order = find_order(selected)
st.session_state["active_order_id"] = selected
index = int(order.get("状态序号", 0))

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

st.markdown("<div class='demo-banner motion-reveal'><b>本机演示模式</b><span>订单状态和调度线用于流程演示，不展示虚构的实时车辆位置或温度数据。</span></div>", unsafe_allow_html=True)
