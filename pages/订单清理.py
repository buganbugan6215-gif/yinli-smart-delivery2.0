from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

import streamlit as st
from 功能组件_页面共用代码.ui import require_staff_access

require_staff_access()
st.switch_page("pages/订单备份与迁移.py")
