"""调度页初次打开避免反复读取相同配送日。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from 功能组件_页面共用代码 import order_state


def test_empty_staff_page_uses_only_snapshot_and_orders_queries(monkeypatch, tmp_path):
    monkeypatch.setattr(order_state, "ORDER_DATA_DIR", tmp_path)
    monkeypatch.setattr(order_state, "ORDER_DB_PATH", tmp_path / "orders.db")
    original = order_state._read_db_connection
    calls = []

    def counted():
        calls.append(1)
        return original()

    monkeypatch.setattr(order_state, "_read_db_connection", counted)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
    app.session_state["staff_authenticated"] = True
    app.switch_page("pages/企业工作台.py").run()
    assert not app.exception
    assert len(calls) == 2
