"""可信本地 GSAP：不读取订单，不加载外部脚本，不触发 Streamlit 刷新。"""
from pathlib import Path
import base64
import streamlit as st


def install_motion():
    folder = Path(__file__).parent
    engine = (folder / "vendor" / "gsap.min.js").read_text(encoding="utf-8")
    encoded = base64.b64encode(engine.encode("utf-8")).decode("ascii")
    controller = (folder / "motion.js").read_text(encoding="utf-8")
    # 单独容器可被 CSS 精确移除占位；脚本来自仓库，绝不插入用户输入。
    with st.container(key="yl_motion_bootstrap"):
        st.html(f'''<span hidden></span><script>if (!window.gsap) {{ const s = document.createElement("script"); s.textContent = atob("{encoded}"); document.head.appendChild(s); }}\n;{controller}</script>''', unsafe_allow_javascript=True)
