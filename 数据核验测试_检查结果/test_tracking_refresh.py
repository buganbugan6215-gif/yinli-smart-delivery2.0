import copy

import streamlit as st
import streamlit_folium
from streamlit.testing.v1 import AppTest

from 功能组件_页面共用代码 import maps, order_state as state
from test_batch_ui import ROOT
from test_gps_simulator import _order


def test_tracking_reuses_base_map_and_stops_timer(monkeypatch):
    order, _ = _order()
    order.update({"订单编号": "MAP-TEST", "线路编号": "R1", "品类": "鲜面条", "期望送达日期": "2026-09-24"})
    monkeypatch.setattr(state, "init_orders", lambda *a, **k: [copy.deepcopy(order)])
    monkeypatch.setattr(state, "customer_order", lambda *a: copy.deepcopy(order))
    builds, components, intervals = [], [], []
    original_build, original_fragment = maps.create_chengdu_map, st.fragment

    def build(*args, **kwargs):
        builds.append(1)
        return original_build(*args, **kwargs)

    def fragment(*args, **kwargs):
        intervals.append(kwargs.get("run_every"))
        return original_fragment(*args, **kwargs)

    monkeypatch.setattr(maps, "create_chengdu_map", build)
    monkeypatch.setattr(st, "fragment", fragment)
    monkeypatch.setattr(streamlit_folium, "_component_func", lambda **kwargs: components.append(kwargs))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.switch_page("pages/配送网络地图.py").run()
    assert not app.exception
    assert intervals[-1] == "10s"
    app.run()
    assert not app.exception
    assert len(builds) == 1
    assert components[-1]["key"] == components[-2]["key"]
    assert components[-1]["script"] == components[-2]["script"]
    assert components[-1]["feature_group"]  # 车辆位于单独的动态图层。

    # 在下一次片段检查期间确认送达，页面应重新注册无定时器片段。
    reads = 0

    def delivered_on_poll(*args):
        nonlocal reads
        reads += 1
        if reads >= 2:
            order["状态"] = "已送达"
        return copy.deepcopy(order)

    monkeypatch.setattr(state, "customer_order", delivered_on_poll)
    app.run()
    assert not app.exception
    assert intervals[-1] is None
    assert any("自动更新已停止" in c.value for c in app.caption)
    assert len(builds) == 1
    assert components[-1]["key"] == components[0]["key"]
    monkeypatch.setattr(state, "customer_order", lambda *a: copy.deepcopy(order))
    order["状态"] = "签收完成"
    app.run()
    assert not app.exception
    assert intervals[-1] is None
    assert len(builds) == 1

    order["状态"] = "仓库备货中"
    app.run()
    assert not app.exception
    assert intervals[-1] is None
    assert any("当前地图不自动更新" in c.value for c in app.caption)

    # 换单时必须更新底图，避免保留上一个订单的路线。
    order["订单编号"] = "MAP-OTHER"
    app.session_state["active_order_id"] = "MAP-OTHER"
    app.run()
    assert not app.exception
    assert len(builds) == 2
    assert components[-1]["key"] != components[0]["key"]
