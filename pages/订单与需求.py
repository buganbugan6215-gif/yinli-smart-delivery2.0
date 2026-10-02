from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

import pandas as pd
import streamlit as st
from 功能组件_页面共用代码.ui import display_table
from 功能组件_页面共用代码.batch_dispatch import day_orders
from 功能组件_页面共用代码.live_operations import select_delivery_day, order_summary
from 功能组件_页面共用代码.ui import inject_css, render_sidebar, require_staff_access, page_title

inject_css()
render_sidebar()
require_staff_access()
page_title("订单台账", "查询客户提交、配送子单与异常反馈；调度操作请进入统一调度")
day = select_delivery_day(st, historical=True)
query = st.text_input("搜索总单号、子单号或客户名称").strip()
product = st.selectbox("品类", ["全部", "鲜面条", "姜蒜"])

@st.fragment(run_every="30s")
def render_orders():
    orders = day_orders(day)
    if not orders:
        st.info("该配送日暂无实际订单。")
        return
    visible = [o for o in orders if (product == "全部" or o["品类"] == product) and
               (not query or any(query.lower() in str(o.get(k, "")).lower() for k in ("订单编号", "总单编号", "客户名称")))]
    summary = order_summary(visible)
    st.caption(f"每 30 秒读取最新订单 · 当前筛选 {summary['客户提交次数']} 次客户提交 / {summary['配送子单']} 个配送子单 / {summary['货量_kg']:.1f} 千克")
    frame = pd.DataFrame(visible)
    cols = ["总单编号", "订单编号", "客户名称", "品类", "配送重量_kg", "期望送达日期", "最早到达", "最晚到达", "状态", "线路编号", "车辆编号", "联系电话", "收货地址"]
    display_table(frame[[c for c in cols if c in frame]], hide_index=True, use_container_width=True)
    st.download_button("导出筛选订单 CSV", frame.drop(columns=["路线GeoJSON"], errors="ignore").to_csv(index=False).encode("utf-8-sig"), f"{day}_订单台账.csv")
    feedback = [o for o in visible if o.get("异常反馈")]
    with st.expander(f"异常反馈 · {len(feedback)} 条"):
        for o in feedback:
            st.write({"订单编号": o["订单编号"], "客户名称": o.get("客户名称"), "反馈": o["异常反馈"]})
        if not feedback:
            st.caption("当前筛选没有异常反馈。")

render_orders()
