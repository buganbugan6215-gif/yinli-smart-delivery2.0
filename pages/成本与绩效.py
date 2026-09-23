import streamlit as st
import plotly.express as px

from 功能组件_页面共用代码.data_loader import load_site_data
from 功能组件_页面共用代码.ui import fmt_money, inject_css, page_title, plotly_config, render_sidebar, require_staff_access, section_label, source_note

inject_css()
render_sidebar()
require_staff_access()
st.info("此页为竞赛成果/独立试算视图。当前客户订单的整日调度，请进入「订单与参数」。")
data = load_site_data()
page_title("费用与服务", "看清这次配送的费用构成和服务表现")

scenario = st.selectbox("查看方案", ["鲜面条配送", "姜蒜配送", "车辆复用"])
key = {"鲜面条配送": "noodle", "姜蒜配送": "ginger", "车辆复用": "reuse"}[scenario]
summary = data.summary.get(key, {})

if not summary:
    st.warning("暂无可验证数据。")
else:
    cost = summary.get("cost_breakdown", {}) or {k: summary.get(k) for k in ["fixed_cost", "transport_cost", "cooling_cost", "time_penalty_cost", "loss_cost"] if summary.get(k) is not None}
    section_label("费用构成")
    if cost:
        cost_labels = {"fixed_cost": "车辆固定费用", "transport_cost": "运输费用", "cooling_cost": "冷藏费用", "time_penalty_cost": "时间影响费用", "loss_cost": "货损费用", "variable_cost": "运行费用"}
        frame = {"费用项目": [cost_labels.get(k, k) for k in cost], "费用（元）": list(cost.values())}
        fig = px.bar(frame, y="费用项目", x="费用（元）", orientation="h", text_auto=".2f", color_discrete_sequence=["#ff8133"])
        fig.update_layout(height=280, margin=dict(l=0,r=0,t=12,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#1d2a3a"), xaxis_title="金额（元）", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config())

    cols = st.columns(4)
    for col, (label, value) in zip(cols, [("预计总费用", fmt_money(summary.get("total_cost"))), ("每公里费用", fmt_money(summary.get("total_cost", 0) / summary.get("total_distance_km", 1)) if summary.get("total_distance_km") else "暂无"), ("按时送达客户", summary.get("ontime_customers", "暂无")), ("平均装载率", f"{summary.get('average_load_rate', 0) * 100:.1f}%" if summary.get("average_load_rate") is not None else "暂无")]):
        col.metric(label, value)

section_label("车辆成本参考")
if data.sensitivity.empty:
    st.info("暂无灵敏度分析数据。")
else:
    sens = data.sensitivity.copy()
    x = "满载能耗增幅" if "满载能耗增幅" in sens else sens.columns[0]
    y = "修正后总成本上界_元" if "修正后总成本上界_元" in sens else sens.columns[-1]
    fig = px.line(sens, x=x, y=y, markers=True, color_discrete_sequence=["#1750df"])
    fig.update_layout(height=320, margin=dict(l=0,r=0,t=12,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#1d2a3a"))
    st.plotly_chart(fig, use_container_width=True, config=plotly_config())
    with st.expander("查看详细参考数据", expanded=False):
        st.dataframe(sens, use_container_width=True, hide_index=True)

source_note(data.manifest)
