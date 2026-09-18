import streamlit as st

from 功能组件_页面共用代码.matlab_bridge import run_noodle_model
from 功能组件_页面共用代码.planner import generate_plan, is_result_json, normalize_customers, read_uploaded_file, result_json_to_plan
from 功能组件_页面共用代码.ui import fmt_money, inject_css, page_title, plotly_config, render_sidebar, require_staff_access, section_label, source_note

inject_css()
render_sidebar()
require_staff_access()
page_title("数据导入与方案生成", "上传订单后，快速得到一份清晰的配送安排")

st.markdown("""
<div class="hero-panel">
  <div>
    <div class="hero-kicker">上传订单 · 自动整理</div>
    <h2>上传订单，直接得到配送安排。</h2>
    <p>支持 Excel、CSV 和已保存的结果 JSON。系统会整理车辆、配送顺序、预计到达和费用，结果只保存在当前会话。</p>
  </div>
  <div class="hero-index"><span>结果内容</span><strong>路线 · 车辆 · 费用</strong><small>可下载配送清单</small></div>
</div>
""", unsafe_allow_html=True)

uploaded_files = st.file_uploader("上传客户订单或结果文件", type=["xlsx", "xls", "csv", "json"], accept_multiple_files=True, help="客户表至少包含客户编号、经度、纬度、需求量。")
product = st.selectbox("配送品类", ["鲜面条", "姜蒜"], index=0)

st.caption("如果上传的是客户订单，系统会按以下默认值快速生成一份配送草案。")
with st.expander("正式 MATLAB 模型", expanded=False):
    st.write("该入口运行团队的 `solve_first_question_noodle.m`。它仅适用于题目原始的 30 个鲜面条客户、最短距离矩阵和车辆参数，不会把任意上传表伪装成正式求解。")
    if st.button("运行正式鲜面条 MATLAB 模型", use_container_width=True):
        with st.spinner("MATLAB 正在执行多起点构造与邻域搜索..."):
            ok, message = run_noodle_model()
        (st.success if ok else st.error)(message)
with st.expander("调整计算参数", expanded=False):
    c1, c2, c3 = st.columns(3)
    capacity = c1.number_input("单车额定载重（kg）", min_value=1.0, value=1500.0, step=100.0)
    vehicles = c2.number_input("计划车辆数", min_value=1, value=6, step=1)
    speed = c3.number_input("平均速度（km/h）", min_value=1.0, value=35.0, step=1.0)
    c4, c5, c6 = st.columns(3)
    fixed = c4.number_input("单车固定成本（元）", min_value=0.0, value=200.0, step=50.0)
    transport = c5.number_input("运输成本（元/km）", min_value=0.0, value=2.5, step=0.1)
    cooling = c6.number_input("制冷成本（元/km）", min_value=0.0, value=0.45, step=0.05)
    c7, c8 = st.columns(2)
    late_penalty = c7.number_input("迟到惩罚（元/min）", min_value=0.0, value=0.5, step=0.1)
    loss_cost = c8.number_input("货损成本（元/kg）", min_value=0.0, value=0.0336, step=0.005, format="%.4f")

if st.button("生成方案", type="primary", use_container_width=True):
    if not uploaded_files:
        st.error("请先上传至少一个客户需求表或最终结果 JSON。")
    else:
        try:
            parsed = [read_uploaded_file(file) for file in uploaded_files]
            json_result = next((value for _, value in parsed if is_result_json(value)), None)
            if json_result is not None:
                plan = result_json_to_plan(json_result, product)
            else:
                table = next((value for _, value in parsed if hasattr(value, "columns")), None)
                if table is None:
                    raise ValueError("没有找到可识别的客户表。")
                customers = normalize_customers(table, product)
                plan = generate_plan(customers, {"capacity_kg": capacity, "vehicles": vehicles, "speed_kmh": speed, "fixed_cost": fixed, "transport_cost_per_km": transport, "cooling_cost_per_km": cooling, "late_penalty_per_min": late_penalty, "loss_cost_per_kg": loss_cost})
            st.session_state["uploaded_plan"] = plan
            st.success(f"方案已生成：{plan['mode']}。")
        except Exception as exc:
            st.error(f"方案生成失败：{exc}")

