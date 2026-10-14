"""到达范围、客户确认与改约：保留原预约，确认不擅自改写路线约束。"""
import copy
import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4

from 功能组件_页面共用代码 import order_state as state
from 功能组件_页面共用代码.delivery_calendar import beijing_now, as_beijing

RELEASE_VERSION = "2026-10-14-cloud-read-v18"
DONE = {"已送达", "签收完成"}


def arrival_window(order, now=None):
    if order.get("状态") in DONE or not order.get("线路编号"):
        return None
    now = as_beijing(now)
    day = as_beijing(datetime.fromisoformat(order["期望送达日期"]))
    eta = day + timedelta(minutes=float(order.get("计划到达_分钟", 0)))
    source = "已确认路线计划（含前序站点服务和等待）"
    if order.get("发车时间"):
        actual_departure = as_beijing(datetime.fromisoformat(order["发车时间"]))
        planned_departure = day + timedelta(minutes=float(order.get("计划发车_分钟", 360)))
        eta += actual_departure - planned_departure
        source = "按实际发车时间修正的计划预测，尚未接入实时路况"
    report = order.get("到达预报")
    if report:
        start, end = (as_beijing(datetime.fromisoformat(report[k])) for k in ("开始", "结束"))
        source = "工作人员更新的送达预报"
    else:
        start, end = eta - timedelta(minutes=10), eta + timedelta(minutes=10)
        # 备货阶段取原预约内的交集；途中延误不强行裁回原时间窗。
        if not order.get("发车时间"):
            lower = day + timedelta(minutes=float(order.get("期望窗开始_分钟", 0)))
            upper = day + timedelta(minutes=float(order.get("期望窗结束_分钟", 1439)))
            if lower <= eta <= upper:
                start, end = max(start, lower), min(end, upper)
    token = hashlib.sha256(json.dumps([order.get("线路编号"), start.isoformat(), end.isoformat(), report], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    confirmed = order.get("收货确认", {})
    return {"开始": start.isoformat(), "结束": end.isoformat(), "版本": token, "来源": source,
            "标签": f"{start:%m月%d日 %H:%M}—{end:%H:%M}",
            "已确认": confirmed.get("版本") == token,
            "已过期": now > end,
            "临近": order.get("状态") == "配送途中" and start - timedelta(minutes=30) <= now <= end,
            "超出预约": start < day + timedelta(minutes=float(order.get("期望窗开始_分钟", 0))) or end > day + timedelta(minutes=float(order.get("期望窗结束_分钟", 1439)))}


def _read(conn, oid):
    row = conn.execute("SELECT payload FROM orders WHERE order_id=?", (oid,)).fetchone()
    if not row:
        raise ValueError("订单不存在。")
    return json.loads(row[0])


def _write(conn, order):
    conn.execute("UPDATE orders SET payload=?, updated_at=? WHERE order_id=?", (json.dumps(order, ensure_ascii=False), beijing_now().isoformat(), order["订单编号"]))


def _event(order, action, detail):
    order.setdefault("时间沟通记录", []).append({"时间": beijing_now().isoformat(), "操作": action, "内容": detail})


def customer_reply(oid, action, *, version=None, start=None, end=None, note="", now=None):
    if not state.customer_order(oid):
        raise ValueError("请先核验该订单。")
    with state._db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        order = _read(conn, oid)
        if order.get("状态") in DONE:
            raise ValueError("已送达订单不能再调整收货时间。")
        if action == "确认":
            window = arrival_window(order, now)
            if not window or window["版本"] != version or window["已过期"]:
                raise ValueError("送达预报已更新或过期，请刷新后重新确认。")
            if order.get("改约申请", {}).get("状态") == "待处理":
                raise ValueError("改约申请正在处理，请等待工作人员回复。")
            order["收货确认"] = {**window, "确认时间": beijing_now().isoformat()}
            _event(order, "客户确认", window["标签"])
        elif action == "改约":
            begin, finish = state.minutes_from_midnight(start), state.minutes_from_midnight(end)
            if not 0 <= begin < finish <= 1439:
                raise ValueError("请选择有效的当日收货时间范围。")
            finish_at = as_beijing(datetime.fromisoformat(order["期望送达日期"])) + timedelta(minutes=finish)
            if finish_at <= as_beijing(now):
                raise ValueError("申请的收货时间已过去，请联系工作人员处理。")
            if order.get("改约申请", {}).get("状态") == "待处理":
                raise ValueError("已有待处理申请，请勿重复提交。")
            order["改约申请"] = {"编号": uuid4().hex, "开始": start, "结束": end, "说明": note[:300], "状态": "待处理", "提交时间": beijing_now().isoformat()}
            order.pop("收货确认", None)
            _event(order, "申请改约", f"{start}—{end}；{note[:300]}")
        else:
            raise ValueError("不支持的操作。")
        _write(conn, order)


def _staff():
    if not state.st.session_state.get("staff_authenticated"):
        raise ValueError("需要工作人员权限。")


def staff_reply(oid, request_id, note):
    _staff()
    if not note.strip():
        raise ValueError("请填写处理说明，客户将看到此回复。")
    with state._db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        order = _read(conn, oid)
        request = order.get("改约申请", {})
        if request.get("编号") != request_id or request.get("状态") != "待处理":
            raise ValueError("申请状态已变化，请刷新。")
        request.update({"状态": "未调整，已回复", "回复": note[:300], "处理时间": beijing_now().isoformat()})
        _event(order, "工作人员回复", note[:300])
        _write(conn, order)


def staff_forecast(oid, start, end, note):
    _staff()
    begin, finish = state.minutes_from_midnight(start), state.minutes_from_midnight(end)
    if not 0 <= begin < finish <= 1439 or not note.strip():
        raise ValueError("请填写有效的预报时间范围和更新原因。")
    with state._db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        order = _read(conn, oid)
        if not order.get("线路编号") or order.get("状态") in DONE:
            raise ValueError("仅可更新已确认且未送达订单的预报。")
        day = as_beijing(datetime.fromisoformat(order["期望送达日期"]))
        if day + timedelta(minutes=finish) <= beijing_now():
            raise ValueError("预报结束时间不能早于当前时间。")
        order["到达预报"] = {"开始": (day+timedelta(minutes=begin)).isoformat(), "结束": (day+timedelta(minutes=finish)).isoformat(), "说明": note[:300], "更新时间": beijing_now().isoformat()}
        _event(order, "送达预报更新", f"{start}—{end}；{note[:300]}")
        _write(conn, order)


def approve_reschedule(oid, request_id):
    """发车前对整个配送日试算，成功后原子替换为待确认草案；失败保留原方案。"""
    _staff()
    from 功能组件_页面共用代码 import batch_dispatch as batch, warehouses
    from 功能组件_页面共用代码.batch_solver import solve_batch
    original = state.find_order(oid, include_saved=True)
    if not original:
        raise ValueError("订单不存在。")
    day = original["期望送达日期"]
    orders = batch.day_orders(day)
    before = json.dumps(orders, sort_keys=True, ensure_ascii=False)
    if any(o["状态"] not in state.STATUS_FLOW[:3] for o in orders):
        raise ValueError("已有车辆发出，不能自动改动线路；请协商后回复客户或更新送达预报。")
    candidate = copy.deepcopy(orders)
    changed = next(o for o in candidate if o["订单编号"] == oid)
    request = changed.get("改约申请", {})
    if request.get("编号") != request_id or request.get("状态") != "待处理":
        raise ValueError("申请已处理或已变化，请刷新。")
    changed.setdefault("原始预约", {k:changed.get(k) for k in ("最早到达", "最晚到达", "期望窗开始_分钟", "期望窗结束_分钟")})
    begin, finish = state.minutes_from_midnight(request["开始"]), state.minutes_from_midnight(request["结束"])
    changed.update({"最早到达": request["开始"], "最晚到达": request["结束"], "期望送达": f"{day} {request['开始']}", "最晚送达": f"{day} {request['结束']}", "期望窗开始_分钟":begin, "期望窗结束_分钟":finish, "允许窗开始_分钟":begin, "允许窗结束_分钟":finish})
    previous = batch.get_batch(day) or batch.get_draft(day)
    count = warehouses.selection(day)
    rates = state.pricing_settings()
    plan = solve_batch(candidate, rates, previous["发车分钟"] if previous else 360, warehouse_count=count)
    plan["输入指纹"] = batch.input_fingerprint(candidate)
    plan["计算时间"] = beijing_now().isoformat()
    plan["订单指纹"] = {o["订单编号"]: batch.input_fingerprint([o]) for o in candidate}
    batch.validate_result(plan, candidate)
    if rates != state.pricing_settings() or not warehouses.current(plan):
        raise ValueError("计算期间调度参数变化，请重新处理。")
    with state._db_connection() as conn:
        batch._tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        current = [json.loads(r[0]) for r in conn.execute("SELECT payload FROM orders").fetchall()]
        current = sorted([o for o in current if o.get("期望送达日期") == day], key=lambda o:o["订单编号"])
        if json.dumps(current, sort_keys=True, ensure_ascii=False) != before:
            raise ValueError("计算期间订单或状态变化，请刷新重试。")
        conn.execute("CREATE TABLE IF NOT EXISTS warehouse_selection (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        selected = conn.execute("SELECT count FROM warehouse_selection WHERE day=?", (day,)).fetchone()
        if (selected[0] if selected else 1) != count:
            raise ValueError("计算期间仓库模式变化，请重试。")
        batch_row = conn.execute("SELECT payload FROM delivery_batches WHERE delivery_day=?", (day,)).fetchone()
        draft_row = conn.execute("SELECT payload FROM delivery_drafts WHERE delivery_day=?", (day,)).fetchone()
        current_plan = json.loads(batch_row[0]) if batch_row else json.loads(draft_row[0]) if draft_row else None
        if current_plan != previous:
            raise ValueError("计算期间调度方案变化，请重试。")
        if previous:
            conn.execute("CREATE TABLE IF NOT EXISTS app_settings (name TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            conn.execute("INSERT OR REPLACE INTO app_settings VALUES (?, ?)", (f"replan-{day}-{uuid4().hex}", json.dumps(previous, ensure_ascii=False)))
        for o in candidate:
            for k in ("线路编号", "车辆编号", "配送顺序", "计划到达_分钟", "计划发车_分钟", "收货确认", "到达预报", "发车时间", "批次编号"):
                o.pop(k, None)
            o.update({"路线GeoJSON":None, "状态":"方案待确认", "状态序号":1})
            _event(o, "配送日重新计算", "客户改约后已重算，等待工作人员重新确认线路。")
            if o["订单编号"] == oid:
                o["改约申请"].update({"状态":"已采纳，待线路确认", "回复":"已按申请时间重算全部线路，确认后将展示新的送达范围。"})
            _write(conn, o)
        conn.execute("DELETE FROM delivery_batches WHERE delivery_day=?", (day,))
        conn.execute("INSERT OR REPLACE INTO delivery_drafts VALUES (?, ?)", (day, json.dumps(plan, ensure_ascii=False)))
    return plan
