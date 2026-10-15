"""调度、地图、分析共享同一个配送日仓库选择与计算结果。"""
import pandas as pd
import streamlit as st
from 功能组件_页面共用代码 import warehouses
from 功能组件_页面共用代码.batch_dispatch import get_batch, get_draft, day_orders, input_fingerprint, save_draft
from 功能组件_页面共用代码.order_state import pricing_settings

RELEASE_VERSION = "2026-10-15-route-eta-v28"


def selector(day, confirmed=None, selected_count=None):
    if confirmed is None and selected_count is None:
        confirmed = get_batch(day)
    previous = confirmed.get("仓库数量", 1) if confirmed else (selected_count if selected_count is not None else warehouses.selection(day))
    widget_key = f"warehouse_mode_{day}"
    flag = f"warehouse_changed_{day}"
    # 只在真实切换事件保存，刷新或其他工作人员变更不反向覆盖数据库。
    st.session_state[widget_key] = previous
    def change():
        try:
            warehouses.save_selection(day, st.session_state[widget_key])
            st.session_state[flag] = True
        except ValueError as exc:
            st.session_state[flag] = str(exc)
    with st.container(key="warehouse_mode", border=True):
        chosen = st.radio("配送仓库", [1, 2], format_func=warehouses.label,
                          horizontal=True, disabled=bool(confirmed), key=widget_key, on_change=change)
        st.caption("双仓使用指定的 D6 新增配送点；共享配送车队，按品类分别补货。" if not confirmed else "已确认批次按发布时仓库点位执行。")
    event = st.session_state.pop(flag, False)
    if isinstance(event, str):
        st.error(event)
    changed = event is True and not confirmed
    return chosen, changed


def active_plan(day):
    batch = get_batch(day)
    if batch:
        return batch
    plan = get_draft(day)
    if plan and warehouses.current(plan) and plan["参数"] == pricing_settings() and plan["输入指纹"] == input_fingerprint(day_orders(day)):
        return plan
    return None


def calculate(day, departure=360):
    from 功能组件_页面共用代码.batch_solver import solve_batch
    orders = day_orders(day)
    progress = st.progress(0.0, text="正在计算所选仓库的道路矩阵…")
    try:
        plan = solve_batch(orders, pricing_settings(), departure,
                           lambda value, message: progress.progress(value, text=message),
                           warehouse_count=warehouses.selection(day))
        plan["输入指纹"] = input_fingerprint(orders)
        return save_draft(plan)
    finally:
        progress.empty()


def render_cost(plan):
    from 功能组件_页面共用代码.ui import display_table
    if "成本" not in plan:
        st.caption("此为历史单仓方案，保留原有成本口径。")
        return
    costs = plan["成本"]
    with st.container(key="warehouse_result", border=True):
        st.markdown(f"### {warehouses.label(plan['仓库数量'])}")
        a, b, c = st.columns(3)
        a.metric("末端配送里程", f"{sum(r['总里程_km'] for r in plan['线路']):.2f} 公里")
        b.metric("运输行驶费", f"¥ {costs['运输行驶费合计_元']:,.2f}")
        c.metric("计划可比费用 · 未含新增场地", f"¥ {costs['未含新增场地费_元']:,.2f}")
        counts = pd.DataFrame(plan["订单结果"]).groupby("出发仓库").size().to_dict()
        st.caption(" · ".join(f"{d['名称']}：{counts.get(d['名称'], 0)} 单" for d in plan["仓库"]))
        if costs["新增场地费_元"] is None:
            st.caption("新增场地费尚未提供，未计入计划可比费用。")
        st.caption("含现有车队全日固定费、末端运输与制冷、货损和分品类补货。客户时间窗为硬约束，当前可行方案罚金为零。")
        with st.expander("查看费用分项与仓间补货"):
            display_table(pd.DataFrame([{"费用项目":k.removesuffix("_元"), "金额（元）":round(v, 2) if v is not None else None} for k,v in costs.items()]), hide_index=True, use_container_width=True)
            if plan["补货"]:
                display_table(pd.DataFrame([{k:v for k,v in t.items() if k != "路线GeoJSON"} for t in plan["补货"]]).round(2), hide_index=True, use_container_width=True)


def render_map(plan, key="warehouse-map"):
    from 功能组件_页面共用代码.maps import plan_map
    from streamlit_folium import st_folium
    detailed = st.toggle("显示细支道路（加载更多地图数据）", key=key+"-roads")
    fmap = plan_map(plan, detailed=detailed)
    st.caption("蓝色实线：鲜面条 · 橙色虚线：姜蒜 · 灰蓝虚线：仓间补货")
    st_folium(fmap, use_container_width=True, height=560, returned_objects=[], key=key+str(detailed))


def route_table(plan):
    from 功能组件_页面共用代码.ui import display_table
    rows = []
    for route in plan["线路"]:
        minute = int(route.get("发车时间_分钟", plan["发车分钟"]))
        rows.append({"线路编号": route["线路编号"], "出发仓库": route.get("出发仓库", "原配送中心"),
                     "车辆编号": route["车辆编号"], "品类": route.get("品类", ""),
                     "订单数": len(route["订单编号列表"]), "发车时间": f"{minute//60:02d}:{minute%60:02d}",
                     "货量_kg": round(route["总重量_kg"], 2), "里程_km": round(route["总里程_km"], 2)})
    display_table(pd.DataFrame(rows), hide_index=True, use_container_width=True)
