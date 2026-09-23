import streamlit as st

from 功能组件_页面共用代码.ui import inject_css, render_sidebar

st.set_page_config(page_title="银犁智慧配送", page_icon="YL", layout="wide", initial_sidebar_state="collapsed")
inject_css()
render_sidebar()

st.markdown("""
<div class="home-nav">
  <div class="home-brand"><span>YL</span><strong>银犁智慧配送</strong></div>
  <div class="home-nav-copy">让每一次配送都有清楚的答案</div>
</div>
""", unsafe_allow_html=True)

with st.container(key="home_hero"):
    hero_copy, hero_visual = st.columns([1.08, 0.92], gap="large", vertical_alignment="center")
    with hero_copy:
        st.markdown("""
        <div class="home-hero-copy">
          <h1>今日下单，次日统一配送。</h1>
          <p>北京时间每日 23:59 截止次日订单，00:00 起自动归入下一配送日。凭订单编号查询您的配送线路。</p>
        </div>
        """, unsafe_allow_html=True)
        action_a, action_b = st.columns(2)
        with action_a:
            st.page_link("pages/客户下单.py", label="立即下单", use_container_width=True)
        with action_b:
            st.page_link("pages/订单追踪.py", label="查询订单", use_container_width=True)
        st.caption("目前支持鲜面条和姜蒜配送，费用在提交前清楚展示。")
    with hero_visual:
        st.markdown("""
        <div class="customer-journey motion-focus">
          <div><span>01</span><b>提交配送需求</b><small>地址、品类、重量和时间窗</small></div>
          <div><span>02</span><b>等待方案确认</b><small>截止后统一计算并确认全部线路</small></div>
          <div><span>03</span><b>确认收货</b><small>一键签收或提交异常反馈</small></div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("""
<section class="home-section home-reveal">
  <h2>您关心的配送信息，都在这里。</h2>
  <p>从提交需求到确认收货，每一步都有清楚的状态和下一步提示。</p>
</section>
<div class="home-bento">
  <article class="home-feature home-feature-large home-reveal"><h3>填写一次，配送需求清楚送达。</h3><p>客户名称、联系人、地址、电话、品类、重量和送达时间集中填写，提交前即可查看预估费用。</p><div class="feature-line"></div></article>
  <article class="home-feature home-feature-blue home-reveal"><h3>进度随时可查</h3><p>订单提交、方案确认、仓库备货、配送途中、送达和签收，状态一目了然。</p></article>
  <article class="home-feature home-feature-light home-reveal"><h3>只看自己的路线</h3><p>统一确认后，可查看本订单所属线路、配送顺序和到本收货点的道路，不展示其他客户信息。</p></article>
  <article class="home-feature home-feature-dark home-reveal"><h3>签收更简单</h3><p>正常到货一键确认；有包装、数量、温度或延误问题，可直接提交异常反馈。</p></article>
</div>
""", unsafe_allow_html=True)

with st.container(key="home_flow"):
    st.markdown("""
    <section class="home-section home-reveal"><h2>三步完成一次配送。</h2><p>无需上传表格，客户只需填写自己的配送需求。</p></section>
    <div class="home-flow">
      <div class="home-flow-item home-reveal"><b>下单</b><span>填写地址、品类、重量和送达时间</span></div>
      <div class="home-flow-item home-reveal"><b>追踪</b><span>查看备货、装车和配送进度</span></div>
      <div class="home-flow-item home-reveal"><b>签收</b><span>确认收货，异常情况及时反馈</span></div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<section class='home-section home-reveal'><h2>按您关心的内容直接进入。</h2></section>", unsafe_allow_html=True)
entry_cols = st.columns(4, gap="medium")
entries = [
    ("pages/客户下单.py", "客户下单", "提交配送需求", "▤"),
    ("pages/订单追踪.py", "订单追踪", "查看处理进度", "◎"),
    ("pages/配送网络地图.py", "配送地图", "看位置与路线", "◇"),
    ("pages/电子签收.py", "电子签收", "确认收货或反馈异常", "✦"),
]
for col, (page, title, copy, icon) in zip(entry_cols, entries):
    with col:
        with st.container(key=f"entry_{title}"):
            st.markdown(f"<div class='entry-icon'>{icon}</div>", unsafe_allow_html=True)
            st.page_link(page, label=title, use_container_width=True)
            st.caption(copy)

st.markdown("""
<div class="home-final home-reveal">
  <div><h2>准备好配送信息，就可以开始下单。</h2><p>提交前显示预估费用，提交后可随时查看进度。</p></div>
</div>
""", unsafe_allow_html=True)
st.page_link("pages/客户下单.py", label="填写配送订单", use_container_width=True)
