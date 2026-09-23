"""整日批次的指纹校验、原子确认与进度更新。"""
from __future__ import annotations

import copy
import hashlib
from io import BytesIO
import json
import math

import pandas as pd

from 功能组件_页面共用代码.delivery_calendar import batch_closed, beijing_now
from 功能组件_页面共用代码 import order_state as state

INPUT_FIELDS = ("订单编号", "期望送达日期", "经度", "纬度", "品类", "配送重量_kg",
                "期望窗开始_分钟", "期望窗结束_分钟", "服务时间_分钟")


def input_fingerprint(orders):
    rows = [{key: o.get(key) for key in INPUT_FIELDS} for o in sorted(orders, key=lambda o: o["订单编号"])]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def day_orders(day):
    return sorted([o for o in state.init_orders(include_saved=True) if str(o.get("期望送达日期")) == str(day)], key=lambda o: o["订单编号"])


def _tables(connection):
    connection.execute("CREATE TABLE IF NOT EXISTS delivery_batches (delivery_day TEXT PRIMARY KEY, payload TEXT NOT NULL)")


def get_batch(day):
    with state._db_connection() as conn:
        _tables(conn)
        row = conn.execute("SELECT payload FROM delivery_batches WHERE delivery_day=?", (str(day),)).fetchone()
    return json.loads(row[0]) if row else None


def validate_result(plan, orders):
    expected = {o["订单编号"] for o in orders}
    if not expected or len(expected) != len(orders):
        raise ValueError("批次为空或包含重复订单。")
    if plan.get("输入指纹") != input_fingerprint(orders):
        raise ValueError("订单已变化，请重新计算整个批次。")
    if {str(o["期望送达日期"]) for o in orders} != {plan.get("配送日期")}:
        raise ValueError("结果配送日期不匹配。")
    assignments = plan.get("订单结果", [])
    assigned = [a["订单编号"] for a in assignments]
    if len(assigned) != len(expected) or set(assigned) != expected:
        raise ValueError("结果必须覆盖当天全部订单，且每单只能出现一次。")
    labels = plan.get("矩阵标签", [])
    matrix = plan.get("距离矩阵_m", [])
    if len(labels) != len(expected)+1 or labels[0] != "配送中心" or set(labels[1:]) != expected:
        raise ValueError("距离矩阵未覆盖全部客户与配送中心。")
    if len(matrix) != len(labels) or any(len(r) != len(labels) for r in matrix):
        raise ValueError("距离矩阵维度不正确。")
    if any(not math.isfinite(float(v)) or v < 0 for r in matrix for v in r):
        raise ValueError("距离矩阵存在非法或不可达距离。")
    if any(abs(matrix[i][i]) > 1e-8 for i in range(len(labels))):
        raise ValueError("距离矩阵对角线必须为零。")
    routes = plan.get("线路", [])
    route_ids = [r["线路编号"] for r in routes]
    if len(route_ids) != len(set(route_ids)):
        raise ValueError("线路编号重复。")
    route_orders = [oid for r in routes for oid in r["订单编号列表"]]
    if len(route_orders) != len(expected) or set(route_orders) != expected:
        raise ValueError("线路存在漏单或重复订单。")
    for a in assignments:
        route = next((r for r in routes if r["线路编号"] == a["线路编号"]), None)
        if route is None or a["车辆编号"] != route["车辆编号"] or route["订单编号列表"][a["配送顺序"]-1] != a["订单编号"]:
            raise ValueError("订单、车辆与线路不一致。")
        if not state_route_valid(a):
            raise ValueError("订单缺少有效道路路线。")


def state_route_valid(a):
    from 功能组件_页面共用代码.formal_dispatch import is_dijkstra_route
    return is_dijkstra_route(a)


def confirm_batch(plan, now=None):
    day = plan["配送日期"]
    if not batch_closed(day, now):
        raise ValueError("尚未到截止时间，只能查看订单，不能确认收单中的批次。")
    if plan.get("参数") != state.pricing_settings():
        raise ValueError("车辆或成本参数已变化，请重新计算。")
    with state._db_connection() as conn:
        _tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM delivery_batches WHERE delivery_day=?", (day,)).fetchone():
            raise ValueError("该配送日已统一确认，不能重复覆盖。")
        records = [json.loads(r[0]) for r in conn.execute("SELECT payload FROM orders").fetchall()]
        orders = [o for o in records if str(o.get("期望送达日期")) == day]
        validate_result(plan, orders)
        if any(o.get("状态") not in state.STATUS_FLOW[:2] for o in orders):
            raise ValueError("该批次含已进入配送流程的旧订单，不能重新分配。")
        result = copy.deepcopy(plan)
        result["确认时间"] = (now or beijing_now()).isoformat()
        assignment = {a["订单编号"]: a for a in plan["订单结果"]}
        for o in orders:
            o.update(assignment[o["订单编号"]])
            o.update({"状态": "仓库备货中", "状态序号": 2, "数据模式": "整日批次 Dijkstra 统一调度", "批次编号": day})
            conn.execute("UPDATE orders SET payload=?, updated_at=? WHERE order_id=?", (json.dumps(o, ensure_ascii=False), result["确认时间"], o["订单编号"]))
        conn.execute("INSERT INTO delivery_batches VALUES (?, ?)", (day, json.dumps(result, ensure_ascii=False)))
    return result


def advance_batch(day, target, now=None):
    transitions = {"配送途中": "仓库备货中", "已送达": "配送途中"}
    if target not in transitions:
        raise ValueError("不支持的整批状态操作。")
    with state._db_connection() as conn:
        _tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT payload FROM delivery_batches WHERE delivery_day=?", (str(day),)).fetchone()
        if not row:
            raise ValueError("请先统一确认本批次。")
        batch = json.loads(row[0])
        for assigned in batch["订单结果"]:
            row = conn.execute("SELECT payload FROM orders WHERE order_id=?", (assigned["订单编号"],)).fetchone()
            if row is None:
                raise ValueError("订单缺失，请先核查批次。")
            order = json.loads(row[0])
            if order["状态"] != transitions[target]:
                raise ValueError("批次状态已变化，请刷新后再操作。")
            order["状态"], order["状态序号"] = target, state.STATUS_FLOW.index(target)
            timestamp = (now or beijing_now()).isoformat()
            if target == "配送途中":
                order["发车时间"] = timestamp
            conn.execute("UPDATE orders SET payload=?, updated_at=? WHERE order_id=?", (json.dumps(order, ensure_ascii=False), timestamp, order["订单编号"]))


def workbook_bytes(plan):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(plan["距离矩阵_m"], index=plan["矩阵标签"], columns=plan["矩阵标签"]).to_excel(writer, sheet_name="最短距离矩阵_米")
        pd.DataFrame([{k: v for k, v in r.items() if k != "路线GeoJSON"} for r in plan["订单结果"]]).to_excel(writer, sheet_name="订单线路分配", index=False)
        pd.DataFrame([{k: v for k, v in r.items() if k not in {"路线GeoJSON", "订单编号列表"}} for r in plan["线路"]]).to_excel(writer, sheet_name="线路汇总", index=False)
    return output.getvalue()
