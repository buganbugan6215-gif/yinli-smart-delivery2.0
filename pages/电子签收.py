import streamlit as st

from 功能组件_页面共用代码.order_state import STATUS_FLOW, find_order, init_orders, persist_order
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar


inject_css()
render_sidebar()
orders = init_orders()
page_title("确认签收", "正常到货一键确认；发现异常可在下方提交反馈")

if not orders:
    st.info("当前没有可签收的订单。")
    if st.button("返回客户下单", type="primary", use_container_width=True):
        st.switch_page("pages/客户下单.py")
    st.stop()

ids = [item["订单编号"] for item in orders]
active = st.session_state.get("active_order_id", ids[0])
selected = st.selectbox("选择订单", ids, index=ids.index(active) if active in ids else 0)
order = find_order(selected)

st.markdown(f"<div class='receipt-head motion-focus'><span>{order['订单编号']}</span><h2>{order['客户名称']}</h2><p>{order['品类']} · {order['配送重量_kg']:,.0f} kg · {order['收货地址']}</p></div>", unsafe_allow_html=True)

if order.get("状态") == "签收完成":
    st.success("该订单已确认签收。")
elif order.get("状态") != "已送达":
    st.info(f"当前订单处于“{order.get('状态')}”，待配送车辆发出后可确认签收。")
else:
    st.markdown("### 货物确认无误")
    st.caption("请在确认数量、包装和货物状态无异常后完成签收。")
    if st.button("确认签收", type="primary", use_container_width=True):
        order["状态"] = "签收完成"
        order["状态序号"] = 5
        order["签收结果"] = "正常签收"
        persist_order(order)
        st.success("签收完成，订单状态已更新。")
        st.rerun()

st.divider()
with st.expander("异常反馈", expanded=False):
    st.caption("包装、数量、温度或送达时间存在问题时，请提交情况说明。")
    with st.form("exception_form"):
        problems = st.multiselect("异常类型", ["包装破损", "数量不符", "温度异常", "送达延迟", "其他"])
        detail = st.text_area("异常情况说明", placeholder="请描述发现的问题，便于工作人员尽快处理")
        callback = st.checkbox(f"需要客服回电至 {order.get('联系电话', '订单联系电话')}")
        submitted = st.form_submit_button("提交异常反馈", use_container_width=True)
    if submitted:
        if not problems or not detail.strip():
            st.error("请选择异常类型并填写情况说明。")
        else:
            order["异常反馈"] = {
                "异常类型": "、".join(problems),
                "情况说明": detail.strip(),
                "需要回电": callback,
                "处理状态": "等待客服联系",
            }
            persist_order(order)
            st.success("异常反馈已提交，工作人员将根据订单联系电话与您沟通。")

if order.get("异常反馈"):
    feedback = order["异常反馈"]
    st.info(f"已提交：{feedback['异常类型']}｜{feedback['处理状态']}")
