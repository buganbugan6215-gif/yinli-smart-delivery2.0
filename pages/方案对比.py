import pandas as pd
import plotly.express as px
import streamlit as st

from 功能组件_页面共用代码.data_loader import load_site_data
from 功能组件_页面共用代码.ui import inject_css, page_title, plotly_config, render_sidebar, require_staff_access, section_label, source_note

inject_css()
render_sidebar()
require_staff_access()
st.info("此页为竞赛成果/独立试算视图。当前客户订单的整日调度，请进入「订单与参数」。")
data = load_site_data()
page_title("方案比较", "把不同配送安排放在一起，帮助客户和企业做选择")

rows = []
for key, name in [("noodle", "鲜面条配送"), ("ginger", "姜蒜专线"), ("reuse", "车辆复用")]:
    s = data.summary.get(key, {})
    if s:
        rows.append({"方案": name, "客户数": s.get("customers"), "启用车辆": s.get("vehicles_used"), "总里程_km": s.get("total_distance_km"), "总成本_元": s.get("total_cost"), "准时率": s.get("ontime_rate"), "总载重_kg": s.get("total_load_kg")})

if not rows:
    st.warning("暂无可比较的方案数据。")
else:
    frame = pd.DataFrame(rows)
    section_label("关键指标")
    view = frame.rename(columns={"总里程_km": "预计里程（km）", "总成本_元": "预计费用（元）", "启用车辆": "配送车辆", "准时率": "预计准时送达"})
    st.dataframe(view.style.format({"预计里程（km）": "{:,.1f}", "预计费用（元）": "¥ {:,.2f}", "预计准时送达": "{:.0%}", "总载重_kg": "{:,.0f}"}, na_rep="暂无"), use_container_width=True, hide_index=True)
    metric = st.selectbox("选择要比较的内容", ["总成本_元", "总里程_km", "启用车辆", "准时率"], format_func={"总成本_元": "预计费用", "总里程_km": "预计里程", "启用车辆": "配送车辆", "准时率": "预计准时送达"}.get)
    labels = {"总成本_元": "预计费用（元）", "总里程_km": "预计里程（km）", "启用车辆": "配送车辆", "准时率": "预计准时送达"}
    fig = px.bar(frame, x="方案", y=metric, text_auto=".1%" if metric == "准时率" else ".1f", color="方案", color_discrete_sequence=["#1750df", "#ff8133", "#7b8798"])
    if metric == "准时率":
        fig.update_yaxes(tickformat=".0%")
    fig.update_yaxes(title=labels[metric])
    fig.update_layout(height=350, margin=dict(l=0,r=0,t=12,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#1d2a3a"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config=plotly_config())

    section_label("怎么选")
    st.markdown("如果更关注单一品类的服务稳定性，可以查看独立配送方案；如果更关注车辆利用和整体费用，可以进一步查看车辆复用方案。实际使用前请结合当天订单和交通情况确认。")

source_note(data.manifest)
