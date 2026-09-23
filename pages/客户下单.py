import streamlit as st

from datetime import time
from 功能组件_页面共用代码.delivery_calendar import delivery_day, cutoff_label

from 功能组件_页面共用代码.order_state import create_order, estimate_delivery_fee, geocode_address, init_orders
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar


inject_css()
render_sidebar()
init_orders()
page_title("客户下单", "填写收货信息和送达时间，提交前即可查看预估费用")

st.markdown("""
<div class="service-hero motion-focus">
  <div><h2>把配送需求交给我们。</h2><p>信息填写完成后，系统按北京时间自动安排次日配送，截止后由工作人员统一安排车辆。</p></div>
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
    st.caption(f"WGS84 坐标：{coordinates[0]:.6f}, {coordinates[1]:.6f}。提交前请核对识别地点是否与收货地址一致。")
else:
    st.caption("配置高德 Web 服务密钥后优先使用高德；未配置时自动使用 OpenStreetMap。识别结果缓存 24 小时。")

st.markdown("### 配送内容")
delivery_date = delivery_day()
st.info(f"本次下单配送日：{delivery_date}。每日 23:59 截止收取次日订单（北京时间，含该分钟）；00:00 起自动归入再下一天。")
st.caption(f"本批次截止时间：{cutoff_label(delivery_date)}。日期由提交时服务器北京时间确定，无需手动选择。")
product = st.segmented_control("配送品类", ["鲜面条", "姜蒜"], default="鲜面条", selection_mode="single")
if product == "姜蒜":
    q1, q2, q3 = st.columns(3)
    ginger_kg = q1.number_input("生姜需求量（kg）", min_value=0.0, value=50.0, step=5.0)
    garlic_kg = q2.number_input("大蒜需求量（kg）", min_value=0.0, value=50.0, step=5.0)
    quantity = ginger_kg + garlic_kg
    q3.metric("配送日期", str(delivery_date))
else:
    q1, q2 = st.columns([1, 1])
    quantity = q1.number_input("鲜面需求量（kg）", min_value=1.0, value=100.0, step=10.0)
    q2.metric("配送日期", str(delivery_date))
    ginger_kg = garlic_kg = 0.0
t1, t2 = st.columns(2)
expected_time = t1.time_input("最早到达时间", value=time(8, 0))
latest_time = t2.time_input("最晚送达时间", value=time(18, 0))
st.caption("费用会随品类、重量、已识别配送坐标和工作人员调价参数实时更新。")
quote = estimate_delivery_fee(product, quantity, coordinates[0] if coordinates else None, coordinates[1] if coordinates else None)
st.markdown(f"""
<div class="fee-preview"><span>本单预估配送费用</span><strong>¥ {quote['预估费用_元']:,.2f}</strong><small>起步价 ¥ {quote['起步价_元']:.2f} + 重量价 ¥ {quote['重量价_元']:.2f}{f" + 参考里程价 ¥ {quote['里程价_元']:.2f}（{quote['参考距离_km']:.1f} km）" if coordinates else '。填写坐标后将计入参考里程价。'}</small></div>
""", unsafe_allow_html=True)
submitted = st.button("提交配送订单", type="primary", use_container_width=True)

if submitted:
    missing = [name for name, value in [("客户名称", customer), ("收货地址", address), ("联系人", contact), ("联系电话", phone)] if not value.strip()]
    if missing:
        st.error("请补充：" + "、".join(missing))
    elif quantity <= 0:
        st.error("配送重量必须大于零。")
    elif latest_time <= expected_time:
        st.error("最晚送达时间需要晚于期望送达时间。")
    elif not coordinates:
        st.error("请先识别或填写收货地址坐标，以生成配送路线和完整预估费用。")
    else:
        order = create_order({
            "客户名称": customer.strip(), "联系人": contact.strip(), "联系电话": phone.strip(), "收货地址": address.strip(),
            "品类": product, "配送重量_kg": quantity, "鲜面需求量_kg": quantity if product == "鲜面条" else 0,
            "生姜需求量_kg": ginger_kg, "大蒜需求量_kg": garlic_kg, "期望送达日期": str(delivery_date),
            "最早到达": expected_time.strftime('%H:%M'), "最晚到达": latest_time.strftime('%H:%M'),
            "期望送达": f"{delivery_date} {expected_time.strftime('%H:%M')}",
            "最晚送达": f"{delivery_date} {latest_time.strftime('%H:%M')}", "预估费用_元": quote["预估费用_元"],
            "经度": coordinates[0] if coordinates else "", "纬度": coordinates[1] if coordinates else "", "地址识别结果": coordinates[2] if coordinates else "未识别", "地址识别服务": coordinates[3] if coordinates else "未识别",
        })
        st.success(f"订单 {order['订单编号']} 已提交，服务时间 {order['服务时间_分钟']} 分钟，预估费用 ¥ {order['预估费用_元']:,.2f}。配送日期：{order['期望送达日期']}，等待整日统一调度。")
        st.session_state["active_order_id"] = order["订单编号"]
        if order.get("保存状态") == "已保存到本机演示订单表":
            st.caption("订单已保存。退出后仍可使用订单编号和联系电话后四位查询进度。")
        else:
            st.warning("订单已进入当前会话，但写入 Excel 失败。工作人员可从当前订单列表导出。")
        st.page_link("pages/订单追踪.py", label="查看订单进度", use_container_width=True)
