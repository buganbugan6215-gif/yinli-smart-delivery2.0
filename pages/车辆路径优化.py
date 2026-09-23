import streamlit as st
import plotly.express as px

from 功能组件_页面共用代码.data_loader import load_site_data
from 功能组件_页面共用代码.ui import fmt_money, fmt_num, inject_css, page_title, plotly_config, render_sidebar, require_staff_access, section_label, source_note

inject_css()
render_sidebar()
require_staff_access()
st.info("此页为竞赛成果/独立试算视图。当前客户订单的整日调度，请进入「订单与参数」。")
data = load_site_data()
page_title("车辆安排", "查看每辆车服务哪些客户、走多远、预计花费多少")

scenario = st.radio("配送品类", ["鲜面条配送", "姜蒜配送"], horizontal=True)
key = "noodle" if scenario == "鲜面条配送" else "ginger"
routes = data.routes.get(key)
arrivals = data.arrivals.get(key)
summary = data.summary.get(key, {})

if routes is None or routes.empty:
    st.warning("暂无路线结果数据。请先运行 数据整理脚本_生成网站数据/prepare_data.py。")
else:
    vehicle_options = ["全部车辆"] + routes["车辆编号"].astype(str).tolist() if "车辆编号" in routes else ["全部车辆"]
    vehicle = st.selectbox("查看车辆", vehicle_options)
    selected = routes if vehicle == "全部车辆" else routes[routes["车辆编号"].astype(str) == vehicle]
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [("配送路线", len(selected)), ("服务客户", int(selected["客户数"].sum()) if "客户数" in selected else "暂无"), ("预计里程", f"{selected['总里程_km'].sum():,.1f} km" if "总里程_km" in selected else "暂无"), ("预计费用", fmt_money(selected["总成本_元"].sum()) if "总成本_元" in selected else "暂无")]):
        col.metric(label, value)

    section_label("车辆安排")
    display_cols = ["车辆编号", "车型", "客户数", "配送量_kg", "装载率", "发车时刻", "回场时刻", "总里程_km", "总成本_元", "访问顺序"]
    view = selected[[c for c in display_cols if c in selected.columns]].copy().rename(columns={"客户数": "服务客户数", "配送量_kg": "配送量（kg）", "发车时刻": "出发时间", "回场时刻": "回场时间", "总里程_km": "里程（km）", "总成本_元": "费用（元）", "访问顺序": "配送顺序"})
    st.dataframe(view, use_container_width=True, hide_index=True)

    left, right = st.columns(2, gap="large")
    with left:
        if "装载率" in selected:
            fig = px.bar(selected, x="车辆编号", y="装载率", text=selected["装载率"].map(lambda v: f"{v:.0%}"), color_discrete_sequence=["#1750df"])
            fig.update_yaxes(tickformat=".0%", range=[0, 1.05])
            fig.update_layout(height=320, margin=dict(l=0,r=0,t=16,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#1d2a3a"), yaxis_title="车辆装载率", xaxis_title="车辆")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config())
    with right:
        hist = data.history.get(key, {})
        if hist.get("history"):
            with st.expander("查看系统计算过程", expanded=False):
                h = hist["history"]
                fig = px.line(h, x="iteration", y="best_cost", markers=True, color_discrete_sequence=["#ff8133"])
                fig.update_layout(height=280, margin=dict(l=0,r=0,t=16,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#1d2a3a"), xaxis_title="计算轮次", yaxis_title="当前费用")
                st.plotly_chart(fig, use_container_width=True, config=plotly_config())
        else:
            st.info("算法迭代记录暂无可验证数据。")

    if arrivals is not None and not arrivals.empty:
        section_label("客户送达情况")
        st.dataframe(arrivals, use_container_width=True, hide_index=True)

source_note(data.manifest)
