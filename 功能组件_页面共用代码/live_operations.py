"""运营页面只读取当前订单数据库及对应配送日的调度结果。"""
from datetime import timedelta

from 功能组件_页面共用代码 import delivery_calendar
from 功能组件_页面共用代码.batch_dispatch import input_fingerprint
from 功能组件_页面共用代码.batch_solver import assign_routes, route_schedule

PRODUCT_COLORS = {"鲜面条": "#1750df", "姜蒜": "#bd5800"}


def operating_days():
    today = delivery_calendar.beijing_now().date()
    return [str(today), str(today + timedelta(days=1))]


def select_delivery_day(st, historical=False):
    days = operating_days()
    chosen = st.selectbox("配送日期", days + (["其他日期"] if historical else []),
                          format_func=lambda d: f"{'今天' if d == days[0] else '明天'} · {d}" if d in days else d)
    return str(st.date_input("选择其他配送日期")) if chosen == "其他日期" else chosen


def order_summary(orders):
    return {"配送子单": len(orders), "客户提交次数": len({o.get("总单编号") or o["订单编号"] for o in orders}),
            "货量_kg": sum(float(o["配送重量_kg"]) for o in orders),
            "已签收": sum(o.get("状态") == "签收完成" for o in orders)}


def plan_metrics(plan):
    rates = plan["参数"]
    rows = []
    for r in plan["线路"]:
        kind = "小型冷藏车" if r["车辆编号"].startswith("小型冷藏车") else "大型冷藏车"
        fixed = rates[kind + "固定成本_元"]
        transport = r["总里程_km"] * rates[kind + "单位运输成本_元每km"]
        rows.append({"线路编号": r["线路编号"], "品类": r.get("品类", "旧方案未记录"), "车辆编号": r["车辆编号"],
                     "里程_km": r["总里程_km"], "货量_kg": r["总重量_kg"], "固定成本_元": fixed,
                     "里程成本_元": transport, "固定及里程成本_元": fixed + transport})
    return rows


def compare_strategies(orders, plan):
    """同一订单快照、同一矩阵、同一车辆约束；只改变插入次序。"""
    by_id = {o["订单编号"]: o for o in orders}
    ordered = [by_id[oid] for oid in plan["矩阵标签"][1:]]
    rows = []
    for strategy, label in (("deadline", "时间窗优先"), ("weight", "重量优先")):
        try:
            vehicles = assign_routes(ordered, plan["距离矩阵_m"], plan["参数"], plan["发车分钟"], strategy=strategy)
            schedules = [route_schedule(v["sequence"], ordered, plan["距离矩阵_m"], v, plan["发车分钟"], plan["参数"]) for v in vehicles]
            rows.append({"方案": label, "可行性": "全部订单可行", "车辆数": len(vehicles),
                "里程_km": sum(s["km"] for s in schedules),
                "固定及里程成本_元": sum(v["fixed"] + s["km"] * v["per_km"] for v, s in zip(vehicles, schedules))})
        except ValueError:
            rows.append({"方案": label, "可行性": "当前启发式未找到全量可行方案", "车辆数": None,
                         "里程_km": None, "固定及里程成本_元": None})
    return {"输入指纹": input_fingerprint(orders), "参数": plan["参数"], "发车分钟": plan["发车分钟"], "结果": rows}
