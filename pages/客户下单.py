from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

import streamlit as st
from 功能组件_页面共用代码.ui import chinese_multiselect
from 功能组件_页面共用代码.ui import display_table
from 功能组件_页面共用代码.calendar_runtime import ensure_current_calendar

ensure_current_calendar()

from datetime import time
from 功能组件_页面共用代码.delivery_calendar import delivery_day, cutoff_label

from 功能组件_页面共用代码.order_state import create_order_group, estimate_delivery_fee, geocode_address, init_orders
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar


inject_css()
render_sidebar()
init_orders()
page_title("客户下单", "填写收货信息和送达时间，提交前即可查看预估费用")

st.markdown("""
<div class="service-hero motion-focus">
  <div><h2>把配送需求交给我们。</h2><p>选择收货日期、货物和时间窗。北京时间 20:00 前最早次日配送，20:00 起最早后天配送，也可预约更晚日期。</p></div>
  <div class="service-orbit"><span></span><b>订单正在进入配送网络</b></div>
</div>
""", unsafe_allow_html=True)

st.markdown("### 收货信息")
c1, c2 = st.columns(2)
customer = c1.text_input("客户名称", placeholder="例如：青羊区某门店")
contact = c2.text_input("联系人", placeholder="收货联系人")
c3, c4 = st.columns([1.4, 1])
address = c3.text_input("收货地址", placeholder="请填写详细地址，例如：成都市青羊区人民中路一段")
phone = c4.text_input("联系电话", placeholder="用于配送联系")

if "order_coordinates" not in st.session_state:
    st.session_state["order_coordinates"] = None
if st.session_state.get("geocoded_address") != address.strip():
    st.session_state["order_coordinates"] = None
if st.button("识别地址坐标", disabled=not address.strip()):
    with st.spinner("正在核对地址..."):
        coordinates = geocode_address(address)
    st.session_state["order_coordinates"] = coordinates
    st.session_state["geocoded_address"] = address.strip()
    if not coordinates:
        st.warning("未识别到坐标。请补充城市、区县、街道或门牌号后重试，也可手工填写坐标。")
coordinates = st.session_state.get("order_coordinates")
geo_left, geo_right = st.columns(2)
manual_lon = geo_left.number_input("经度（识别失败时可手工填写）", value=float(coordinates[0]) if coordinates else 0.0, format="%.6f")
manual_lat = geo_right.number_input("纬度（识别失败时可手工填写）", value=float(coordinates[1]) if coordinates else 0.0, format="%.6f")
if manual_lon and manual_lat:
    coordinates = (manual_lon, manual_lat, coordinates[2] if coordinates else "手工填写坐标", coordinates[3] if coordinates and len(coordinates) > 3 else "手工坐标")
if coordinates:
    st.success(f"已通过{coordinates[3]}定位：{coordinates[2]}")
    st.caption(f"地理坐标：{coordinates[0]:.6f}, {coordinates[1]:.6f}。提交前请核对识别地点是否与收货地址一致。")
else:
    st.caption("配置高德地图服务密钥后优先使用高德；未配置时自动使用 开放街道地图。识别结果缓存 24 小时。")

st.markdown("### 配送内容")
earliest_date = delivery_day()
date_expired = st.session_state.get("requested_delivery_date", earliest_date) < earliest_date
if date_expired:
    st.session_state["requested_delivery_date"] = earliest_date
    st.warning("原配送日期已截止，已显示新的最早可配送日；请核对日期后重新提交。")
delivery_date = st.date_input("期望配送日期", value=earliest_date, min_value=earliest_date,
                              key="requested_delivery_date", format="YYYY-MM-DD")
