from datetime import datetime

import pytest
from streamlit.testing.v1 import AppTest

from 功能组件_页面共用代码 import delivery_calendar as calendar
from 功能组件_页面共用代码 import order_state as state
from 功能组件_页面共用代码 import batch_dispatch as dispatch
from 功能组件_页面共用代码.calendar_runtime import ensure_current_calendar
from test_batch_dispatch import samples
from test_batch_ui import ROOT


def test_upgrade_retained_old_function_references(monkeypatch):
    # 模拟页面已更新，但 Python 进程仍持有午夜截止版本的模块和函数。
    monkeypatch.delattr(calendar, "POLICY_VERSION")
    monkeypatch.setattr(calendar, "cutoff_label", lambda day: "23:59（含该分钟）")
    monkeypatch.setattr(state, "delivery_day", lambda value=None: "OLD")
    monkeypatch.setattr(dispatch, "batch_closed", lambda *args: False)
    ensure_current_calendar()
    assert "20:00" in calendar.cutoff_label("2026-09-24")
    assert str(state.delivery_day(datetime(2026, 9, 23, 20, 0))) == "2026-09-25"
    assert dispatch.batch_closed("2026-09-24", datetime(2026, 9, 23, 20, 0))


@pytest.mark.parametrize("instant,closed,day", [
    (datetime(2026, 9, 23, 19, 59, 59), False, "2026-09-24"),
    (datetime(2026, 9, 23, 20, 0), True, "2026-09-25"),
    (datetime(2026, 9, 23, 20, 1), True, "2026-09-25"),
])
def test_staff_and_customer_pages_share_cutoff(tmp_path, monkeypatch, instant, closed, day):
    # 页面入口会修复服务持有的函数引用；测试结束后恢复这些别名。
    for module, names in ((state, ("beijing_now", "delivery_day")), (dispatch, ("beijing_now", "batch_closed"))):
        for name in names:
            monkeypatch.setattr(module, name, getattr(module, name))
    monkeypatch.setattr(calendar, "beijing_now", lambda: instant)
    monkeypatch.setattr(state, "ORDER_DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "ORDER_DB_PATH", tmp_path / "orders.db")
    monkeypatch.setattr(state, "SETTINGS_PATH", tmp_path / "settings.json")
    for order in samples():
        state.save_order_record(order)
    staff = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    staff.session_state["staff_authenticated"] = True
    staff.switch_page("pages/企业工作台.py").run()
    assert not staff.exception
    assert any("2026-09-23 20:00" in c.value for c in staff.caption)
    assert not any("23:59" in c.value for c in staff.caption)
    status = next(m.value for m in staff.metric if m.label == "批次状态")
    assert status == ("已截止，待调度" if closed else "正在收单")
    assert any(b.label == "一次计算全部订单的矩阵与线路" for b in staff.button) == closed
    customer = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    customer.switch_page("pages/客户下单.py").run()
    assert not customer.exception
    assert any(f"本次下单配送日：{day}" in i.value for i in customer.info)
    assert any("20:00" in c.value and "本批次截止时间" in c.value for c in customer.caption)
