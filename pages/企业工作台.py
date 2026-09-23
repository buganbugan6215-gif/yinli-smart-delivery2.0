from io import BytesIO
import json

import pandas as pd
import streamlit as st

from 功能组件_页面共用代码.data_loader import load_site_data
from 功能组件_页面共用代码.formal_dispatch import build_formal_job, is_dijkstra_route, parse_formal_result
from 功能组件_页面共用代码.gps_simulator import arrival_risk, get_tracking_snapshot
from 功能组件_页面共用代码.order_state import STATUS_FLOW, init_orders, persist_order, pricing_settings, save_pricing_settings, set_order_status
from 功能组件_页面共用代码.ui import fmt_money, inject_css, page_title, render_sidebar, require_staff_access


inject_css()
render_sidebar()
require_staff_access()
data = load_site_data()
orders = init_orders(include_saved=True)
page_title("企业工作台", "查看当日订单、调整调度参数，并确认配送流程")

summary = data.summary.get("noodle", {})
st.markdown('<div class="ops-ribbon motion-focus"><span>今日运营</span><b>订单、参数、方案与状态统一管理</b><div class="pulse-route"><i></i></div></div>', unsafe_allow_html=True)
metrics = st.columns(4)
metrics[0].metric("已接收订单", len(orders))
metrics[1].metric("待确认方案", sum(item.get("状态") == "方案待确认" for item in orders))
metrics[2].metric("配送中", sum(item.get("状态") == "配送途中" for item in orders))
metrics[3].metric("参考方案费用", fmt_money(summary.get("total_cost")))

order_tab, parameter_tab, interface_tab = st.tabs(["订单与状态", "车辆与成本参数", "算法接口"])