st.info(f"本次下单配送日：{delivery_date}。当前最早可配送日：{earliest_date}；可选择后天或更晚日期。")
st.caption(f"所选批次截止时间：{cutoff_label(delivery_date)}。北京时间每日 20:00 截止次日订单，提交时再次核验所选日期。")
products = chinese_multiselect("配送品类（可同时选择）", ["鲜面条", "姜蒜"], default=["鲜面条"])
noodle_kg = ginger_kg = garlic_kg = 0.0
if "鲜面条" in products:
    noodle_kg = st.number_input("鲜面需求量（千克）", min_value=0.0, value=100.0, step=10.0)
if "姜蒜" in products:
    g, a = st.columns(2)
    ginger_kg = g.number_input("生姜需求量（千克）", min_value=0.0, value=50.0, step=5.0)
    garlic_kg = a.number_input("大蒜需求量（千克）", min_value=0.0, value=50.0, step=5.0)
st.caption("同时选择两种品类，会生成同一总单下的两个配送子单，分别计费、分车配送、独立签收。")
t1, t2 = st.columns(2)
expected_time = t1.time_input("最早到达时间", value=time(8, 0))
latest_time = t2.time_input("最晚送达时间", value=time(18, 0))
quotes = []
for product, quantity in (("鲜面条", noodle_kg), ("姜蒜", ginger_kg + garlic_kg)):
    if quantity > 0:
        quote = estimate_delivery_fee(product, quantity, coordinates[0] if coordinates else None, coordinates[1] if coordinates else None)
        quotes.append({"品类": product, "重量_kg": quantity, "预估配送费_元": quote["预估费用_元"]})
if quotes:
    display_table(quotes, hide_index=True, use_container_width=True)
    st.metric("本次提交预估总费用", f"¥ {sum(q['预估配送费_元'] for q in quotes):,.2f}")
    st.caption("各配送子单分别计起步价、重量价及里程价；下单时按最新计价参数核算。")
if st.button("提交配送订单", type="primary", use_container_width=True):
    missing = [name for name, value in [("客户名称", customer), ("收货地址", address), ("联系人", contact), ("联系电话", phone)] if not value.strip()]
    if date_expired:
        st.error("本次未创建订单，请确认新的配送日期后再次点击提交。")
    elif missing:
        st.error("请补充：" + "、".join(missing))
    elif not products or ("鲜面条" in products and noodle_kg <= 0) or ("姜蒜" in products and ginger_kg + garlic_kg <= 0):
        st.error("请选择配送品类，并为每个选中品类填写大于零的重量。")
    elif latest_time <= expected_time:
        st.error("最晚送达时间需要晚于最早到达时间。")
    elif not coordinates:
        st.error("请先识别或填写收货地址坐标。")
    else:
        try:
            orders = create_order_group({
                "客户名称": customer.strip(), "联系人": contact.strip(), "联系电话": phone.strip(), "收货地址": address.strip(),
                "鲜面需求量_kg": noodle_kg, "生姜需求量_kg": ginger_kg, "大蒜需求量_kg": garlic_kg,
                "期望送达日期": delivery_date.isoformat(),
                "最早到达": expected_time.strftime('%H:%M'), "最晚到达": latest_time.strftime('%H:%M'),
                "经度": coordinates[0], "纬度": coordinates[1], "地址识别结果": coordinates[2], "地址识别服务": coordinates[3],
            })
        except (ValueError, OSError) as exc:
            st.error(f"提交未完成：{exc}")
        else:
            st.session_state["last_order_group"] = orders
            st.session_state["active_order_id"] = orders[0]["订单编号"]
if st.session_state.get("last_order_group"):
    orders = st.session_state["last_order_group"]
    st.success(f"总单 {orders[0]['总单编号']} 已提交，共 {len(orders)} 个配送子单，配送日期：{orders[0]['期望送达日期']}。")
    display_table([{k: o[k] for k in ("订单编号", "品类", "配送重量_kg", "预估费用_元")} for o in orders], hide_index=True, use_container_width=True)
    st.caption("请保存总单号；凭总单号或任一子单号及联系电话后四位，可查询本次提交的全部子单。")
    st.page_link("pages/订单追踪.py", label="查看订单进度", use_container_width=True)
