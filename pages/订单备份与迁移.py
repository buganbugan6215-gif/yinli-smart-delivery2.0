from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

from 功能组件_页面共用代码.ui import inject_css, render_sidebar, require_staff_access, page_title
from 功能组件_页面共用代码.storage_ui import storage_panel
from 功能组件_页面共用代码.batch_dispatch import clear_all_order_data
import streamlit as st

inject_css()
render_sidebar()
require_staff_access()
page_title("订单数据管理", "备份、迁移与清理订单数据")
storage_panel()
with st.expander("清理全部订单"):
    st.warning("此操作会永久删除共享订单库中的全部订单、调度草案和已确认线路，并清理本机订单目录下的 Excel 订单文件。所有客户端都将无法再查询这些订单。")
    phrase = st.text_input("输入“清空全部订单”以确认", key="clear_orders_phrase")
    if st.button("一键清空所有订单", disabled=phrase != "清空全部订单", key="clear_all_orders"):
        try:
            count = clear_all_order_data()
            st.session_state["cleared_orders_count"] = count
            st.rerun()
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
if "cleared_orders_count" in st.session_state:
    st.success(f"已清空 {st.session_state.pop('cleared_orders_count')} 个订单及相关调度路线。")
