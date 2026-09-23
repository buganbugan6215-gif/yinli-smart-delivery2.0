"""通过真实 Streamlit 页面驱动整批操作；仅写临时测试数据库。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from 功能组件_页面共用代码 import order_state as state

ROOT = Path(__file__).resolve().parents[1]


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_staff_compute_confirm_and_customer_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "ORDER_DATA_DIR", tmp_path)
    monkeypatch.setattr(state, "ORDER_DB_PATH", tmp_path / "orders.db")
    monkeypatch.setattr(state, "SETTINGS_PATH", tmp_path / "settings.json")
    for i in (1, 2):
        state.save_order_record({"订单编号": f"UITEST-{i}", "客户名称": f"虚拟测试{i}", "联系人": "测试",
                                 "联系电话": f"0000000{i:04d}", "收货地址": "虚拟地址", "品类": "鲜面条", "配送重量_kg": 25,
                                 "期望送达日期": "2020-01-02", "期望送达": "2020-01-02 08:00", "最晚送达": "2020-01-02 18:00",
                                 "最早到达": "08:00", "最晚到达": "18:00", "经度": 104.26-i*.01, "纬度": 30.85-i*.01,
                                 "期望窗开始_分钟": 480, "期望窗结束_分钟": 1080, "服务时间_分钟": 10,
                                 "状态": "方案待确认", "状态序号": 1, "数据模式": "等待整日统一调度"})
    staff = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    staff.session_state["staff_authenticated"] = True
    staff.switch_page("pages/企业工作台.py").run()
    assert not staff.exception
    button(staff, "一次计算全部订单的矩阵与线路").click().run()
    assert not staff.exception
    button(staff, "统一确认全部线路并开始备货").click().run()
    assert not staff.exception
    assert all(o["线路编号"] for o in state.load_order_records())
    button(staff, "全部车辆发出，开始配送").click().run()
    assert not staff.exception
    button(staff, "确认本批次全部货物已送达").click().run()
    assert not staff.exception

    customer = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    customer.switch_page("pages/订单追踪.py").run()
    assert not customer.exception
    next(t for t in customer.text_input if t.label == "订单编号").input("UITEST-1")
    next(t for t in customer.text_input if t.label == "联系电话后四位").input("0001")
    button(customer, "查询订单").click().run()
    assert not customer.exception
    assert any(m.label == "我的配送线路" for m in customer.metric)
    assert "UITEST-2" not in str(customer.get("markdown"))
    customer.switch_page("pages/配送网络地图.py").run()
    assert not customer.exception
    customer.switch_page("pages/电子签收.py").run()
    assert not customer.exception
    assert customer.selectbox[0].options == ["UITEST-1"]
    button(customer, "确认签收").click().run()
    assert not customer.exception
    orders = {o["订单编号"]: o for o in state.load_order_records()}
    assert orders["UITEST-1"]["状态"] == "签收完成"
    assert orders["UITEST-2"]["状态"] == "已送达"
