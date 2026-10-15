from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

import pandas as pd
import streamlit as st
from 功能组件_页面共用代码.ui import display_table
from 功能组件_页面共用代码.batch_dispatch import day_orders, get_batch, input_fingerprint
from 功能组件_页面共用代码.batch_solver import solve_batch
from 功能组件_页面共用代码 import warehouse_ui, warehouses
from 功能组件_页面共用代码.order_state import pricing_settings
from 功能组件_页面共用代码.live_operations import select_delivery_day, order_summary, plan_metrics, compare_strategies
from 功能组件_页面共用代码.ui import inject_css, render_sidebar, require_staff_access, page_title

inject_css()
render_sidebar()
require_staff_access()
page_title("运营分析", "按配送日分析实际订单、计划成本和同批次方案对比")
day = select_delivery_day(st, historical=True)
st.caption("默认查看今日、明日；预约到更晚日期的订单可选择“其他日期”查看和试算。")
count, changed = warehouse_ui.selector(day)
if changed and day_orders(day):
    try:
        warehouse_ui.calculate(day)
        st.rerun()
    except (ValueError, OSError) as exc:
        st.error(str(exc))
overview, comparison = st.tabs(["订单与计划成本", "方案对比"])

with overview:
    @st.fragment(run_every="30s")
    def render_summary():
        orders = day_orders(day)
        if not orders:
            st.info("该配送日暂无实际订单，不展示竞赛样例数据。")
            return
        summary = order_summary(orders)
        cols = st.columns(4)
        for col, (label, value) in zip(cols, summary.items()):
            col.metric(label.replace("_kg", "（千克）"), value)
        frame = pd.DataFrame(orders)
        display_table(frame.groupby(["品类", "状态"], as_index=False).agg(子单数=("订单编号", "count"), 货量_kg=("配送重量_kg", "sum")), hide_index=True, use_container_width=True)
        plan = warehouse_ui.active_plan(day)
        if not plan:
            st.info("所选仓库尚无有效调度方案，请在统一调度一键计算。")
            return
        st.markdown("### 已确认方案" if get_batch(day) else "### 已计算方案 · 待确认")
        warehouse_ui.render_cost(plan)
    render_summary()

with comparison:
    st.caption("同一批实际订单和一套车队，比较原仓与原仓＋新增点。负节省表示双仓费用更高；未计未知场地费。")
    if st.button("计算本配送日方案对比", type="primary"):
        orders = day_orders(day)
        try:
            with st.spinner("正在计算实际订单的道路矩阵及单仓／双仓方案…"):
                plan = solve_batch(orders, pricing_settings(), warehouse_count=count)
                st.session_state[f"comparison_{day}"] = compare_strategies(orders, plan)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    @st.fragment(run_every="30s")
    def render_comparison():
        result = st.session_state.get(f"comparison_{day}")
        if result:
            if result["输入指纹"] != input_fingerprint(day_orders(day)) or result["参数"] != pricing_settings() or result["发车分钟"] != 0:
                st.warning("订单、参数或发车计算方式已变化，原对比失效，请重新计算。")
            else:
                display_table(pd.DataFrame(result["结果"]).round(2), hide_index=True, use_container_width=True)
                st.caption("两种仓库方案均使用当前订单重新求解；小批量下补货成本可能抵消路线节省。算法为可行插入启发式，不保证全局最优。")
    render_comparison()
