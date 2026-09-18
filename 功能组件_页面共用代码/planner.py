from __future__ import annotations

import io
import json
import math
from typing import Any

import pandas as pd


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _minutes(value: Any, default: int = 0) -> int:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    if isinstance(value, str):
        value = value.strip()
        if ":" in value:
            hh, mm = value.split(":", 1)
            return int(hh) * 60 + int(float(mm))
        if "-" in value:
            value = value.split("-", 1)[0]
    return int(float(value))


def _window(value: Any, fallback_start: Any = None, fallback_end: Any = None) -> tuple[int, int]:
    if isinstance(value, str) and "-" in value:
        left, right = value.split("-", 1)
        return _minutes(left), _minutes(right)
    return _minutes(fallback_start, 240), _minutes(fallback_end, 420)


def read_uploaded_file(uploaded_file: Any) -> tuple[str, Any]:
    """读取上传文件，返回文件名和 DataFrame 或 JSON 对象。"""
    name = uploaded_file.name
    suffix = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    content = uploaded_file.getvalue()
    if suffix == "json":
        return name, json.loads(content.decode("utf-8-sig"))
    if suffix in {"xlsx", "xls"}:
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
        # 多工作表成果包优先选取包含客户、经度、纬度的客户数据表。
        ranked = []
        for sheet_name, sheet in sheets.items():
            text = " ".join(str(x) for x in sheet.iloc[:12].to_numpy().ravel() if pd.notna(x))
            score = sum(token in text for token in ("客户", "经度", "纬度", "需求"))
            ranked.append((score, sheet_name, sheet))
        _, _, selected = max(ranked, key=lambda item: item[0])
        return name, selected
    try:
        return name, pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    except UnicodeDecodeError:
        return name, pd.read_csv(io.BytesIO(content), encoding="gb18030")


def is_result_json(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("summary"), dict) and ("routes" in value or "trips" in value)


def _find_header_row(raw: pd.DataFrame) -> int | None:
    for index in range(min(len(raw), 8)):
        values = " ".join(str(x) for x in raw.iloc[index].tolist() if pd.notna(x))
        if "客户" in values and ("经度" in values or "坐标" in values):
            return index
    return None