plan = st.session_state.get("uploaded_plan")
if plan:
    summary = plan["summary"]
    section_label("配送结果")
    st.info(summary.get("solution_type", plan["mode"]))
    cols = st.columns(5)
    for col, (label, value) in zip(cols, [("服务客户", summary.get("customers", "暂无")), ("配送车辆", summary.get("vehicles_used", "暂无")), ("预计里程", f"{summary.get('total_distance_km', 0):,.1f} km"), ("预计费用", fmt_money(summary.get("total_cost"))), ("预计准时送达", f"{summary.get('ontime_rate', 0) * 100:.0f}%")]):
        col.metric(label, value)
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.markdown("### 车辆与访问顺序")
        route_columns = ["车辆编号", "产品", "客户数", "配送量_kg", "装载率", "发车时刻", "回场时刻", "总里程_km", "总成本_元", "访问顺序"]
        route_view = plan["routes"][[column for column in route_columns if column in plan["routes"].columns]].copy()
        route_view = route_view.rename(columns={"客户数": "服务客户数", "配送量_kg": "配送量（kg）", "装载率": "装载率", "总里程_km": "里程（km）", "总成本_元": "费用（元）", "访问顺序": "配送顺序"})
        st.dataframe(route_view, use_container_width=True, hide_index=True)
    with right:
        st.markdown("### 成本分解")
        cost = summary.get("cost_breakdown", {})
        if cost:
            import plotly.express as px
            labels = {"fixed_cost": "固定成本", "transport_cost": "运输成本", "cooling_cost": "制冷成本", "time_penalty_cost": "时间窗惩罚", "loss_cost": "货损成本"}
            chart = {"成本类型": [labels.get(k, k) for k in cost], "成本（元）": list(cost.values())}
            fig = px.bar(chart, y="成本类型", x="成本（元）", orientation="h", text_auto=".2f", color_discrete_sequence=["#ff8133"])
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=12, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#1d2a3a"))
            st.plotly_chart(fig, use_container_width=True, config=plotly_config())
    st.markdown("### 客户到达明细")
    arrival_columns = ["车辆编号", "产品", "客户编号", "到达时刻", "开始服务时刻", "早到偏差_min", "迟到偏差_min", "期望窗内", "到达时刻_分钟", "开始服务时刻_分钟"]
    arrival_view = plan["arrivals"][[column for column in arrival_columns if column in plan["arrivals"].columns]].copy()
    arrival_view = arrival_view.rename(columns={"早到偏差_min": "提前（分钟）", "迟到偏差_min": "迟到（分钟）", "期望窗内": "按时送达"})
    st.dataframe(arrival_view, use_container_width=True, hide_index=True)
    d1, d2 = st.columns(2)
    d1.download_button("下载车辆路线 CSV", plan["routes"].to_csv(index=False).encode("utf-8-sig"), "生成方案_车辆路线.csv", "text/csv", use_container_width=True)
    d2.download_button("下载客户到达 CSV", plan["arrivals"].to_csv(index=False).encode("utf-8-sig"), "生成方案_客户到达明细.csv", "text/csv", use_container_width=True)
    if plan["mode"] == "快速可行初算":
        st.warning("这是一版基于坐标距离的快速可行初算。要用于论文和正式答辩结论，仍应把同一批数据送入你们的正式 Dijkstra + ALNS 模型复算。")
else:
    st.markdown("### 输入格式")
    st.markdown("客户表至少需要四列：客户编号、经度、纬度、需求量。若有时间窗，可提供期望开始、期望结束和服务时间。上传现有最终结果 JSON 时，页面直接展示 JSON 中的车辆、路线、成本和到达明细。")

source_note({"generated_at": "当前会话", "sources": []})
