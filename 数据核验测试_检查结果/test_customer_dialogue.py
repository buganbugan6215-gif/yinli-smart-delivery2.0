import copy
import json
from datetime import datetime

import pytest
from 功能组件_页面共用代码 import order_state as state, customer_dialogue as dialog, order_archive as archive
from 功能组件_页面共用代码 import batch_dispatch as batch, warehouses
from 功能组件_页面共用代码.batch_solver import solve_batch
from 功能组件_页面共用代码.storage import postgres_sql


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("YL_DATABASE_URL", raising=False)
    monkeypatch.setattr(state,"ORDER_DATA_DIR",tmp_path)
    monkeypatch.setattr(state,"ORDER_DB_PATH",tmp_path / "orders.db")
    monkeypatch.setattr(state,"SETTINGS_PATH",tmp_path / "settings.json")
    monkeypatch.setattr(state.st,"session_state",{})
    return tmp_path


def sample():
    return {"订单编号":"DIALOG-1","客户名称":"虚拟客户","联系电话":"00000001234","收货地址":"测试地址","联系人":"测试",
            "期望送达日期":"2026-10-15","提交时间":"2026-10-14T10:00:00+08:00","最早到达":"08:00","最晚到达":"10:00",
            "期望送达":"2026-10-15 08:00","最晚送达":"2026-10-15 10:00","期望窗开始_分钟":480,"期望窗结束_分钟":600,
            "品类":"鲜面条","配送重量_kg":25,"服务时间_分钟":10,"状态":"仓库备货中","状态序号":2,"数据模式":"测试",
            "经度":104.25,"纬度":30.84,"线路编号":"R1","计划到达_分钟":520,"计划发车_分钟":360}


def test_missing_confirmed_route_does_not_reuse_old_arrival(isolated):
    order=sample()
    state.save_order_record(order)
    assert dialog.arrival_window(order, datetime(2026, 10, 15, 7)) is None


def test_request_validation_and_staff_reply(isolated):
    order=sample();state.save_order_record(order)
    state.verify_customer_order(order["订单编号"],"1234")
    now=datetime(2026,10,14,10)
    with pytest.raises(ValueError):
        dialog.customer_reply(order["订单编号"],"改约",start="12:00",end="10:00",now=now)
    dialog.customer_reply(order["订单编号"],"改约",start="09:00",end="10:00",note="晚一点收货",now=now)
    current=state.load_order_records()[0]
    req=current["改约申请"]
    assert current["最早到达"]=="08:00"
    with pytest.raises(ValueError,match="权限"):
        dialog.staff_reply(order["订单编号"],req["编号"],"已联系")
    state.st.session_state["staff_authenticated"]=True
    dialog.staff_reply(order["订单编号"],req["编号"],"请保持原预约")
    assert state.load_order_records()[0]["改约申请"]["状态"]=="未调整，已回复"


def test_replan_then_confirm_preserves_all_orders(isolated,monkeypatch):
    order=sample();order.update({"状态":"方案待确认","状态序号":1});order.pop("线路编号")
    other=copy.deepcopy(order);other.update({"订单编号":"DIALOG-2","经度":104.24})
    for o in (order,other):state.save_order_record(o)
    rates=state.pricing_settings()
    plan=solve_batch([order,other],rates);plan["输入指纹"]=batch.input_fingerprint([order,other])
    batch.confirm_batch(plan,now=datetime(2026,10,14,21))
    state.verify_customer_order(order["订单编号"],"1234")
    dialog.customer_reply(order["订单编号"],"改约",start="09:00",end="10:00",now=datetime(2026,10,14,21))
    state.st.session_state["staff_authenticated"]=True
    req=state.find_order(order["订单编号"],True)["改约申请"]
    new=dialog.approve_reschedule(order["订单编号"],req["编号"])
    assert batch.get_batch("2026-10-15") is None
    assert len(state.load_order_records())==2
    assert all(o["状态"]=="方案待确认" and not o.get("线路编号") for o in state.load_order_records())
    assert state.find_order(order["订单编号"],True)["最早到达"]=="09:00"
    batch.confirm_batch(new,now=datetime(2026,10,14,21))
    assert state.find_order(order["订单编号"],True)["计划到达_分钟"]>=540


def test_backup_restart_restore_all_tables(isolated,monkeypatch):
    state.st.session_state["staff_authenticated"]=True
    order=sample();state.save_order_record(order)
    warehouses.save_selection("2026-10-15",2)
    with state._db_connection() as conn:
        batch._tables(conn)
        conn.execute("INSERT INTO delivery_batches VALUES (?,?)",("2026-10-15",json.dumps({"配送日期":"2026-10-15","订单结果":[{"订单编号":order["订单编号"]}]})))
    raw=archive.export_backup()
    with pytest.raises(ValueError,match="已有"):
        archive.restore_backup(raw)
    monkeypatch.setattr(state,"ORDER_DB_PATH",isolated/"restored.db")
    assert archive.restore_backup(raw)==1
    # 新连接/新会话仍能读取历史和原批次；模拟进程重启后的无会话状态。
    state.st.session_state.clear()
    assert state.verify_customer_order(order["订单编号"],"1234")
    assert warehouses.selection("2026-10-15")==2
    assert batch.get_batch("2026-10-15")["订单结果"][0]["订单编号"]==order["订单编号"]
    assert len(archive.recent_orders(state.load_order_records(),datetime(2026,10,14)))==1
    assert not archive.recent_orders(state.load_order_records(),datetime(2026,12,1))
    assert len(state.load_order_records())==1  # 不删除较早记录。


