"""用确认线路的逐段距离重算车辆到站、等待和交付时间。"""
import json
import math
from datetime import datetime, timedelta

from 功能组件_页面共用代码.batch_solver import flexible_departure, travel_minutes
from 功能组件_页面共用代码.delivery_calendar import as_beijing

RELEASE_VERSION = "2026-10-15-smooth-stops-v37"
DONE = {"已送达", "签收完成", "已取消"}


def _display_time(value):
    # 分钟级预报向上取整，避免把 05:10:50 显示为 05:10。
    if value.second or value.microsecond:
        value = value.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return value.strftime("%m月%d日 %H:%M")


def estimate_from_plan(order, plan, orders, now=None):
    """纯计算：当前站的收货起点只影响开始服务，不覆盖车辆到站时刻。"""
    if order.get("状态") in DONE or not order.get("线路编号") or not plan:
        return None
    route = next((r for r in plan.get("线路", []) if r["线路编号"] == order["线路编号"]), None)
    if not route or order["订单编号"] not in route["订单编号列表"]:
        return None
    stop = route["订单编号列表"].index(order["订单编号"])
    sequence = route["订单编号列表"][:stop + 1]
    records = {o["订单编号"]: o for o in orders}
    records[order["订单编号"]] = order
    if any(oid not in records for oid in sequence):
        return None
    try:
        labels = plan["矩阵标签"]
        indices = {label: i for i, label in enumerate(labels)}
        depot = route.get("仓库编号", "D0")
        if depot == "D0":
            previous = 0
        elif any(d["编号"] == depot for d in plan.get("仓库", [])[1:]):
            previous = indices["新增配送点"]
        else:
            return None
        normal = float(plan["参数"]["平均速度_kmh"])
        peak = float(plan["参数"]["早高峰速度_kmh"])
        if not all(math.isfinite(v) and v > 0 for v in (normal, peak)):
            return None
        day = as_beijing(datetime.fromisoformat(order["期望送达日期"]))
        demo = bool(order.get("演示发车"))
        actual = bool(order.get("发车时间")) and not demo
        if actual:
            departed = as_beijing(datetime.fromisoformat(order["发车时间"]))
            clock = (departed - day).total_seconds() / 60
        else:
            clock = float(route.get("发车时间_分钟", order.get("计划发车_分钟", plan.get("发车分钟"))))
            if all(oid in records for oid in route["订单编号列表"]):
                def evaluate(minute):
                    current_clock, last, total_wait = minute, previous, 0.0
                    for route_oid in route["订单编号列表"]:
                        route_order = records[route_oid]
                        index = indices[route_oid]
                        current_clock += travel_minutes(float(plan["距离矩阵_m"][last][index]) / 1000,
                                                        current_clock, normal, peak)
                        wait = max(0.0, float(route_order["期望窗开始_分钟"]) - current_clock)
                        current_clock += wait
                        if current_clock > float(route_order["期望窗结束_分钟"]) + 1e-8:
                            return None
                        total_wait += wait
                        current_clock += float(route_order["服务时间_分钟"])
                        last = index
                    return {"departure": minute, "wait_minutes": total_wait}

                adjusted = flexible_departure(clock, evaluate)
                if adjusted:
                    clock = adjusted["departure"]
            departed = day + timedelta(minutes=clock)
        total_km = driving = prior_wait = prior_service = 0.0
        for oid in sequence:
            index = indices[oid]
            km = float(plan["距离矩阵_m"][previous][index]) / 1000
            earliest = float(records[oid]["期望窗开始_分钟"])
            service = float(records[oid]["服务时间_分钟"])
            if not all(math.isfinite(v) and v >= 0 for v in (km, earliest, service)):
                return None
            duration = travel_minutes(km, clock, normal, peak)
            clock += duration
            driving += duration
            total_km += km
            wait = max(0.0, earliest - clock)
            if oid == order["订单编号"]:
                eta = day + timedelta(minutes=clock)
                start = eta + timedelta(minutes=wait)
                finish = start + timedelta(minutes=service)
                break
            prior_wait += wait
            prior_service += service
            clock += wait + service
            previous = index
    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
        # 历史方案缺失输入时不拿预约时间冒充预测。
        return None
    current = as_beijing(now)
    source = "按实际发车时间逐站重算" if actual else "按各线路调整的计划发车时间逐站计算"
    if demo:
        source += "（演示发车按原定配送日计算）"
    return {"时间": eta.isoformat(), "标签": _display_time(eta), "来源": source,
            "开始服务": _display_time(start), "完成交付": _display_time(finish),
            "发车": _display_time(departed), "配送顺序": stop + 1, "道路里程_km": total_km,
            "行驶_分钟": driving, "前站等待_分钟": prior_wait, "前站服务_分钟": prior_service,
            "本站等待_分钟": wait, "本站服务_分钟": service,
            "平均速度_kmh": normal, "早高峰速度_kmh": peak,
            "已过期": current > eta,
            "临近": not demo and order.get("状态") == "配送途中" and eta - timedelta(minutes=30) <= current <= eta}


def arrival_window(order, now=None):
    """直接读取已确认批次，因此发布前确认的旧订单也使用新算法。"""
    if order.get("状态") in DONE or not order.get("线路编号"):
        return None
    from 功能组件_页面共用代码 import order_state as state
    from 功能组件_页面共用代码.batch_dispatch import _tables
    from 功能组件_页面共用代码.storage import database_url
    with state._read_db_connection() as conn:
        if not database_url():
            _tables(conn)
        row = conn.execute("SELECT payload FROM delivery_batches WHERE delivery_day=?", (order["期望送达日期"],)).fetchone()
        if not row:
            return None
        plan = json.loads(row[0])
        route = next((r for r in plan.get("线路", []) if r["线路编号"] == order["线路编号"]), None)
        if not route or order["订单编号"] not in route["订单编号列表"]:
            return None
        sequence = route["订单编号列表"]
        placeholders = ",".join("?" for _ in sequence)
        records = conn.execute(f"SELECT payload FROM orders WHERE order_id IN ({placeholders})", tuple(sequence)).fetchall()
    return estimate_from_plan(order, plan, [json.loads(r[0]) for r in records], now)
