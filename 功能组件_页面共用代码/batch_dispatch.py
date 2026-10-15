"""整日批次的指纹校验、原子确认与进度更新。"""
from __future__ import annotations

RELEASE_VERSION = "2026-10-15-map-date-v30"

import copy
import hashlib
from io import BytesIO
import json
import math

import pandas as pd

from 功能组件_页面共用代码.delivery_calendar import beijing_now
from 功能组件_页面共用代码 import order_state as state

INPUT_FIELDS = ("订单编号", "期望送达日期", "经度", "纬度", "品类", "配送重量_kg",
                "期望窗开始_分钟", "期望窗结束_分钟", "服务时间_分钟")
_MISSING = object()


def input_fingerprint(orders, legacy=False):
    fields = INPUT_FIELDS if legacy else INPUT_FIELDS + ("生姜需求量_kg", "大蒜需求量_kg")
    rows = [{key: o.get(key) for key in fields} for o in sorted(orders, key=lambda o: o["订单编号"])]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def day_orders(day):
    return sorted([o for o in state.init_orders(include_saved=True) if str(o.get("期望送达日期")) == str(day)
                   and o.get("状态") != state.CANCELLED_STATUS], key=lambda o: o["订单编号"])


def clear_all_order_data():
    """工作人员清空订单及其路线快照；计价参数仍保留。"""
    if not state.st.session_state.get("staff_authenticated"):
        raise ValueError("需要工作人员权限。")
    with state._db_connection() as conn:
        _tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        count = int(conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0])
        for table in ("delivery_drafts", "delivery_batches", "orders"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("CREATE TABLE IF NOT EXISTS warehouse_selection (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        conn.execute("DELETE FROM warehouse_selection")
        conn.execute("CREATE TABLE IF NOT EXISTS app_settings (name TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        conn.execute("INSERT OR REPLACE INTO app_settings VALUES (?, ?)", ("legacy_excel_disabled", "true"))
    state._cached_cloud_orders.clear()
    for key in ("customer_orders", "verified_order_ids", "active_order_id", "lookup_order_id", "last_order_group", "tracking_base_map"):
        state.st.session_state.pop(key, None)
    root = state.ORDER_DATA_DIR.resolve()
    exports = list(root.glob("*.xlsx")) + list(root.glob("*/*.xlsx"))
    for path in exports:
        if not path.resolve().is_relative_to(root):
            raise RuntimeError("数据库已清空，但发现订单目录外的 Excel 文件，未执行文件清理。")
    try:
        for path in exports:
            path.unlink()
    except OSError as exc:
        raise RuntimeError("数据库已清空，但部分本地 Excel 订单文件未能删除，请关闭占用文件后手动清理。") from exc
    return count


def _tables(connection):
    connection.execute("CREATE TABLE IF NOT EXISTS delivery_batches (delivery_day TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS delivery_drafts (delivery_day TEXT PRIMARY KEY, payload TEXT NOT NULL)")


def get_draft(day):
    with state._db_connection() as conn:
        _tables(conn)
        row = conn.execute("SELECT payload FROM delivery_drafts WHERE delivery_day=?", (str(day),)).fetchone()
    return json.loads(row[0]) if row else None


def load_staff_day_state(day):
    """一次读取调度页所需的批次、草稿和仓库模式。"""
    with state._db_connection() as conn:
        _tables(conn)
        conn.execute("CREATE TABLE IF NOT EXISTS warehouse_selection (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        row = conn.execute("SELECT "
                           "(SELECT payload FROM delivery_batches WHERE delivery_day=?), "
                           "(SELECT payload FROM delivery_drafts WHERE delivery_day=?), "
                           "COALESCE((SELECT count FROM warehouse_selection WHERE day=?), 1)",
                           (str(day), str(day), str(day))).fetchone()
    return (json.loads(row[0]) if row[0] else None,
            json.loads(row[1]) if row[1] else None,
            int(row[2]))


def save_draft(plan, now=None):
    """保存完整计算快照；计算期间新到订单不被误标为已计算。"""
    day = plan["配送日期"]
    from 功能组件_页面共用代码.warehouses import current
    if not current(plan):
        raise ValueError("仓库模式、仓配配置或路网已变化，请重新计算。")
    if plan.get("参数") != state.pricing_settings():
        raise ValueError("车辆或成本参数已变化，请重新计算。")
    with state._db_connection() as conn:
        _tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("CREATE TABLE IF NOT EXISTS warehouse_selection (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        selected = conn.execute("SELECT count FROM warehouse_selection WHERE day=?", (day,)).fetchone()
        if plan.get("仓库数量", 1) != (selected[0] if selected else 1):
            raise ValueError("计算期间仓库模式已变化，请重新计算。")
        if conn.execute("SELECT 1 FROM delivery_batches WHERE delivery_day=?", (day,)).fetchone():
            raise ValueError("该配送日已统一确认，不能重新计算覆盖。")
        ids = {a["订单编号"] for a in plan.get("订单结果", [])}
        records = [json.loads(r[0]) for r in conn.execute("SELECT payload FROM orders").fetchall()]
        snapshot = [o for o in records if o["订单编号"] in ids and o.get("状态") != state.CANCELLED_STATUS]
        validate_result(plan, snapshot)
        if any(o.get("状态") not in state.STATUS_FLOW[:2] for o in snapshot):
            raise ValueError("订单已进入配送流程，请刷新后检查。")
        saved = copy.deepcopy(plan)
        saved["计算时间"] = (now or beijing_now()).isoformat()
        saved["订单指纹"] = {o["订单编号"]: input_fingerprint([o]) for o in snapshot}
        conn.execute("INSERT OR REPLACE INTO delivery_drafts VALUES (?, ?)", (day, json.dumps(saved, ensure_ascii=False)))
    return saved


def calculation_groups(day, orders=None, confirmed=_MISSING, draft=_MISSING, selected_count=None):
    """列表分类，不删除订单，不改变客户的配送状态。"""
    orders = day_orders(day) if orders is None else orders
    orders = [o for o in orders if o.get("状态") != state.CANCELLED_STATUS]
    if confirmed is _MISSING:
        confirmed = get_batch(day)
    if confirmed:
        ids = {a["订单编号"] for a in confirmed["订单结果"]}
    else:
        if draft is _MISSING:
            draft = get_draft(day)
        from 功能组件_页面共用代码.warehouses import current
        marks = draft.get("订单指纹", {}) if draft and draft.get("参数") == state.pricing_settings() and current(draft, selected_count) else {}
        ids = {o["订单编号"] for o in orders if marks.get(o["订单编号"]) == input_fingerprint([o])}
    return ([o for o in orders if o["订单编号"] not in ids], [o for o in orders if o["订单编号"] in ids])


def get_batch(day):
    with state._db_connection() as conn:
        _tables(conn)
        row = conn.execute("SELECT payload FROM delivery_batches WHERE delivery_day=?", (str(day),)).fetchone()
    return json.loads(row[0]) if row else None


def validate_result(plan, orders):
    expected = {o["订单编号"] for o in orders}
    if not expected or len(expected) != len(orders):
        raise ValueError("批次为空或包含重复订单。")
    if plan.get("输入指纹") != input_fingerprint(orders, legacy="仓库" not in plan):
        raise ValueError("订单已变化，请重新计算整个批次。")
    if {str(o["期望送达日期"]) for o in orders} != {plan.get("配送日期")}:
        raise ValueError("结果配送日期不匹配。")
    assignments = plan.get("订单结果", [])
    assigned = [a["订单编号"] for a in assignments]
    if len(assigned) != len(expected) or set(assigned) != expected:
        raise ValueError("结果必须覆盖当天全部订单，且每单只能出现一次。")
    labels = plan.get("矩阵标签", [])
    matrix = plan.get("距离矩阵_m", [])
    count = plan.get("仓库数量", 1)
    customer_labels = labels[1:] if count == 1 else labels[1:-1]
    if count not in (1, 2) or len(labels) != len(expected)+count or labels[0] != "配送中心" or set(customer_labels) != expected or (count == 2 and labels[-1] != "新增配送点"):
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
    products = {o["订单编号"]: o["品类"] for o in orders}
    vehicle_products = {}
    for route in routes:
        kinds = {products[oid] for oid in route["订单编号列表"]}
        vehicle_products.setdefault(route["车辆编号"], set()).update(kinds)
        if len(kinds) != 1 or not kinds <= {"鲜面条", "姜蒜"}:
            raise ValueError("鲜面条与姜蒜不能同车混装，请重新计算分品类线路。")
    if any(len(kinds) > 1 for kinds in vehicle_products.values()):
        raise ValueError("同一车辆不能承担本批次两种品类，请分别安排车辆。")
    if "仓库" in plan:
        # 已确认的历史批次保留发布时的仓库快照；新方案在 confirm_batch 中另校验当前配置。
        if (len(plan["仓库"]) != count or plan.get("仓配配置", {}).get("仓库") != plan["仓库"]
                or plan["仓库"][0].get("编号") != "D0"
                or (count == 2 and plan["仓库"][1].get("编号") not in {"D5", "D6"})):
            raise ValueError("仓库点位与方案发布时的仓配配置不一致。")
        allowed = {d["编号"]: d for d in plan["仓库"]}
        vehicle_depots = {}
        for route in routes:
            key = route.get("仓库编号")
            if key not in allowed:
                raise ValueError("线路出发仓库不属于当前方案。")
            previous = vehicle_depots.setdefault(route["车辆编号"], key)
            if previous != key:
                raise ValueError("同一车辆不能同时驻守两个仓库。")
            features = route["路线GeoJSON"]["features"]
            if features[0]["geometry"]["coordinates"][0] != allowed[key]["坐标"] or features[-1]["geometry"]["coordinates"][-1] != allowed[key]["坐标"]:
                raise ValueError("线路未从所属仓库出发并返回。")
    for a in assignments:
        route = next((r for r in routes if r["线路编号"] == a["线路编号"]), None)
        if route is None or a["车辆编号"] != route["车辆编号"] or route["订单编号列表"][a["配送顺序"]-1] != a["订单编号"]:
            raise ValueError("订单、车辆与线路不一致。")
        if "仓库" in plan and a.get("仓库编号") != route.get("仓库编号"):
            raise ValueError("订单与线路仓库不一致。")
        if not state_route_valid(a):
            raise ValueError("订单缺少有效道路路线。")


def state_route_valid(a):
    from 功能组件_页面共用代码.formal_dispatch import is_dijkstra_route
    return is_dijkstra_route(a)


def confirm_batch(plan, now=None, depart_immediately=False):
    day = plan["配送日期"]
    from 功能组件_页面共用代码.warehouses import current
    if not current(plan):
        raise ValueError("仓库模式、仓配配置或路网已变化，请重新计算。")
    if plan.get("参数") != state.pricing_settings():
        raise ValueError("车辆或成本参数已变化，请重新计算。")
    with state._db_connection() as conn:
        _tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("CREATE TABLE IF NOT EXISTS warehouse_selection (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        selected = conn.execute("SELECT count FROM warehouse_selection WHERE day=?", (day,)).fetchone()
        if plan.get("仓库数量", 1) != (selected[0] if selected else 1):
            raise ValueError("计算期间仓库模式已变化，请重新计算。")
        if conn.execute("SELECT 1 FROM delivery_batches WHERE delivery_day=?", (day,)).fetchone():
            raise ValueError("该配送日已统一确认，不能重复覆盖。")
        records = [json.loads(r[0]) for r in conn.execute("SELECT payload FROM orders").fetchall()]
        orders = [o for o in records if str(o.get("期望送达日期")) == day and o.get("状态") != state.CANCELLED_STATUS]
        validate_result(plan, orders)
        if any(o.get("状态") not in state.STATUS_FLOW[:2] for o in orders):
            raise ValueError("该批次含已进入配送流程的旧订单，不能重新分配。")
        result = copy.deepcopy(plan)
        result["确认时间"] = (now or beijing_now()).isoformat()
        assignment = {a["订单编号"]: a for a in plan["订单结果"]}
        for o in orders:
            o.update(assignment[o["订单编号"]])
            if o.get("改约申请", {}).get("状态") == "已采纳，待线路确认":
                o["改约申请"].update({"状态": "已采纳，线路已确认", "回复": "新线路已确认，请核对新的预计送达范围并确认收货。"})
            o["行驶参数"] = {key: plan["参数"][key] for key in ("平均速度_kmh", "早高峰速度_kmh")}
            o.update({"状态": "配送途中" if depart_immediately else "仓库备货中",
                      "状态序号": 3 if depart_immediately else 2,
                      "数据模式": "演示配送中（车辆位置为仿真）" if depart_immediately else "整日批次 Dijkstra 统一调度",
                      "批次编号": day})
            if depart_immediately:
                o["发车时间"] = result["确认时间"]
                o["演示发车"] = True
            conn.execute("UPDATE orders SET payload=?, updated_at=? WHERE order_id=?", (json.dumps(o, ensure_ascii=False), result["确认时间"], o["订单编号"]))
        conn.execute("INSERT INTO delivery_batches VALUES (?, ?)", (day, json.dumps(result, ensure_ascii=False)))
        conn.execute("DELETE FROM delivery_drafts WHERE delivery_day=?", (day,))
    state._cached_cloud_orders.clear()
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
        if target == "配送途中":
            records = [json.loads(r[0]) for r in conn.execute("SELECT payload FROM orders").fetchall()]
            validate_result(batch, [o for o in records if str(o.get("期望送达日期")) == str(day)
                                    and o.get("状态") != state.CANCELLED_STATUS])
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
            if target == "已送达":
                order["实际到达时间"] = timestamp
            conn.execute("UPDATE orders SET payload=?, updated_at=? WHERE order_id=?", (json.dumps(order, ensure_ascii=False), timestamp, order["订单编号"]))
    state._cached_cloud_orders.clear()


def workbook_bytes(plan):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(plan["距离矩阵_m"], index=plan["矩阵标签"], columns=plan["矩阵标签"]).to_excel(writer, sheet_name="最短距离矩阵_米")
        pd.DataFrame([{k: v for k, v in r.items() if k != "路线GeoJSON"} for r in plan["订单结果"]]).to_excel(writer, sheet_name="订单线路分配", index=False)
        pd.DataFrame([{k: v for k, v in r.items() if k not in {"路线GeoJSON", "订单编号列表"}} for r in plan["线路"]]).to_excel(writer, sheet_name="线路汇总", index=False)
        if plan.get("仓库"):
            pd.DataFrame(plan["仓库"]).to_excel(writer, sheet_name="启用仓库", index=False)
            pd.DataFrame([{k:v for k,v in t.items() if k != "路线GeoJSON"} for t in plan.get("补货", [])]).to_excel(writer, sheet_name="分品类补货", index=False)
            pd.DataFrame([{"费用项目":k,"金额_元":v} for k,v in plan["成本"].items()]).to_excel(writer, sheet_name="计划成本", index=False)
    return output.getvalue()