def normalize_customers(raw: pd.DataFrame, product: str) -> pd.DataFrame:
    """兼容竞赛模板和普通 CSV，归一化客户需求字段。"""
    frame = raw.copy()

    # 兼容成果包中的“客户编号横向展开”工作簿：客户编号在列上，字段在行上。
    for row_index in range(min(len(frame), 10)):
        row_values = frame.iloc[row_index].tolist()
        id_position = next((index for index, value in enumerate(row_values) if str(value).strip() in {"客户编号", "客户"}), None)
        if id_position is None or len(row_values) - id_position < 4:
            continue
        value_position = next((index for index in range(id_position + 1, len(row_values)) if pd.notna(pd.to_numeric(row_values[index], errors="coerce"))), None)
        if value_position is None:
            continue
        ids = pd.to_numeric(pd.Series(row_values[value_position:]), errors="coerce")
        if ids.notna().sum() < 3:
            continue
        labels = frame.iloc[row_index : row_index + 16].apply(lambda row: " ".join(str(x) for x in row.iloc[:value_position].tolist() if pd.notna(x)), axis=1)

        def row_for(*terms: str) -> pd.Series | None:
            hit = labels[labels.apply(lambda text: any(term in text for term in terms))]
            return frame.iloc[hit.index[0]] if not hit.empty else None

        longitude_row = row_for("经度")
        latitude_row = row_for("纬度")
        demand_row = row_for("需求量", "日需求", "鲜面条需求")
        if longitude_row is None or latitude_row is None or demand_row is None:
            continue
        values = {"客户编号": ids.to_numpy(), "经度": pd.to_numeric(pd.Series(longitude_row.iloc[value_position:]), errors="coerce").to_numpy(), "纬度": pd.to_numeric(pd.Series(latitude_row.iloc[value_position:]), errors="coerce").to_numpy()}
        if product == "姜蒜":
            garlic_row = row_for("蒜需求", "大蒜")
            ginger_row = row_for("姜需求", "生姜")
            if garlic_row is not None and ginger_row is not None:
                values["大蒜_kg"] = pd.to_numeric(pd.Series(garlic_row.iloc[value_position:]), errors="coerce").to_numpy()
                values["生姜_kg"] = pd.to_numeric(pd.Series(ginger_row.iloc[value_position:]), errors="coerce").to_numpy()
            else:
                values["需求量_kg"] = pd.to_numeric(pd.Series(demand_row.iloc[value_position:]), errors="coerce").to_numpy()
        else:
            values["需求量_kg"] = pd.to_numeric(pd.Series(demand_row.iloc[value_position:]), errors="coerce").to_numpy()
        for target, terms in {"时间窗": ("期望时间窗", "期望配送时间窗"), "可接受时间窗": ("可接受时间窗",), "服务时间_分": ("服务时间",)}.items():
            matched = row_for(*terms)
            if matched is not None:
                values[target] = matched.iloc[value_position:].to_numpy()
        frame = pd.DataFrame(values)
        break

    header_row = _find_header_row(frame)
    if header_row is not None and header_row >= 0:
        frame = frame.iloc[header_row + 1 :].copy()
        # 竞赛工作簿的字段占两行：第一行是业务字段，下一行是“经度/纬度”等子字段。
        # 该子标题不是客户记录，必须在归一化前剔除。
        if not frame.empty:
            first_row = frame.iloc[0].astype(str).str.cat(sep=" ")
            first_id = pd.to_numeric(frame.iloc[0, 0], errors="coerce")
            if pd.isna(first_id) and ("经度" in first_row or "纬度" in first_row or "时间窗" in first_row):
                frame = frame.iloc[1:].copy()
    if frame.shape[1] >= 3 and not any("客户" in str(c) for c in frame.columns):
        if product == "鲜面条" and frame.shape[1] >= 9:
            frame = frame.iloc[:, :9]
            frame.columns = ["客户编号", "经度", "纬度", "需求量_kg", "期望开始", "期望结束", "可接受开始", "可接受结束", "服务时间_分"]
        elif product == "姜蒜" and frame.shape[1] >= 10:
            frame = frame.iloc[:, :10]
            frame.columns = ["客户编号", "经度", "纬度", "大蒜_kg", "生姜_kg", "期望开始", "期望结束", "可接受开始", "可接受结束", "服务时间_分"]
    aliases = {
        "客户编号": ["客户编号", "客户", "customer", "id", "编号"],
        "经度": ["经度", "longitude", "lon", "x"],
        "纬度": ["纬度", "latitude", "lat", "y"],
        "需求量_kg": ["需求量_kg", "需求量", "需求量(kg)", "demand", "demand_kg"],
        "期望开始": ["期望开始", "期望时间窗开始", "期望窗开始", "earliest"],
        "期望结束": ["期望结束", "期望时间窗结束", "期望窗结束", "latest"],
        "可接受开始": ["可接受开始", "可接受时间窗开始", "acceptable_start"],
        "可接受结束": ["可接受结束", "可接受时间窗结束", "acceptable_end"],
        "服务时间_分": ["服务时间_分", "服务时间", "service_min", "service_time"],
        "时间窗": ["时间窗", "期望时间窗", "time_window", "window"],
    }
    renamed: dict[str, str] = {}
    for target, candidates in aliases.items():
        for column in frame.columns:
            compact = str(column).replace(" ", "").replace("\n", "")
            if compact in {str(candidate).replace(" ", "") for candidate in candidates}:
                renamed[column] = target
                break
    frame = frame.rename(columns=renamed)
    if product == "姜蒜" and "需求量_kg" not in frame.columns and {"大蒜_kg", "生姜_kg"}.issubset(frame.columns):
        frame["需求量_kg"] = pd.to_numeric(frame["大蒜_kg"], errors="coerce").fillna(0) + pd.to_numeric(frame["生姜_kg"], errors="coerce").fillna(0)
    required = ["客户编号", "经度", "纬度", "需求量_kg"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError("缺少必要字段：" + "、".join(missing) + "。需要客户编号、经度、纬度和需求量。")
    for column in ["客户编号", "经度", "纬度", "需求量_kg", "服务时间_分", "期望开始", "期望结束", "可接受开始", "可接受结束"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[frame["客户编号"].notna() & frame["经度"].notna() & frame["纬度"].notna() & frame["需求量_kg"].notna()].copy()
    if frame.empty:
        raise ValueError("没有读取到有效客户记录。")
    if "时间窗" not in frame.columns:
        frame["时间窗"] = frame.apply(lambda row: f"{_minutes(row.get('期望开始'), 240):03d}-{_minutes(row.get('期望结束'), 420):03d}", axis=1)
    frame["产品"] = product
    frame["服务时间_分"] = frame.get("服务时间_分", pd.Series(15, index=frame.index)).fillna(15)
    frame["客户编号"] = frame["客户编号"].astype(int)
    return frame.reset_index(drop=True)


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value)) * 1.15


