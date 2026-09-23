from io import BytesIO
from datetime import time
import pandas as pd
import streamlit as st

from 功能组件_页面共用代码.order_state import init_orders, pricing_settings, save_pricing_settings
from 功能组件_页面共用代码.delivery_calendar import beijing_now, delivery_day, batch_closed, cutoff_label
from 功能组件_页面共用代码.batch_dispatch import day_orders, get_batch, input_fingerprint, confirm_batch, advance_batch, workbook_bytes
from 功能组件_页面共用代码.batch_solver import solve_batch
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar, require_staff_access

inject_css()
render_sidebar()
require_staff_access()
page_title("企业工作台", "按配送日汇总全部订单，一次计算矩阵，一次确认全部线路")
st.info("收单规则：北京时间每日 20:00 截止次日订单；19:59:59 及以前提交归次日，20:00:00 起提交归后天。")
order_tab, parameter_tab, interface_tab = st.tabs(["整日订单与调度", "车辆与成本参数", "调度说明"])

with order_tab:
    available = sorted({str(o.get("期望送达日期")) for o in init_orders(include_saved=True) if o.get("期望送达日期")}, reverse=True)
    if not available:
        st.info("暂无订单。客户提交后将按配送日期出现在这里。")
    else:
        day = st.selectbox("配送日期", available)
        st.caption(f"截止时间：{cutoff_label(day)}")
        if st.button("刷新本配送日订单"):
            st.rerun()
        orders = day_orders(day)
        closed = batch_closed(day)
        batch = get_batch(day)
        stats = st.columns(3)
        stats[0].metric("本批次订单", len(orders))
        stats[1].metric("总货量 kg", f"{sum(float(o['配送重量_kg']) for o in orders):,.1f}")
        stats[2].metric("批次状态", "已统一确认" if batch else "已截止，待调度" if closed else "正在收单")
        columns = ["订单编号", "客户名称", "品类", "配送重量_kg", "期望送达日期", "最早到达", "最晚到达", "状态", "线路编号", "配送顺序"]
        frame = pd.DataFrame(orders)
        st.dataframe(frame[[c for c in columns if c in frame.columns]], use_container_width=True, hide_index=True)
        excel = BytesIO()
        with pd.ExcelWriter(excel, engine="openpyxl") as writer:
            frame.drop(columns=["路线GeoJSON", "报价明细"], errors="ignore").to_excel(writer, index=False, sheet_name="当日订单")
        st.download_button("下载本配送日全部订单 Excel", excel.getvalue(), f"{day}_全部订单.xlsx")
        if not closed:
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
                st.dataframe(pd.DataFrame([{k:v for k,v in r.items() if k not in {"路线GeoJSON", "订单编号列表"}} for r in plan["线路"]]), hide_index=True, use_container_width=True)
                st.caption(plan["算法"] + "；无法覆盖全部订单时不允许发布部分方案。")
                with st.expander("核对全部订单分配和最短距离矩阵"):
                    st.dataframe(pd.DataFrame([{k:v for k,v in r.items() if k != "路线GeoJSON"} for r in plan["订单结果"]]), hide_index=True, use_container_width=True)
                    st.dataframe(pd.DataFrame(plan["距离矩阵_m"], index=plan["矩阵标签"], columns=plan["矩阵标签"]), use_container_width=True)
                if st.button("统一确认全部线路并开始备货", type="primary", disabled=stale, use_container_width=True):
                    try:
                        confirm_batch(plan)
                        st.session_state.pop(f"batch_draft_{day}", None)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        if batch:
            st.success(f"本配送日 {len(batch['订单结果'])} 个订单、{len(batch['线路'])} 条线路已统一确认。")
            st.dataframe(pd.DataFrame([{k:v for k,v in r.items() if k != "路线GeoJSON"} for r in batch["订单结果"]]), hide_index=True, use_container_width=True)
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
                st.dataframe(pd.DataFrame(batch["距离矩阵_m"], index=batch["矩阵标签"], columns=batch["矩阵标签"]), use_container_width=True)
        feedback = [o for o in orders if o.get("异常反馈")]
        if feedback:
            st.markdown("### 本批次异常反馈")
            for o in feedback:
                st.write({"订单编号": o["订单编号"], "联系电话": o.get("联系电话"), **o["异常反馈"]})

