"""复用现有蓝灰卡片和按钮动效，不新增导航入口。"""
from datetime import time
import streamlit as st
from 功能组件_页面共用代码 import customer_dialogue as dialogue
from 功能组件_页面共用代码 import order_state as state

RELEASE_VERSION = "2026-10-14-road-access-v20"


def customer_panel(order):
    oid = order["订单编号"]
    with st.container(key="order_arrival_"+oid, border=True):
        st.markdown("### 送达时间 · 与您确认")
        st.caption(f"您的可收货时间：{order.get('最早到达', '—')}—{order.get('最晚到达', '—')}；平台预报不会自动覆盖原预约。")
        window = dialogue.arrival_window(order)
        if order.get("状态") in dialogue.DONE:
            st.success("货物已送达，收货时间沟通已结束。")
            if order.get("实际到达时间"):
                st.caption("工作人员登记到达时间："+order["实际到达时间"][:19].replace("T", " "))
        elif window:
            st.metric("预计送达范围", window["标签"])
            st.caption(window["来源"]+"；范围为计划估计，非保证到达时刻。")
            if window["已过期"]:
                st.warning("原预报时间已过，尚未登记送达；请等待工作人员更新或提交改约需求。")
            elif window["临近"]:
                st.info("预计即将送达，请留意联系电话并准备收货。")
            if window["超出预约"]:
                st.warning("当前预报超出您的原预约范围，请确认是否可以收货，或申请改约。")
            if window["已确认"]:
                st.success("您已确认此送达范围；预报变化后需要重新确认。")
            elif order.get("收货确认"):
                st.info("送达预报已更新，请重新确认是否方便收货。")
            if order.get("到达预报"):
                st.write("更新说明："+order["到达预报"]["说明"])
            if st.button("此时间可以收货", type="primary", disabled=window["已确认"] or window["已过期"] or order.get("改约申请", {}).get("状态")=="待处理", key="agree_"+oid):
                try:
                    dialogue.customer_reply(oid, "确认", version=window["版本"])
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        else:
            st.info("工作人员确认线路后，这里会显示更窄的预计送达范围，供您确认。")
        request = order.get("改约申请")
        if request:
            st.write(f"改约申请：{request['开始']}—{request['结束']} · {request['状态']}")
            if request.get("回复"):
                st.info("工作人员回复："+request["回复"])
        if order.get("状态") not in dialogue.DONE:
            with st.expander("这个时间不方便？申请调整"):
                st.caption("申请当天的其他收货时间；工作人员核实线路可行性后回复，提交申请不代表改约已生效。")
                with st.form("change_"+oid):
                    a,b=st.columns(2)
                    start=a.time_input("希望最早送达", time(9), key="change_start_"+oid)
                    end=b.time_input("希望最晚送达", time(10), key="change_end_"+oid)
                    note=st.text_area("补充说明（选填）", max_chars=300)
                    if st.form_submit_button("提交改约申请", disabled=bool(request and request["状态"]=="待处理")):
                        try:
                            dialogue.customer_reply(oid,"改约",start=start.strftime("%H:%M"),end=end.strftime("%H:%M"),note=note)
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
        with st.expander("查看时间沟通记录"):
            for event in reversed(order.get("时间沟通记录", [])):
                st.write(f"{event['时间'][:16].replace('T',' ')} · {event['操作']}")
                st.caption(event["内容"])


def staff_panel(orders):
    pending=[o for o in orders if o.get("改约申请",{}).get("状态")=="待处理"]
    with st.expander(f"客户时间沟通 · {len(pending)} 条待处理", expanded=bool(pending)):
        if not orders:
            st.caption("当前筛选没有订单。")
            return
        ordered=sorted(orders,key=lambda o:o not in pending)
        oid=st.selectbox("选择沟通订单",[o["订单编号"] for o in ordered],format_func=lambda value:next(f"{o.get('客户名称','客户')} · {o.get('品类','')} · {value}" for o in ordered if o["订单编号"]==value))
        order=state.find_order(oid,include_saved=True)
        request=order.get("改约申请",{})
        window=dialogue.arrival_window(order)
        st.write("客户确认："+("已确认当前预报" if window and window["已确认"] else "尚未确认当前预报"))
        if order.get("偏好到达时间"):
            st.caption("客户偏好："+order["偏好到达时间"]+"；仅作沟通参考，路线以可收货时间窗为约束。")
        if request:
            st.write(f"申请 {request['开始']}—{request['结束']} · {request['状态']}")
            st.write(request.get("说明") or "无补充说明")
        if request.get("状态")=="待处理":
            st.caption("发车前可按申请重算整个配送日；成功后回到统一调度确认新线路，失败则保留原方案。")
            if st.button("采纳申请并重算配送日", key="replan_"+oid):
                try:
                    with st.spinner("正在检查全部订单与线路可行性…"):
                        dialogue.approve_reschedule(oid, request["编号"])
                    st.success("已重算，请到统一调度确认新线路。")
                    st.rerun()
                except (ValueError,OSError,RuntimeError) as exc:
                    st.error(str(exc))
            with st.form("staff_reply_"+oid):
                reply=st.text_area("无法直接调整时的回复", max_chars=300)
                if st.form_submit_button("保持原预约并回复客户"):
                    try:
                        dialogue.staff_reply(oid,request["编号"],reply)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        if order.get("线路编号") and order.get("状态") not in dialogue.DONE:
            with st.form("forecast_"+oid):
                st.markdown("**更新送达预报／延误说明**")
                a,b=st.columns(2)
                start=a.time_input("预报开始",time(9))
                end=b.time_input("预报结束",time(9,20))
                note=st.text_input("更新原因",max_chars=300)
                if st.form_submit_button("发布预报，请客户重新确认"):
                    try:
                        dialogue.staff_forecast(oid,start.strftime("%H:%M"),end.strftime("%H:%M"),note)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))


def storage_panel():
    from 功能组件_页面共用代码.storage import database_url
    from 功能组件_页面共用代码.order_archive import export_backup, restore_backup
    with st.expander("订单保存与迁移"):
        if database_url():
            # 实际探测成功才显示已连接。
            with state._db_connection() as conn:
                count=conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            st.success(f"已连接外部订单库 · {count} 个配送子单。应用重启后从该库读取。")
        else:
            st.warning("当前为本地存储，云端 Reboot 后不保证保留。请先下载备份，再按《云端订单保存配置》接入外部数据库。")
        st.caption("历史列表默认展示近 30 天；数据库不自动删除更早订单，预约订单也会保留。")
        if st.button("生成完整业务备份"):
            st.session_state["order_backup_download"] = export_backup()
        if st.session_state.get("order_backup_download"):
            st.download_button("下载订单与调度备份",st.session_state["order_backup_download"],"银犁订单完整备份.json",mime="application/json")
            st.caption("备份含客户联系方式与地址，请保存在自己的电脑，不要上传公开仓库。")
        uploaded=st.file_uploader("将完整备份迁入空数据库",type=["json"])
        if st.button("导入完整备份", disabled=uploaded is None):
            try:
                count=restore_backup(uploaded.getvalue())
                st.success(f"已导入 {count} 个订单及关联调度记录。")
            except (ValueError,RuntimeError) as exc:
                st.error(str(exc))