def generate_plan(customers: pd.DataFrame, settings: dict[str, float]) -> dict[str, Any]:
    """基于客户坐标的快速可行初算，不替代正式最短路和 ALNS 求解。"""
    depot_lon = settings.get("depot_lon", 104.26105)
    depot_lat = settings.get("depot_lat", 30.851137)
    capacity = max(1.0, settings.get("capacity_kg", 1500.0))
    requested_vehicles = max(1, int(settings.get("vehicles", 1)))
    required_by_capacity = math.ceil(float(customers["需求量_kg"].sum()) / capacity)
    vehicle_count = max(requested_vehicles, required_by_capacity)
    speed = max(1.0, settings.get("speed_kmh", 35.0))
    fixed_rate = settings.get("fixed_cost", 200.0)
    transport_rate = settings.get("transport_cost_per_km", 2.5)
    cooling_rate = settings.get("cooling_cost_per_km", 0.45)
    late_rate = settings.get("late_penalty_per_min", 0.5)
    loss_rate = settings.get("loss_cost_per_kg", 0.0336)
    remaining = {int(row["客户编号"]): row for _, row in customers.iterrows()}
    routes: list[list[pd.Series]] = []
    for _ in range(vehicle_count):
        route: list[pd.Series] = []
        load = 0.0
        current_lon, current_lat = depot_lon, depot_lat
        while remaining:
            candidates = []
            for customer_id, row in remaining.items():
                demand = float(row["需求量_kg"])
                if load + demand <= capacity + 1e-9:
                    start, _ = _window(row.get("时间窗"), row.get("期望开始"), row.get("期望结束"))
                    distance = haversine_km(current_lon, current_lat, float(row["经度"]), float(row["纬度"]))
                    candidates.append((distance + abs(start - 300) * 0.002, customer_id, row))
            if not candidates:
                break
            _, customer_id, row = min(candidates, key=lambda item: item[0])
            route.append(row)
            load += float(row["需求量_kg"])
            current_lon, current_lat = float(row["经度"]), float(row["纬度"])
            del remaining[customer_id]
        if route:
            routes.append(route)
    while remaining:
        route = []
        load = 0.0
        current_lon, current_lat = depot_lon, depot_lat
        while remaining:
            candidates = [(haversine_km(current_lon, current_lat, float(row["经度"]), float(row["纬度"])), customer_id, row) for customer_id, row in remaining.items() if load + float(row["需求量_kg"]) <= capacity + 1e-9]
            if not candidates:
                raise ValueError("存在需求量超过车辆额定载重的客户，无法生成容量可行方案。")
            _, customer_id, row = min(candidates, key=lambda item: item[0])
            route.append(row)
            load += float(row["需求量_kg"])
            current_lon, current_lat = float(row["经度"]), float(row["纬度"])
            del remaining[customer_id]
            if len(route) >= 8:
                break
        routes.append(route)
    route_rows, arrival_rows = [], []
    total_distance = total_fixed = total_transport = total_cooling = total_penalty = total_loss = 0.0
    ontime = 0
    for vehicle_index, route in enumerate(routes, 1):
        if not route:
            continue
        earliest = min(_window(row.get("时间窗"), row.get("期望开始"), row.get("期望结束"))[0] for row in route)
        clock = max(0.0, earliest - 60)
        current_lon, current_lat = depot_lon, depot_lat
        load = sum(float(row["需求量_kg"]) for row in route)
        vehicle_distance = 0.0
        vehicle_penalty = 0.0
        vehicle_ontime = 0
        for stop_index, row in enumerate(route, 1):
            leg = haversine_km(current_lon, current_lat, float(row["经度"]), float(row["纬度"]))
            travel = leg / speed * 60
            arrival = clock + travel
            start, end = _window(row.get("时间窗"), row.get("期望开始"), row.get("期望结束"))
            service_start = max(arrival, start)
            service = _number(row.get("服务时间_分"), 15)
            late = max(0.0, service_start - end)
            early = max(0.0, start - arrival)
            is_ontime = arrival >= start and arrival <= end
            if is_ontime:
                ontime += 1
                vehicle_ontime += 1
            vehicle_penalty += late * late_rate
            arrival_rows.append({"车辆编号": vehicle_index, "停靠序号": stop_index, "客户编号": int(row["客户编号"]), "产品": row["产品"], "需求量_kg": float(row["需求量_kg"]), "路段距离_km": leg, "路段速度_kmh": speed, "到达时刻": f"{int(arrival // 60):02d}:{int(arrival % 60):02d}", "开始服务时刻": f"{int(service_start // 60):02d}:{int(service_start % 60):02d}", "早到偏差_min": early, "迟到偏差_min": late, "期望窗内": is_ontime})
            clock = service_start + service
            current_lon, current_lat = float(row["经度"]), float(row["纬度"])
            vehicle_distance += leg
        return_leg = haversine_km(current_lon, current_lat, depot_lon, depot_lat)
        vehicle_distance += return_leg
        clock += return_leg / speed * 60
        fixed = fixed_rate
        transport = vehicle_distance * transport_rate
        cooling = vehicle_distance * cooling_rate
        loss = load * loss_rate
        total_fixed += fixed
        total_transport += transport
        total_cooling += cooling
        total_penalty += vehicle_penalty
        total_loss += loss
        total_distance += vehicle_distance
        route_rows.append({"车辆编号": vehicle_index, "产品": route[0]["产品"], "车型": "上传参数车辆", "客户数": len(route), "配送量_kg": load, "额定载重_kg": capacity, "装载率": load / capacity, "发车时刻": f"{int((earliest - 60) // 60):02d}:{int((earliest - 60) % 60):02d}", "回场时刻": f"{int(clock // 60):02d}:{int(clock % 60):02d}", "总里程_km": vehicle_distance, "固定成本_元": fixed, "运输成本_元": transport, "制冷成本_元": cooling, "时间窗惩罚_元": vehicle_penalty, "货损成本_元": loss, "总成本_元": fixed + transport + cooling + vehicle_penalty + loss, "访问顺序": "配送中心0→" + "→".join(f"客户{int(row['客户编号']):02d}" for row in route) + "→配送中心0", "准时客户": vehicle_ontime})
    total_cost = total_fixed + total_transport + total_cooling + total_penalty + total_loss
    summary = {"solution_type": "上传数据快速可行初算，不替代正式 Dijkstra 与 ALNS 求解", "customers": len(customers), "vehicles_used": len(route_rows), "total_load_kg": float(customers["需求量_kg"].sum()), "total_distance_km": total_distance, "fixed_cost": total_fixed, "transport_cost": total_transport, "cooling_cost": total_cooling, "time_penalty_cost": total_penalty, "loss_cost": total_loss, "total_cost": total_cost, "ontime_customers": ontime, "ontime_rate": ontime / len(customers), "average_load_rate": sum(row["装载率"] for row in route_rows) / len(route_rows), "cost_breakdown": {"fixed_cost": total_fixed, "transport_cost": total_transport, "cooling_cost": total_cooling, "time_penalty_cost": total_penalty, "loss_cost": total_loss}, "validations": {"all_customers_once": len(arrival_rows) == len(customers), "capacity": all(row["配送量_kg"] <= row["额定载重_kg"] for row in route_rows), "coordinates_available": True}}
    return {"summary": summary, "routes": pd.DataFrame(route_rows), "arrivals": pd.DataFrame(arrival_rows), "customers": customers.copy(), "mode": "快速可行初算"}