def test_postgres_translation():
    assert postgres_sql("INSERT OR IGNORE INTO orders VALUES (?, ?, ?)").endswith("ON CONFLICT DO NOTHING")
    assert "ON CONFLICT (day) DO UPDATE SET count=excluded.count" in postgres_sql("INSERT OR REPLACE INTO warehouse_selection VALUES (?, ?)")
    assert postgres_sql("SELECT payload FROM orders WHERE order_id=?")=="SELECT payload FROM orders WHERE order_id=%s"


def test_cloud_failure_never_creates_local_database(isolated,monkeypatch):
    import sys
    from types import SimpleNamespace
    from 功能组件_页面共用代码 import storage
    monkeypatch.setattr(storage,"database_url",lambda:"postgresql://hidden-password@example.invalid/db")
    def fail(*args,**kwargs):
        raise OSError("hidden-password connection error")
    monkeypatch.setitem(sys.modules,"psycopg",SimpleNamespace(connect=fail))
    with pytest.raises(RuntimeError) as error:
        state.save_order_record(sample())
    assert "hidden-password" not in str(error.value)
    assert not state.ORDER_DB_PATH.exists()


def test_failed_replan_preserves_original_batch(isolated,monkeypatch):
    from 功能组件_页面共用代码 import batch_solver
    order=sample();state.save_order_record(order)
    state.verify_customer_order(order["订单编号"],"1234")
    dialog.customer_reply(order["订单编号"],"改约",start="09:00",end="10:00",now=datetime(2026,10,14,21))
    state.st.session_state["staff_authenticated"]=True
    before=state.load_order_records()
    def infeasible(*args,**kwargs):
        raise ValueError("时间窗不可行")
    monkeypatch.setattr(batch_solver,"solve_batch",infeasible)
    with pytest.raises(ValueError,match="不可行"):
        dialog.approve_reschedule(order["订单编号"],before[0]["改约申请"]["编号"])
    assert state.load_order_records()==before


def test_malformed_backup_is_atomic(isolated):
    state.st.session_state["staff_authenticated"]=True
    raw=json.dumps({"格式":"银犁订单完整备份1","表":{name:[] for name in archive.TABLES}}).encode()
    content=json.loads(raw)
    content["orders"]="invalid"
    content["表"]["orders"]=[["A","now",json.dumps({"订单编号":"B","状态":"方案待确认"})]]
    with pytest.raises(ValueError,match="格式"):
        archive.restore_backup(json.dumps(content).encode())
    assert state.load_order_records()==[]


def test_customer_and_staff_ui(isolated, monkeypatch):
    from streamlit.runtime.state.session_state_proxy import SessionStateProxy
    monkeypatch.setattr(state.st,"session_state",SessionStateProxy())
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    root=Path(__file__).resolve().parents[1]
    order=sample()
    from 功能组件_页面共用代码.delivery_calendar import beijing_now
    from datetime import timedelta
    ui_day=beijing_now().date()+timedelta(days=1)
    order.update({"期望送达日期":str(ui_day),"车辆编号":"测试车","配送顺序":1})
    state.save_order_record(order)
    app=AppTest.from_file(str(root/"app.py"),default_timeout=30).run()
    app.session_state["verified_order_ids"]=[order["订单编号"]]
    app.switch_page("pages/订单追踪.py").run()
    assert not app.exception
    assert not any(b.label in {"此时间可以收货", "提交改约申请"} for b in app.button)
    staff=AppTest.from_file(str(root/"app.py"),default_timeout=30).run()
    staff.session_state["staff_authenticated"]=True
    staff.switch_page("pages/订单与需求.py").run()
    next(s for s in staff.selectbox if s.label=="配送日期").select("其他日期").run()
    from datetime import date
    staff.date_input[0].set_value(ui_day).run()
    # 新建的已确认记录属于全部订单视图。
    next(r for r in staff.radio if r.label=="订单列表").set_value("全部订单").run()
    assert not staff.exception
    assert not any(b.label=="保持原预约并回复客户" for b in staff.button)
    staff.switch_page("pages/订单备份与迁移.py").run()
    assert not staff.exception
    next(b for b in staff.button if b.label=="生成完整业务备份").click().run()
    assert not staff.exception
    assert staff.get("download_button")
