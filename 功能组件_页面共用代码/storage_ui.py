"""订单备份与迁移页面的存储控件。"""
import streamlit as st

from 功能组件_页面共用代码 import order_state as state
from 功能组件_页面共用代码.order_archive import export_backup, restore_backup
from 功能组件_页面共用代码.storage import database_url


def storage_panel():
    with st.container(border=True):
        if database_url():
            with state._db_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            st.success(f"已连接外部订单库 · {count} 个配送子单。应用重启后从该库读取。")
        else:
            st.warning("当前为本地存储，云端 Reboot 后不保证保留。请先下载备份，再按《云端订单保存配置》接入外部数据库。")
        st.caption("历史列表默认展示近 30 天；数据库不自动删除更早订单，预约订单也会保留。")
        if st.button("生成完整业务备份"):
            st.session_state["order_backup_download"] = export_backup()
        if st.session_state.get("order_backup_download"):
            st.download_button("下载订单与调度备份", st.session_state["order_backup_download"], "银犁订单完整备份.json", mime="application/json")
            st.caption("备份含客户联系方式与地址，请保存在自己的电脑，不要上传公开仓库。")
        uploaded = st.file_uploader("将完整备份迁入空数据库", type=["json"])
        if st.button("导入完整备份", disabled=uploaded is None):
            try:
                count = restore_backup(uploaded.getvalue())
                st.success(f"已导入 {count} 个订单及关联调度记录。")
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
