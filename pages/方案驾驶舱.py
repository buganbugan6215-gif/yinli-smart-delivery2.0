import streamlit as st
import plotly.express as px
import folium
from streamlit_folium import st_folium

from 功能组件_页面共用代码.data_loader import load_site_data, get_summary
from 功能组件_页面共用代码.maps import add_customer_points, add_route_features, add_zoom_detail_behavior, create_chengdu_map
from 功能组件_页面共用代码.ui import fmt_money, fmt_num, inject_css, page_title, plotly_config, render_sidebar, require_staff_access, section_label, source_note

inject_css()
render_sidebar()
require_staff_access()
data = load_site_data()
page_title("配送总览", "先看结果，再查看路线、车辆和费用")

scenario = st.selectbox("查看方案", ["鲜面条配送", "姜蒜配送", "车辆复用"], index=0)
key = {"鲜面条配送": "noodle", "姜蒜配送": "ginger", "车辆复用": "reuse"}[scenario]
summary = get_summary(data, key)

if not summary:
    st.warning("暂无可验证数据。请先运行 数据整理脚本_生成网站数据/prepare_data.py。")
else:
    cols = st.columns(5)
    metrics = [
        ("服务客户", summary.get("customers")),
        ("配送车辆", summary.get("vehicles_used")),
        ("预计里程", f"{summary.get('total_distance_km', 0):,.1f} km"),
        ("预计费用", fmt_money(summary.get("total_cost"))),
        ("预计准时送达", f"{summary.get('ontime_rate', 0) * 100:.0f}%"),
    ]
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value if value is not None else "暂无")

    section_label("结果解读")
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        plain = {"noodle": "面条订单按客户需求和送达时间安排车辆。", "ginger": "姜蒜订单按品类需求和送达时间安排车辆。", "reuse": "两类订单按照车辆可用时间安排配送任务。"}
        st.markdown(f"### {plain.get(key, '当前配送方案')}")
        load_text = f"，共配送 **{fmt_num(summary.get('total_load_kg'), 0)} kg**" if summary.get("total_load_kg") is not None else ""
        st.markdown(f"当前方案服务 **{summary.get('customers', '暂无')}** 个客户，安排 **{summary.get('vehicles_used', '暂无')}** 辆车，预计完成 **{summary.get('total_distance_km', 0):,.1f} km** 配送{load_text}。")
        checks = summary.get("validations", {})
        if checks:
            st.markdown("#### 服务检查")
            check_names = {"all_customers_once": "客户覆盖完整", "capacity": "车辆没有超载", "coordinates_available": "客户位置完整", "车辆时段不重叠": "车辆时间不冲突", "跨产品复用已记录": "复用安排已记录"}
            check_cols = st.columns(3)
            for col, (name, passed) in zip(check_cols * 3, list(checks.items())[:9]):
                label = check_names.get(name, name)
                status_class = "status-good" if passed else "status-warn"
                status_text = "已确认" if passed else "需复核"
                col.markdown(f"<span class='{status_class}'>{status_text} - {label}</span>", unsafe_allow_html=True)
        with st.expander("查看计算说明"):
            st.caption(summary.get("solution_type", "页面读取已保存的配送结果。"))
    with right:
        cost = summary.get("cost_breakdown", {})
        if not cost:
            cost = {k: summary.get(k) for k in ["fixed_cost", "transport_cost", "cooling_cost", "time_penalty_cost", "loss_cost"] if summary.get(k) is not None}
        if cost:
            labels = {"fixed_cost": "车辆固定费用", "transport_cost": "运输费用", "cooling_cost": "冷藏费用", "time_penalty_cost": "时间影响费用", "loss_cost": "货损费用", "variable_cost": "运行费用"}
            frame = {"费用项目": [labels.get(k, k) for k in cost], "费用（元）": list(cost.values())}
            fig = px.bar(frame, x="费用（元）", y="费用项目", orientation="h", text_auto=".0f", color_discrete_sequence=["#ff8133"])
            fig.update_layout(margin=dict(l=0, r=0, t=16, b=0), height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#1d2a3a"), showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config=plotly_config())
        else:
            st.info("成本分项暂无可验证数据。")

source_note(data.manifest)

section_label("全部配送路线")
map_filter = st.radio("地图显示", ["全部路线", "鲜面专线", "姜蒜专线"], horizontal=True)
product_code = {"全部路线": None, "鲜面专线": "N", "姜蒜专线": "G"}[map_filter]
fmap, minor_layer = create_chengdu_map(zoom_start=10)
add_route_features(fmap, data.geojson.get("routes", {}), product_code)
add_customer_points(fmap, data.geojson.get("customers", {}), product_code)
add_zoom_detail_behavior(fmap, minor_layer, threshold=13)
folium.LayerControl(collapsed=True, position="topright").add_to(fmap)
st_folium(fmap, use_container_width=True, height=620, returned_objects=[])
st.caption("工作人员可按品类查看全部配送路径和客户点；放大地图后自动显示细支道路。")