with order_tab:
    @st.fragment(run_every="8s")
    def render_live_orders() -> None:
        live_orders = init_orders(include_saved=True)
        st.markdown("### 当日客户订单")
        st.caption("每 8 秒自动同步一次，其他工作人员更新的状态会出现在本页。")
        if not live_orders:
            st.markdown("<div class='empty-stage motion-reveal'><h3>当前没有客户订单</h3><p>客户提交需求后，订单会按日期和品类进入这里。</p></div>", unsafe_allow_html=True)
            return
        frame = pd.DataFrame(live_orders)
        show = [c for c in ["订单编号", "客户名称", "品类", "鲜面需求量_kg", "生姜需求量_kg", "大蒜需求量_kg", "期望窗开始_分钟", "期望窗结束_分钟", "服务时间_分钟", "状态"] if c in frame.columns]
        st.dataframe(frame[show], use_container_width=True, hide_index=True)
        export = BytesIO()
        with pd.ExcelWriter(export, engine="openpyxl") as writer:
            for product, sheet in [("鲜面条", "鲜面订单"), ("姜蒜", "姜蒜订单")]:
                frame[frame["品类"] == product].to_excel(writer, sheet_name=sheet, index=False)
        st.download_button(
            "下载当前订单 Excel",
            export.getvalue(),
            "银犁当日客户订单.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="workbench_download_orders",
        )
        labels = [f"{item['订单编号']} · {item['客户名称']} · {item['状态']}" for item in live_orders]
        chosen_label = st.selectbox("选择需要处理的订单", labels, key="live_order_choice")
        chosen = live_orders[labels.index(chosen_label)]
        left, right = st.columns([.8, 1.2], gap="large")
        with left:
            st.markdown(f"<div class='ops-order motion-reveal'><span>{chosen['品类']}</span><h3>{chosen['客户名称']}</h3><p>{float(chosen['配送重量_kg']):,.0f} kg · {chosen['期望送达']}</p><b>{chosen['状态']}</b></div>", unsafe_allow_html=True)
        with right:
            st.markdown("#### 配送流程操作")
            st.caption("必须导入本机 Dijkstra 路网结果后，才允许确认方案与发车。")
            formal_ready = is_dijkstra_route(chosen)
            if not formal_ready:
                st.download_button(
                    "1. 下载本机 Dijkstra 精算任务",
                    build_formal_job(chosen),
                    file_name=f"{chosen['订单编号']}_Dijkstra任务.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key=f"workbench_download_dijkstra_{chosen['订单编号']}",
                )
                uploaded = st.file_uploader("2. 上传本机求解结果", type=["json", "zip"], key=f"formal_{chosen['订单编号']}")
                if uploaded and st.button("导入 Dijkstra 路网结果", use_container_width=True, key=f"import_{chosen['订单编号']}"):
                    try:
                        result = parse_formal_result(uploaded.getvalue(), uploaded.name)
                        if str(result.get("订单编号", chosen["订单编号"])) != chosen["订单编号"]:
                            raise ValueError("结果文件的订单编号与当前订单不一致。")
                        chosen["路线GeoJSON"] = result["路线GeoJSON"]
                        chosen["路网最短距离_km"] = result.get("路网最短距离_km", "")
                        chosen["路网节点"] = result.get("路网节点", {})
                        chosen["数据模式"] = "Dijkstra 路网精算结果"
                        persist_order(chosen)
                        st.success("已导入 Dijkstra 路网结果，现在可确认方案。")
                        st.rerun(scope="fragment")
                    except (ValueError, json.JSONDecodeError) as exc:
                        st.error(f"导入失败：{exc}")
            else:
                st.success(f"已导入 Dijkstra 路网结果{(' · ' + str(chosen.get('路网最短距离_km')) + ' km') if chosen.get('路网最短距离_km') != '' else ''}")
            tracking_snapshot = get_tracking_snapshot(chosen, demo_factor=60.0)
            if tracking_snapshot:
                risk_level, risk_message = arrival_risk(chosen, tracking_snapshot)
                contact = str(chosen.get("联系电话", "")).strip()
                if risk_level == "error" and contact:
                    risk_message = f"{risk_message} 客户联系电话：{contact}"
                getattr(st, risk_level)(risk_message)
            current = STATUS_FLOW.index(chosen.get("状态", STATUS_FLOW[0]))
            actions = [
                ("确认配送方案并开始备货", "仓库备货中", current >= STATUS_FLOW.index("仓库备货中") or not formal_ready),
                ("车辆发出，开始配送", "配送途中", current != STATUS_FLOW.index("仓库备货中") or not formal_ready),
                ("确认货物已送达", "已送达", current != STATUS_FLOW.index("配送途中")),
            ]
            for label, target, disabled in actions:
                if st.button(label, use_container_width=True, type="primary" if target == "仓库备货中" else "secondary", disabled=disabled, key=f"status_{chosen['订单编号']}_{target}"):
                    set_order_status(chosen, target)
                    st.success(f"订单状态已更新为：{target}")
                    st.rerun(scope="fragment")
    render_live_orders()

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
    st.markdown("### 当日方案生成链路")
    st.markdown("""
    <div class="integration-rail motion-reveal">
      <div class="ready"><span>01 订单</span><b>已接入</b><small>按日期与品类生成 Excel，保存经纬度、分钟时间窗和服务时间。</small></div>
      <div class="ready"><span>02 空间数据</span><b>接口就绪</b><small>订单经纬度采用 EPSG:4326，可用于生成客户点图层。</small></div>
      <div><span>03 最短路</span><b>待本机运行</b><small>读取成都路网，通过 Dijkstra 生成当日客户最短距离矩阵。</small></div>
      <div><span>04 优化方案</span><b>待算法接入</b><small>读取当日矩阵与参数，生成车辆、路线、成本和准时率。</small></div>
    </div>
    """, unsafe_allow_html=True)
    st.info("公网端不运行大型路网和耗时优化程序。正式使用时，由本机计算程序生成结果文件，再上传平台展示和确认。")
