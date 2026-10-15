"""运营页面只读取当前订单数据库及对应配送日的调度结果。"""
from datetime import date, timedelta

from 功能组件_页面共用代码 import delivery_calendar
from 功能组件_页面共用代码.batch_dispatch import input_fingerprint
from 功能组件_页面共用代码.batch_solver import assign_routes, route_schedule

RELEASE_VERSION = "2026-10-15-staff-map-auto-departure-v40"

PRODUCT_COLORS = {"鲜面条": "#1750df", "姜蒜": "#bd5800"}


def operating_days():
    today = delivery_calendar.beijing_now().date()
    return [str(today), str(today + timedelta(days=1))]


def select_delivery_day(st, historical=False, state_key=None):
    days = operating_days()
    options = days + (["其他日期"] if historical else [])
    saved_key = f"{state_key}_selected_day" if state_key else None
    saved = st.session_state.get(saved_key) if saved_key else None
    default = saved if saved in days else "其他日期" if historical and saved else days[0]
    chosen = st.selectbox("配送日期", options, index=options.index(default),
                          format_func=lambda d: f"{'今天' if d == days[0] else '明天'} · {d}" if d in days else d,
                          key=f"{state_key}_day_mode" if state_key else None)
    if chosen == "其他日期":
        try:
            initial_date = date.fromisoformat(saved) if saved else delivery_calendar.beijing_now().date()
        except ValueError:
            initial_date = delivery_calendar.beijing_now().date()
        day = str(st.date_input("选择其他配送日期", value=initial_date,
                                key=f"{state_key}_other_date" if state_key else None))
    else:
        day = chosen
    if saved_key:
        st.session_state[saved_key] = day
    return day


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
    """同一实时订单与参数，比较单仓和指定双仓，不使用竞赛静态结果。"""
    from 功能组件_页面共用代码.batch_solver import solve_batch
    from 功能组件_页面共用代码.warehouses import label
    rows = []
    for count in (1, 2):
        try:
            candidate = plan if plan.get("仓库数量", 1) == count else solve_batch(orders, plan["参数"], plan["发车分钟"], warehouse_count=count)
            costs = candidate["成本"]
            rows.append({"方案": label(count), "可行性": "全部订单可行", "车辆数": len({r["车辆编号"] for r in candidate["线路"]}),
                         "补货车数": sum(t["补货车数"] for t in candidate["补货"]),
                         "配送里程_公里": sum(r["总里程_km"] for r in candidate["线路"]),
                         "运输行驶费_元": costs["运输行驶费合计_元"], "未含新增场地费_元": costs["未含新增场地费_元"]})
        except ValueError as exc:
            rows.append({"方案": label(count), "可行性": str(exc), "车辆数": None, "补货车数": None,
                         "配送里程_公里": None, "运输行驶费_元": None, "未含新增场地费_元": None})
    if all(r["未含新增场地费_元"] is not None for r in rows):
        baseline = rows[0]["未含新增场地费_元"]
        for row in rows:
            row["比单仓节省_元"] = baseline-row["未含新增场地费_元"]
            row["节省比例_%"] = 100*row["比单仓节省_元"]/baseline if baseline else 0
    return {"输入指纹": input_fingerprint(orders), "参数": plan["参数"], "发车分钟": plan["发车分钟"], "结果": rows}
