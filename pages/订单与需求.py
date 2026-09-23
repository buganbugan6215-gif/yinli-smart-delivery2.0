import streamlit as st
import plotly.express as px

from 功能组件_页面共用代码.data_loader import load_site_data
from 功能组件_页面共用代码.ui import inject_css, page_title, plotly_config, render_sidebar, require_staff_access, section_label, source_note

inject_css()
render_sidebar()
require_staff_access()
st.info("此页为竞赛成果/独立试算视图。当前客户订单的整日调度，请进入「订单与参数」。")
data = load_site_data()
page_title("订单概览", "先看订单总量，再按品类和需求筛选")

if data.customers.empty:
    st.warning("暂无客户明细。请先运行 数据整理脚本_生成网站数据/prepare_data.py。")
else:
    frame = data.customers.copy()
    categories = ["全部"] + sorted(frame["产品"].dropna().astype(str).unique().tolist()) if "产品" in frame else ["全部"]
    category = st.selectbox("产品筛选", categories)
    if category != "全部":
        frame = frame[frame["产品"] == category]
    if "需求量_kg" in frame:
        low, high = int(frame["需求量_kg"].min()), int(frame["需求量_kg"].max())
        demand = st.slider("需求量范围（kg）", low, max(high, low + 1), (low, high))
        frame = frame[frame["需求量_kg"].between(*demand)]

    cols = st.columns(4)
    for col, (label, value) in zip(cols, [("当前客户", len(frame)), ("总需求量", f"{frame['需求量_kg'].sum():,.0f} kg" if "需求量_kg" in frame else "暂无"), ("平均每客户", f"{frame['需求量_kg'].mean():,.1f} kg" if "需求量_kg" in frame else "暂无"), ("配送品类", frame['产品'].nunique() if '产品' in frame else "暂无")]):
        col.metric(label, value)

    section_label("订单结构")
    left, right = st.columns(2, gap="large")
    with left:
        if "产品" in frame and "需求量_kg" in frame:
            product = frame.groupby("产品", as_index=False)["需求量_kg"].sum()
            fig = px.pie(product, names="产品", values="需求量_kg", hole=.58, color="产品", color_discrete_map={"鲜面条": "#1750df", "姜蒜": "#ff8133"})
            fig.update_traces(textposition="outside", texttemplate="%{label}<br>%{value:,.0f} kg", hovertemplate="%{label}: %{value:,.1f} kg<extra></extra>")
            fig.update_layout(height=330, margin=dict(l=10,r=10,t=16,b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#1d2a3a"), showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config=plotly_config())
    with right:
        if "时间窗" in frame.columns:
            frame["送达时段"] = frame["时间窗"].astype(str).str[:3].map(lambda value: f"{int(value) // 60:02d}:{int(value) % 60:02d}" if value.isdigit() else value)
            order = sorted(frame["送达时段"].dropna().unique().tolist())
            fig = px.histogram(frame, x="送达时段", color="产品" if "产品" in frame else None, barmode="group", category_orders={"送达时段": order}, color_discrete_map={"鲜面条": "#1750df", "姜蒜": "#ff8133"})
            fig.update_layout(height=330, margin=dict(l=10,r=10,t=16,b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#1d2a3a"), legend_title_text="")
            fig.update_xaxes(title="最早送达时间")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config())
        else:
            st.info("时间窗分布暂无可验证数据。")

    section_label("客户清单")
    st.caption("以下只显示业务确认需要的字段，完整数据仍保留在网站数据文件中。")
    view_columns = ["客户编号", "产品", "经度", "纬度", "需求量_kg", "时间窗", "服务时间_分"]
    view = frame[[column for column in view_columns if column in frame.columns]].copy()
    view = view.rename(columns={"需求量_kg": "需求量（kg）", "时间窗": "期望送达时间", "服务时间_分": "服务时间（分钟）"})
    with st.expander("查看客户清单", expanded=False):
        st.dataframe(view, use_container_width=True, hide_index=True)

source_note(data.manifest)
