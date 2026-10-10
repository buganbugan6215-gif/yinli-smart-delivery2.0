from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()
import streamlit as st
from 功能组件_页面共用代码 import warehouse_ui
from 功能组件_页面共用代码.batch_dispatch import day_orders, get_draft, get_batch
from 功能组件_页面共用代码.live_operations import select_delivery_day
from 功能组件_页面共用代码.ui import inject_css, page_title, render_sidebar, require_staff_access

inject_css()
render_sidebar()
require_staff_access()
page_title("配送地图", "按实际订单查看所选仓库、末端线路和仓间补货")
day = select_delivery_day(st, historical=True)
count, changed = warehouse_ui.selector(day)
plan = warehouse_ui.active_plan(day)
if changed and day_orders(day):
    old = get_draft(day)
    try:
        warehouse_ui.calculate(day, old["发车分钟"] if old else 360)
        st.rerun()
    except (ValueError, OSError) as exc:
        st.error(str(exc))
if not plan:
    st.info("当前仓库模式尚无有效方案，点击即可计算当前订单。")
    if st.button("立即计算路径", type="primary", icon=":material/route:", disabled=not day_orders(day)):
        try:
            warehouse_ui.calculate(day)
            st.rerun()
        except (ValueError, OSError) as exc:
            st.error(str(exc))
else:
    st.caption("已确认配送方案" if get_batch(day) else "待确认方案预览 · 客户仅能查看确认后的自身路线")
    warehouse_ui.render_cost(plan)
    warehouse_ui.render_map(plan, key=f"operations-map-{day}-{count}")
