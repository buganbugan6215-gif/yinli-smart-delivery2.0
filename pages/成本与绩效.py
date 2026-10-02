from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

from datetime import time
import pandas as pd
import streamlit as st
from 功能组件_页面共用代码.ui import display_table
from 功能组件_页面共用代码.batch_dispatch import day_orders, get_batch, input_fingerprint
from 功能组件_页面共用代码.batch_solver import solve_batch
from 功能组件_页面共用代码.order_state import pricing_settings
from 功能组件_页面共用代码.live_operations import select_delivery_day, order_summary, plan_metrics, compare_strategies
from 功能组件_页面共用代码.ui import inject_css, render_sidebar, require_staff_access, page_title

inject_css()
render_sidebar()
require_staff_access()
page_title("运营分析", "按配送日分析实际订单、计划成本和同批次方案对比")
day = select_delivery_day(st, historical=True)
st.caption("默认查看今日、明日；预约到更晚日期的订单可选择“其他日期”查看和试算。")
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
        plan = get_batch(day)
        if not plan:
            st.info("尚未确认调度方案，暂无计划里程与车辆成本。可在方案对比中试算。")
            return
        rows = plan_metrics(plan)
        st.markdown("### 已确认方案的计划成本")
        st.caption("按确认时车辆参数计算固定成本与里程成本；不代表实际结算，不计未建模的制冷、货损及罚款。")
        display_table(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.write(f"计划总里程 {sum(r['里程_km'] for r in rows):.2f} 公里 · 固定及里程成本 ¥ {sum(r['固定及里程成本_元'] for r in rows):.2f}")
    render_summary()

with comparison:
    st.caption("同一批实际订单、同一距离矩阵、同一车辆和不混装约束，比较两种插入顺序。试算不会确认或修改订单；收单期间结果会随新订单失效。")
    departure = st.time_input("试算发车时间", value=time(6, 0))
    minutes = departure.hour * 60 + departure.minute
    if st.button("计算本配送日方案对比", type="primary"):
        orders = day_orders(day)
        try:
            with st.spinner("正在计算实际订单的道路矩阵和两种可行方案…"):
                plan = solve_batch(orders, pricing_settings(), minutes)
                st.session_state[f"comparison_{day}"] = compare_strategies(orders, plan)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    @st.fragment(run_every="30s")
    def render_comparison():
        result = st.session_state.get(f"comparison_{day}")
        if result:
            if result["输入指纹"] != input_fingerprint(day_orders(day)) or result["参数"] != pricing_settings() or result["发车分钟"] != minutes:
                st.warning("订单、参数或发车时间已变化，原对比失效，请重新计算。")
            else:
                display_table(pd.DataFrame(result["结果"]), hide_index=True, use_container_width=True)
                st.caption("两种方法均为启发式；可能得到相同结果，不保证全局最优。")
    render_comparison()