def result_json_to_plan(payload: dict[str, Any], product: str) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}))
    summary.setdefault("solution_type", "已保存最终结果")
    route_rows = []
    arrival_rows = []
    # 第一问/姜蒜使用 routes；车辆复用结果使用 trips。统一转换成页面表格。
    route_items = payload.get("routes", []) or payload.get("trips", [])
    for index, route in enumerate(route_items, 1):
        if not isinstance(route, dict):
            continue
        route_product = route.get("product", product)
        vehicle = route.get("vehicle_slot") or route.get("physical_vehicle") or f"趟次{index}"
        capacity = route.get("capacity")
        load = route.get("load")
        route_rows.append({"车辆编号": vehicle, "产品": route_product, "车型": route.get("vehicle_kind") or route.get("vehicle_type"), "客户数": len(route.get("route", [])), "配送量_kg": load, "额定载重_kg": capacity, "装载率": _number(load) / max(_number(capacity, 1), 1), "发车时刻": route.get("departure"), "回场时刻": route.get("return_time"), "总里程_km": route.get("distance"), "固定成本_元": route.get("fixed"), "运输成本_元": route.get("transport"), "制冷成本_元": route.get("cooling"), "时间窗惩罚_元": route.get("time_penalty"), "货损成本_元": route.get("loss"), "总成本_元": route.get("cost") or route.get("variable_cost"), "物理车辆": route.get("physical_vehicle"), "访问顺序": "配送中心0→" + "→".join(f"客户{int(x):02d}" for x in route.get("route", [])) + "→配送中心0"})
        for detail in route.get("details", []):
            if isinstance(detail, dict):
                arrival_rows.append({"车辆编号": vehicle, "产品": route_product, "客户编号": detail.get("customer"), "到达时刻_分钟": detail.get("arrival"), "开始服务时刻_分钟": detail.get("service_start"), "离开时刻_分钟": detail.get("leave"), "早到偏差_min": detail.get("early"), "迟到偏差_min": detail.get("late"), "期望窗内": detail.get("ontime"), "路段距离_km": detail.get("leg_distance"), "装载前_kg": detail.get("load_before_leg")})
    routes_frame = pd.DataFrame(route_rows)
    arrivals_frame = pd.DataFrame(arrival_rows)
    summary.setdefault("total_cost", summary.get("cost"))
    summary.setdefault("total_distance_km", summary.get("distance"))
    summary.setdefault("vehicles_used", summary.get("physical_vehicle_count"))
    if summary.get("customers") is None and not arrivals_frame.empty and "客户编号" in arrivals_frame:
        identity = [column for column in ["产品", "客户编号"] if column in arrivals_frame]
        summary["customers"] = int(arrivals_frame.drop_duplicates(identity).shape[0])
    if summary.get("total_load_kg") is None and not routes_frame.empty:
        summary["total_load_kg"] = float(pd.to_numeric(routes_frame["配送量_kg"], errors="coerce").sum())
    if summary.get("ontime_customers") is None and not arrivals_frame.empty and "期望窗内" in arrivals_frame:
        summary["ontime_customers"] = int(arrivals_frame["期望窗内"].fillna(False).astype(bool).sum())
    if summary.get("ontime_rate") is None and summary.get("customers"):
        summary["ontime_rate"] = _number(summary.get("ontime_customers")) / _number(summary.get("customers"), 1)
    cost_fields = ["fixed_cost", "transport_cost", "cooling_cost", "time_penalty_cost", "loss_cost"]
    for summary_key in cost_fields:
        if summary.get(summary_key) is None and not routes_frame.empty:
            route_key = {"fixed_cost": "固定成本_元", "transport_cost": "运输成本_元", "cooling_cost": "制冷成本_元", "time_penalty_cost": "时间窗惩罚_元", "loss_cost": "货损成本_元"}[summary_key]
            if route_key in routes_frame:
                summary[summary_key] = float(pd.to_numeric(routes_frame[route_key], errors="coerce").sum())
    summary["cost_breakdown"] = {key: summary.get(key) for key in cost_fields if summary.get(key) is not None}
    return {"summary": summary, "routes": routes_frame, "arrivals": arrivals_frame, "customers": pd.DataFrame(), "mode": "已保存最终结果"}
