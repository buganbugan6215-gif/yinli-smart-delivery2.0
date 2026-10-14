"""两仓共享车队：车辆固定驻仓、品类隔离、补货先于末端发车。"""
import math
import copy

RELEASE_VERSION = "2026-10-15-form-submit-v26"


def transfer_info(matrix, rates):
    from 功能组件_页面共用代码.batch_solver import travel_minutes
    from 功能组件_页面共用代码.warehouses import config
    c = config()["规则"]
    outward, backward = matrix[0][-1]/1000, matrix[-1][0]/1000
    if outward*(1+rates.get("满载续航增幅", .2))+backward > c["补货车续航_km"]:
        raise ValueError("双仓补货路程超过补货车续航。")
    departure = c["原中心货物就绪_min"]+c["补货装车_min"]
    travel = lambda km, start: travel_minutes(km, start, rates["平均速度_kmh"], rates["早高峰速度_kmh"])
    out_time = travel(outward, departure)
    ready = departure+out_time+c["补货卸车_min"]
    back_time = travel(backward, ready)
    cooling = (out_time+back_time)/60*rates["配送制冷系数_元每小时"] + (c["补货装车_min"]+c["补货卸车_min"])/60*rates["服务制冷系数_元每小时"]
    return {"就绪分钟": ready, "发车分钟": departure, "返回分钟": ready+back_time,
            "往返里程_km": outward+backward, "每车固定费_元": c["补货车固定费_元每车每天"],
            "每车运输费_元": (outward+backward)*c["补货行驶费_元每km"], "每车制冷费_元": cooling}


def replenishment(orders, vehicles, matrix, rates, count):
    if count == 1:
        return []
    from 功能组件_页面共用代码.warehouses import config
    c = config()["规则"]
    info = transfer_info(matrix, rates)
    rows = []
    for product in ("鲜面条", "姜蒜"):
        kg = sum(float(orders[i-1]["配送重量_kg"]) for v in vehicles if v.get("depot", 0) != 0
                 for i in v["sequence"] if orders[i-1]["品类"] == product)
        if kg <= 0:
            continue
        number = math.ceil(kg/c["补货车容量_kg"]-1e-10)
        rows.append({"品类": product, "起点": "原配送中心", "终点": "新增配送点", "货量_kg": kg,
                     "补货车数": number, **info, "固定费_元": number*info["每车固定费_元"],
                     "运输费_元": number*info["每车运输费_元"], "制冷费_元": number*info["每车制冷费_元"],
                     "处理费_元": kg*c["新增配送点处理费_元每kg"]})
    return rows


def cost_summary(routes, transfers, rates, count):
    from 功能组件_页面共用代码.warehouses import config
    # 原有车队全日固定费只计一次，不随两仓分配重复或因闲置消失。
    rows = {"配送车辆固定费_元": sum(rates[k+"数量"]*rates[k+"固定成本_元"] for k in ("小型冷藏车", "大型冷藏车")),
            "末端运输费_元": sum(r["运输费_元"] for r in routes),
            "末端制冷费_元": sum(r["制冷费_元"] for r in routes),
            "时间窗罚金_元": sum(r["时间窗罚金_元"] for r in routes),
            "货损费_元": sum(r["货损费_元"] for r in routes),
            "补货固定费_元": sum(r["固定费_元"] for r in transfers),
            "补货运输费_元": sum(r["运输费_元"] for r in transfers),
            "补货制冷费_元": sum(r["制冷费_元"] for r in transfers),
            "新增点处理费_元": sum(r["处理费_元"] for r in transfers)}
    comparable = sum(rows.values())
    fee = config()["规则"]["新增配送点固定费_元每天"] if count == 2 else 0.0
    return {**rows, "未含新增场地费_元": comparable, "新增场地费_元": fee,
            "含新增场地总费用_元": None if fee is None else comparable+fee,
            "运输行驶费合计_元": rows["末端运输费_元"]+rows["补货运输费_元"]}


def allocate(orders, matrix, rates, departure, strategy, count):
    from 功能组件_页面共用代码.batch_solver import route_schedule
    from 功能组件_页面共用代码.warehouses import depots, config
    depots(count)
    base_ready = config()["规则"]["原中心货物就绪_min"]
    ready = {0: base_ready}
    if count == 2:
        ready[len(orders)+1] = transfer_info(matrix, rates)["就绪分钟"]
    fleet = []
    for kind in ("小型冷藏车", "大型冷藏车"):
        for i in range(int(rates[kind+"数量"])):
            fleet.append({"id": f"{kind}-{i+1:02d}", "capacity": rates[kind+"载重_kg"],
                          "range": rates[kind+"续航_km"], "fixed": rates[kind+"固定成本_元"],
                          "per_km": rates[kind+"单位运输成本_元每km"], "sequence": []})
    priority = (lambda i: (-float(orders[i-1]["配送重量_kg"]), orders[i-1]["期望窗结束_分钟"])) if strategy == "weight" else (lambda i: (orders[i-1]["期望窗结束_分钟"], -float(orders[i-1]["配送重量_kg"])))
    # 在两个仓各尝试一遍种子次序，降低贪心首次驻仓决定的影响。
    candidates = []
    failures = []
    for seed in ([None] if count == 1 else [None, len(orders)+1]):
        vehicles = copy.deepcopy(fleet)
        indices = sorted(range(1, len(orders)+1), key=priority)
        if seed is not None:
            first = min(indices, key=lambda i: matrix[seed][i]+matrix[i][seed]-matrix[0][i]-matrix[i][0])
            indices.remove(first)
            indices.insert(0, first)
        try:
            for step, customer in enumerate(indices):
                best = None
                for vi, v in enumerate(vehicles):
                    depot_options = [v["depot"]] if v["sequence"] else list(ready)
                    if seed is not None and step == 0:
                        depot_options = [seed]
                    for depot in depot_options:
                        vehicle = {**v, "depot": depot, "ready": ready[depot]}
                        old = route_schedule(v["sequence"], orders, matrix, vehicle, departure, rates)
                        for pos in range(len(v["sequence"])+1):
                            trial = v["sequence"][:pos]+[customer]+v["sequence"][pos:]
                            schedule = route_schedule(trial, orders, matrix, vehicle, departure, rates)
                            if schedule is None:
                                continue
                            increment = schedule["variable"]-old["variable"]
                            if best is None or increment < best[0]:
                                best = (increment, vi, {**vehicle, "sequence": trial})
                if best is None:
                    raise ValueError(f"未找到可行线路：订单 {orders[customer-1]['订单编号']} 无法安排，未能覆盖全部订单；请核对车辆数量、载重、续航和时间窗。未发布部分方案。")
                vehicles[best[1]] = best[2]
            used = [v for v in vehicles if v["sequence"]]
            transfer = replenishment(orders, used, matrix, rates, count)
            score = sum(route_schedule(v["sequence"], orders, matrix, v, departure, rates)["variable"] for v in used)
            score += sum(t["固定费_元"]+t["运输费_元"]+t["制冷费_元"]+t["处理费_元"] for t in transfer)
            candidates.append((score, used))
        except ValueError as exc:
            failures.append(exc)
    if not candidates:
        raise failures[0]
    return min(candidates, key=lambda item: item[0])[1]