with parameter_tab:
    st.markdown("### 调度参数")
    st.caption("参数用于客户报价和后续求解接口；正式路线需接入当日最短距离矩阵与优化算法。")
    rates = pricing_settings()
    with st.form("operations_parameters"):
        st.markdown("#### 小型冷藏车")
        s1, s2, s3, s4, s5 = st.columns(5)
        small_count = s1.number_input("数量", min_value=0.0, value=rates["小型冷藏车数量"], step=1.0)
        small_load = s2.number_input("载重 kg", min_value=1.0, value=rates["小型冷藏车载重_kg"])
        small_fixed = s3.number_input("固定成本 元", min_value=0.0, value=rates["小型冷藏车固定成本_元"])
        small_transport = s4.number_input("运输成本 元/km", min_value=0.0, value=rates["小型冷藏车单位运输成本_元每km"])
        small_range = s5.number_input("续航 km", min_value=1.0, value=rates["小型冷藏车续航_km"])
        st.markdown("#### 大型冷藏车")
        l1, l2, l3, l4, l5 = st.columns(5)
        large_count = l1.number_input("数量 ", min_value=0.0, value=rates["大型冷藏车数量"], step=1.0)
        large_load = l2.number_input("载重 kg ", min_value=1.0, value=rates["大型冷藏车载重_kg"])
        large_fixed = l3.number_input("固定成本 元 ", min_value=0.0, value=rates["大型冷藏车固定成本_元"])
        large_transport = l4.number_input("运输成本 元/km ", min_value=0.0, value=rates["大型冷藏车单位运输成本_元每km"])
        large_range = l5.number_input("续航 km ", min_value=1.0, value=rates["大型冷藏车续航_km"])
        st.markdown("#### 运营成本与速度")
        a, b, c, d = st.columns(4)
        cooling_drive = a.number_input("配送制冷 元/小时", min_value=0.0, value=rates["配送制冷系数_元每小时"])
        cooling_service = b.number_input("服务制冷 元/小时", min_value=0.0, value=rates["服务制冷系数_元每小时"])
        early = c.number_input("早到惩罚 元/小时", min_value=0.0, value=rates["早到惩罚_元每小时"])
        late = d.number_input("晚到惩罚 元/小时", min_value=0.0, value=rates["晚到惩罚_元每小时"])
        e, f, g, h = st.columns(4)
        loss_drive = e.number_input("运输货损率", min_value=0.0, max_value=1.0, value=rates["运输货损率"], format="%.4f")
        loss_service = f.number_input("服务货损率", min_value=0.0, max_value=1.0, value=rates["服务货损率"], format="%.4f")
        avg_speed = g.number_input("平均速度 km/h", min_value=1.0, value=rates["平均速度_kmh"])
        peak_speed = h.number_input("早高峰速度 km/h", min_value=1.0, value=rates["早高峰速度_kmh"])
        st.markdown("#### 报价参数")
        p1, p2, p3, p4, p5 = st.columns(5)
        start_price = p1.number_input("起步价 元", min_value=0.0, value=rates["起步价_元"])
        mileage_price = p2.number_input("里程价 元/km", min_value=0.0, value=rates["里程价_元每km"])
        noodle_price = p3.number_input("鲜面单价 元/kg", min_value=0.0, value=rates["鲜面条单价_元每kg"])
        ginger_price = p4.number_input("生姜单价 元/kg", min_value=0.0, value=rates["生姜单价_元每kg"])
        garlic_price = p5.number_input("大蒜单价 元/kg", min_value=0.0, value=rates["大蒜单价_元每kg"])
        submitted = st.form_submit_button("保存全部参数", type="primary", use_container_width=True)
    if submitted:
        updated = dict(rates)
        updated.update({
            "小型冷藏车数量": small_count, "小型冷藏车载重_kg": small_load, "小型冷藏车固定成本_元": small_fixed, "小型冷藏车单位运输成本_元每km": small_transport, "小型冷藏车续航_km": small_range,
            "大型冷藏车数量": large_count, "大型冷藏车载重_kg": large_load, "大型冷藏车固定成本_元": large_fixed, "大型冷藏车单位运输成本_元每km": large_transport, "大型冷藏车续航_km": large_range,
            "配送制冷系数_元每小时": cooling_drive, "服务制冷系数_元每小时": cooling_service, "早到惩罚_元每小时": early, "晚到惩罚_元每小时": late,
            "运输货损率": loss_drive, "服务货损率": loss_service, "平均速度_kmh": avg_speed, "早高峰速度_kmh": peak_speed,
            "起步价_元": start_price, "里程价_元每km": mileage_price, "鲜面条单价_元每kg": noodle_price, "生姜单价_元每kg": ginger_price, "大蒜单价_元每kg": garlic_price,
        })
        save_pricing_settings(updated)
        st.success("车辆、成本、速度和货损参数已保存。")

with interface_tab:
    st.markdown("### 每个配送日只确认一份完整方案")
    st.write("1. 北京时间 20:00 前提交归入次日配送；20:00 起提交归入后天配送。")
    st.write("2. 截止后工作人员选择配送日，网页一次计算配送中心与所有客户之间的有向最短距离矩阵。")
    st.write("3. 使用车辆载重、续航、收货时间窗和服务时间生成线路，整批检查后统一确认并锁定。")
    st.write("4. 客户用订单编号和联系电话后四位核验，只能查看自己的配送日期、线路、车辆与顺序。")
    st.caption("多车线路为可行启发式方案，不保证全局最优；路网方向和道路长度来自仓库内的竞赛货车路网。")
