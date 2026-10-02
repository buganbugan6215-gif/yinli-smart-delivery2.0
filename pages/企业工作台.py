from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

from datetime import time
import pandas as pd
import streamlit as st
from 功能组件_页面共用代码.ui import display_table
from 功能组件_页面共用代码.calendar_runtime import ensure_current_calendar

ensure_current_calendar()

from 功能组件_页面共用代码.order_state import pricing_settings
from 功能组件_页面共用代码.delivery_calendar import beijing_now, delivery_day, batch_closed, cutoff_label
from 功能组件_页面共用代码.batch_dispatch import day_orders, get_batch, input_fingerprint, confirm_batch, advance_batch, workbook_bytes
from 功能组件_页面共用代码.batch_solver import solve_batch
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar, require_staff_access

inject_css()
render_sidebar()
require_staff_access()
page_title("统一调度", "计算完整批次、确认分品类线路、管理发车与送达")
st.info("收单规则：北京时间每日 20:00 截止次日订单；截止前最早次日配送，截止后最早后天配送。客户可预约更晚日期。")
from 功能组件_页面共用代码.live_operations import select_delivery_day
order_tab = st.container()

with order_tab:
    day = select_delivery_day(st, historical=True)
    st.caption(f"截止时间：{cutoff_label(day)}")
    if st.button("刷新本配送日订单"):
        st.rerun()
    orders = day_orders(day)
    closed = batch_closed(day)
    batch = get_batch(day)
    stats = st.columns(3)
    stats[0].metric("本批次订单", len(orders))
    stats[1].metric("总货量（千克）", f"{sum(float(o['配送重量_kg']) for o in orders):,.1f}")
    stats[2].metric("批次状态", "已统一确认" if batch else "已截止，待调度" if closed else "正在收单")
    if not orders:
        st.info("本配送日暂无订单，收到订单后可计算整批线路。")
    elif not closed:
        st.warning("本批次尚在收单。截止后才能统一计算和确认，以免漏掉后续订单。")
    elif not batch:
        departure = st.time_input("计划发车时间", time(6, 0))
        if st.button("一次计算全部订单的矩阵与线路", type="primary", use_container_width=True):
            progress = st.progress(0.0, text="正在加载货车路网…")
            try:
                plan = solve_batch(orders, pricing_settings(), departure.hour*60+departure.minute,
                                   lambda value, message: progress.progress(value, text=message))
                plan["输入指纹"] = input_fingerprint(orders)
                st.session_state[f"batch_draft_{day}"] = plan
            except (ValueError, OSError) as exc:
                st.error(str(exc))
            finally:
                progress.empty()
        plan = st.session_state.get(f"batch_draft_{day}")
        if plan:
            current_input = input_fingerprint(orders)
            stale = (current_input != plan["输入指纹"] or pricing_settings() != plan["参数"] or
                     departure.hour*60+departure.minute != plan["发车分钟"])
            if stale:
                st.warning("订单、车辆参数或计划发车时间已变化，请重新计算后确认。")
            st.markdown("### 整批方案预览")
            display_table(pd.DataFrame([{k:v for k,v in r.items() if k not in {"路线GeoJSON", "订单编号列表"}} for r in plan["线路"]]), hide_index=True, use_container_width=True)
            st.caption(plan["算法"].replace("Dijkstra", "道路最短路径算法") + "；无法覆盖全部订单时不允许发布部分方案。")
            with st.expander("核对全部订单分配和最短距离矩阵"):
                display_table(pd.DataFrame([{k:v for k,v in r.items() if k != "路线GeoJSON"} for r in plan["订单结果"]]), hide_index=True, use_container_width=True)
                display_table(pd.DataFrame(plan["距离矩阵_m"], index=plan["矩阵标签"], columns=plan["矩阵标签"]), use_container_width=True)
            if st.button("统一确认全部线路并开始备货", type="primary", disabled=stale, use_container_width=True):
                try:
                    confirm_batch(plan)
                    st.session_state.pop(f"batch_draft_{day}", None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    if batch:
        st.success(f"本配送日 {len(batch['订单结果'])} 个订单、{len(batch['线路'])} 条线路已统一确认。")
        display_table(pd.DataFrame([{k:v for k,v in r.items() if k != "路线GeoJSON"} for r in batch["订单结果"]]), hide_index=True, use_container_width=True)
        statuses = {o["状态"] for o in orders}
        for label, target, required in [("全部车辆发出，开始配送", "配送途中", "仓库备货中"), ("确认本批次全部货物已送达", "已送达", "配送途中")]:
            if st.button(label, disabled=statuses != {required}, use_container_width=True):
                try:
                    advance_batch(day, target)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        st.caption("全部送达按钮仅在所有货物实际到达后操作；每位客户独立确认自己的签收。")
        st.download_button("下载整批距离矩阵与线路清单", workbook_bytes(batch), f"{day}_距离矩阵与线路.xlsx")
        with st.expander("查看本配送日完整最短距离矩阵（米）"):
            display_table(pd.DataFrame(batch["距离矩阵_m"], index=batch["矩阵标签"], columns=batch["矩阵标签"]), use_container_width=True)
