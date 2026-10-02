from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

import streamlit as st
from 功能组件_页面共用代码.order_state import pricing_settings, save_pricing_settings
from 功能组件_页面共用代码.ui import inject_css, render_sidebar, require_staff_access, page_title, chinese_column

inject_css()
render_sidebar()
require_staff_access()
page_title("车辆与计价", "维护车辆资源与报价；已确认方案保留确认时参数")
rates = pricing_settings()
updated = dict(rates)
with st.form("operations_parameters"):
    for kind in ("小型冷藏车", "大型冷藏车"):
        st.subheader(kind)
        cols = st.columns(3)
        for i, (suffix, label, minimum) in enumerate((("数量", "数量", 0), ("载重_kg", "载重（千克）", 1), ("续航_km", "续航（公里）", 1), ("固定成本_元", "固定成本（元/车）", 0), ("单位运输成本_元每km", "里程成本（元/公里）", 0))):
            key = kind + suffix
            updated[key] = cols[i % 3].number_input(label, min_value=float(minimum), value=float(rates[key]), step=1.0 if suffix == "数量" else 0.1, key=key)
    st.subheader("行驶速度")
    a, b = st.columns(2)
    updated["平均速度_kmh"] = a.number_input("非早高峰速度（公里/小时）", min_value=1.0, value=rates["平均速度_kmh"])
    updated["早高峰速度_kmh"] = b.number_input("07:00–09:00 速度（公里/小时）", min_value=1.0, value=rates["早高峰速度_kmh"])
    st.subheader("客户配送报价")
    cols = st.columns(2)
    for i, key in enumerate(("起步价_元", "里程价_元每km", "鲜面条_元每kg", "姜蒜_元每kg")):
        updated[key] = cols[i % 2].number_input(chinese_column(key), min_value=0.0, value=rates[key], key=key)
    st.caption("两个配送子单分别计费；客户报价与车辆固定及里程成本是不同口径。")
    submitted = st.form_submit_button("保存全部参数", type="primary")
if submitted:
    if any(updated[k + "数量"] != int(updated[k + "数量"]) for k in ("小型冷藏车", "大型冷藏车")):
        st.error("车辆数量必须是整数。")
    else:
        save_pricing_settings(updated)
        st.success("车辆、速度和报价参数已保存。")
