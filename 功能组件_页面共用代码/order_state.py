from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

import pandas as pd
import streamlit as st

from 功能组件_页面共用代码.delivery_calendar import beijing_now, delivery_day

STATUS_FLOW = ["订单已提交", "方案待确认", "仓库备货中", "配送途中", "已送达", "签收完成"]
ROOT = Path(__file__).resolve().parents[1]
ORDER_DATA_DIR = Path(os.getenv("YL_ORDER_DATA_DIR", str(ROOT / "客户订单数据")))
SETTINGS_PATH = ORDER_DATA_DIR / "调价参数.json"
ORDER_DB_PATH = ORDER_DATA_DIR / "订单状态.db"
DEPOT_LON, DEPOT_LAT = 104.26104981303031, 30.851137170192068


def staff_password() -> str | None:
    """密码只从运行环境或 Streamlit secrets 读取。"""
    configured = os.getenv("YL_STAFF_PASSWORD")
    if configured:
        return configured
    try:
        return st.secrets.get("YL_STAFF_PASSWORD")
    except (FileNotFoundError, RuntimeError):
        return None


def pricing_settings() -> dict[str, float]:
    defaults = {
        "起步价_元": 12.0, "里程价_元每km": 0.8,
        "鲜面条_元每kg": 0.75, "姜蒜_元每kg": 0.41,
        "小型冷藏车数量": 6.0, "小型冷藏车载重_kg": 650.0,
        "小型冷藏车固定成本_元": 120.0, "小型冷藏车单位运输成本_元每km": 1.6,
        "小型冷藏车续航_km": 260.0,
        "大型冷藏车数量": 2.0, "大型冷藏车载重_kg": 1500.0,
        "大型冷藏车固定成本_元": 220.0, "大型冷藏车单位运输成本_元每km": 2.2,
        "大型冷藏车续航_km": 320.0,
        "配送制冷系数_元每小时": 18.0, "服务制冷系数_元每小时": 12.0,
        "早到惩罚_元每小时": 8.0, "晚到惩罚_元每小时": 30.0,
        "运输货损率": 0.005, "服务货损率": 0.002,
        "平均速度_kmh": 35.0, "早高峰速度_kmh": 25.0,
        "鲜面条单价_元每kg": 8.0, "生姜单价_元每kg": 10.0, "大蒜单价_元每kg": 12.0,
    }
    try:
        saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return {key: float(saved.get(key, value)) for key, value in defaults.items()}
    except (OSError, ValueError, TypeError):
        return defaults


def save_pricing_settings(values: dict[str, float]) -> None:
    ORDER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")


def minutes_from_midnight(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    return hour * 60 + minute


def service_minutes(product: str, noodle_kg: float = 0, ginger_kg: float = 0, garlic_kg: float = 0) -> int:
    q = float(noodle_kg if product == "鲜面条" else ginger_kg + garlic_kg)
    if product == "鲜面条":
        return 10 if q <= 25 else 15 if q <= 50 else 20 if q < 90 else 25 if q <= 130 else 30
    return 10 if q <= 90 else 15 if q <= 190 else 20 if q <= 290 else 25 if q <= 390 else 30 if q <= 490 else 35 if q <= 590 else 40


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    from math import asin, cos, radians, sin, sqrt
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(a))


def gcj02_to_wgs84(lon: float, lat: float) -> tuple[float, float]:
    """将高德返回的 GCJ-02 坐标近似转换为路网使用的 WGS84。"""
    from math import cos, pi, sin, sqrt
    if not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271):
        return lon, lat
    x, y = lon - 105.0, lat - 35.0
    dlat = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*sqrt(abs(x))
    dlat += (20.0*sin(6.0*x*pi) + 20.0*sin(2.0*x*pi))*2.0/3.0
    dlat += (20.0*sin(y*pi) + 40.0*sin(y/3.0*pi))*2.0/3.0
    dlat += (160.0*sin(y/12.0*pi) + 320*sin(y*pi/30.0))*2.0/3.0
    dlon = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*sqrt(abs(x))
    dlon += (20.0*sin(6.0*x*pi) + 20.0*sin(2.0*x*pi))*2.0/3.0
    dlon += (20.0*sin(x*pi) + 40.0*sin(x/3.0*pi))*2.0/3.0
    dlon += (150.0*sin(x/12.0*pi) + 300.0*sin(x/30.0*pi))*2.0/3.0
    radlat = lat / 180.0 * pi
    magic = 1 - 0.00669342162296594323 * sin(radlat) ** 2
    sqrtmagic = sqrt(magic)
    dlat = (dlat * 180.0) / ((6335552.717000426 / (magic * sqrtmagic)) * pi)
    dlon = (dlon * 180.0) / ((6378245.0 / sqrtmagic * cos(radlat)) * pi)
    return lon * 2 - (lon + dlon), lat * 2 - (lat + dlat)


def estimate_delivery_fee(product: str, quantity_kg: float, longitude: float | None = None, latitude: float | None = None) -> dict[str, float]:
    """报价由起步价、品类重量价与参考里程价组成。"""
    rates = pricing_settings()
    weight = max(0.0, float(quantity_kg)) * rates[f"{product}_元每kg"]
    distance = haversine_km(DEPOT_LON, DEPOT_LAT, longitude, latitude) if longitude is not None and latitude is not None else 0.0
    mileage = distance * rates["里程价_元每km"]
    return {"起步价_元": rates["起步价_元"], "重量价_元": round(weight, 2), "参考距离_km": round(distance, 2), "里程价_元": round(mileage, 2), "预估费用_元": round(rates["起步价_元"] + weight + mileage, 2)}


def _secret(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except (FileNotFoundError, RuntimeError):
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def geocode_address(address: str) -> tuple[float, float, str, str] | None:
    """优先高德地理编码，未配置密钥时回退到 OpenStreetMap。"""
    query = address.strip()
    if len(query) < 2:
        return None
    amap_key = _secret("AMAP_WEB_SERVICE_KEY")
    if amap_key:
        url = "https://restapi.amap.com/v3/geocode/geo?" + urlencode({"address": query, "city": "成都", "key": amap_key, "output": "JSON"})
        try:
            with urlopen(Request(url, headers={"User-Agent": "YinliDelivery/2.0"}), timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            geocodes = payload.get("geocodes") or []
            if payload.get("status") == "1" and geocodes:
                lon, lat = (float(value) for value in geocodes[0]["location"].split(","))
                lon, lat = gcj02_to_wgs84(lon, lat)
                formatted = str(geocodes[0].get("formatted_address") or query)
                return lon, lat, formatted, "高德地图"
        except Exception:
            pass

    candidates = [query, f"四川省成都市{query}", f"{query} 成都 四川"]
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        url = "https://nominatim.openstreetmap.org/search?" + urlencode({"q": candidate, "format": "jsonv2", "limit": 5, "countrycodes": "cn", "addressdetails": 1})
        try:
            request = Request(url, headers={"User-Agent": "YinliDelivery/2.0 (competition-demo)"})
            with urlopen(request, timeout=8) as response:
                results.extend(json.loads(response.read().decode("utf-8")))
        except Exception:
            continue
    if not results:
        return None
    def score(item: dict[str, Any]) -> tuple[int, float]:
        text = str(item.get("display_name", ""))
        address_info = item.get("address") or {}
        in_chengdu = "成都" in text or "成都" in json.dumps(address_info, ensure_ascii=False)
        return (1 if in_chengdu else 0, float(item.get("importance", 0)))
    best = max(results, key=score)
    try:
        return float(best["lon"]), float(best["lat"]), str(best.get("display_name", query)), "OpenStreetMap"
    except (KeyError, TypeError, ValueError):
        return None


def _db_connection() -> sqlite3.Connection:
    ORDER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(ORDER_DB_PATH, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL)")
    return connection


def save_order_record(order: dict[str, Any]) -> None:
    payload = json.dumps(order, ensure_ascii=False, default=str)
    with _db_connection() as connection:
        connection.execute(
            "INSERT INTO orders(order_id, updated_at, payload) VALUES (?, ?, ?) ON CONFLICT(order_id) DO UPDATE SET updated_at=excluded.updated_at, payload=excluded.payload",
            (str(order.get("订单编号")), datetime.now().isoformat(timespec="seconds"), payload),
        )


def load_order_records() -> list[dict[str, Any]]:
    try:
        with _db_connection() as connection:
            rows = connection.execute("SELECT payload FROM orders ORDER BY updated_at DESC").fetchall()
        return [json.loads(row[0]) for row in rows]
    except Exception:
        return []


def _route_geojson(longitude: float | None, latitude: float | None) -> dict[str, Any] | None:
    if longitude is None or latitude is None:
        return None
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"label": "订单演示调度线", "route_mode": "演示坐标连线"}, "geometry": {"type": "LineString", "coordinates": [[DEPOT_LON, DEPOT_LAT], [float(longitude), float(latitude)]]}}]}


def _excel_value(value: Any) -> Any:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value


def save_order_to_excel(order: dict[str, Any]) -> str:
    delivery_date = str(order.get("期望送达日期") or datetime.now().date())
    product = str(order.get("品类", "未分类"))
    ORDER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    date_key = delivery_date.replace("-", "")
    product_key = "鲜面" if product == "鲜面条" else "姜蒜"
    path = ORDER_DATA_DIR / f"{date_key}{product_key}.xlsx"
    row = pd.DataFrame([{key: _excel_value(value) for key, value in order.items() if key not in {"状态序号", "保存路径", "保存状态"}}])
    existing = pd.read_excel(path) if path.exists() else pd.DataFrame()
    pd.concat([existing, row], ignore_index=True).to_excel(path, index=False)
    return str(path.relative_to(ROOT))


def _parse_record(item: dict[str, Any], path: Path) -> dict[str, Any]:
    for key in ("路线GeoJSON", "异常反馈", "报价明细"):
        if isinstance(item.get(key), str) and item[key].strip().startswith(("{", "[")):
            try:
                item[key] = json.loads(item[key])
            except ValueError:
                pass
    item["保存路径"] = str(path.relative_to(ROOT))
    item["状态序号"] = STATUS_FLOW.index(item.get("状态")) if item.get("状态") in STATUS_FLOW else 0
    item.setdefault("数据模式", "本地演示订单")
    return item


def init_orders(include_saved: bool = False) -> list[dict[str, Any]]:
    """当前会话保持快捷访问；按订单号查询和工作人员页面读取共享记录。"""
    if "customer_orders" not in st.session_state:
        st.session_state["customer_orders"] = []
    own = st.session_state["customer_orders"]
    if not include_saved:
        allowed = {item["订单编号"] for item in own} | set(st.session_state.get("verified_order_ids", []))
        current = {item["订单编号"]: item for item in load_order_records()}
        # 返回共享数据库的最新值；不得用客户端旧快照覆盖调度状态。
        return [current[oid] for oid in sorted(allowed) if oid in current]
    records: dict[str, dict[str, Any]] = {}
    paths = list(ORDER_DATA_DIR.glob("*.xlsx")) + list(ORDER_DATA_DIR.glob("*/*.xlsx"))
    for path in paths:
        try:
            for raw in pd.read_excel(path).fillna("").to_dict("records"):
                item = _parse_record(raw, path)
                records[str(item.get("订单编号"))] = item
        except Exception:
            continue
    # 旧 Excel 首次迁移采用 INSERT OR IGNORE，不能覆盖其他会话更新。
    with _db_connection() as connection:
        for item in records.values():
            connection.execute("INSERT OR IGNORE INTO orders VALUES (?, ?, ?)",
                               (str(item["订单编号"]), beijing_now().isoformat(), json.dumps(item, ensure_ascii=False, default=str)))
    for item in load_order_records():
        records[str(item.get("订单编号"))] = item
    return sorted(records.values(), key=lambda item: str(item.get("提交时间", "")), reverse=True)


def create_order(payload: dict[str, Any]) -> dict[str, Any]:
    init_orders()
    own_orders = st.session_state["customer_orders"]
    now = beijing_now()
    payload = dict(payload)
    day = delivery_day(now).isoformat()
    payload["期望送达日期"] = day
    payload["期望送达"] = f"{day} {payload.get('最早到达', '00:00')}"
    payload["最晚送达"] = f"{day} {payload.get('最晚到达', '00:00')}"
    longitude = float(payload["经度"]) if payload.get("经度") not in (None, "") else None
    latitude = float(payload["纬度"]) if payload.get("纬度") not in (None, "") else None
    quote = estimate_delivery_fee(str(payload.get("品类", "")), float(payload.get("配送重量_kg", 0)), longitude, latitude)
    product = str(payload.get("品类", ""))
    earliest = str(payload.get("最早到达", "00:00"))
    latest = str(payload.get("最晚到达", "00:00"))
    noodle = float(payload.get("鲜面需求量_kg", payload.get("配送重量_kg", 0)) if product == "鲜面条" else 0)
    ginger = float(payload.get("生姜需求量_kg", 0))
    garlic = float(payload.get("大蒜需求量_kg", 0))
    enriched = {
        "期望窗开始_分钟": minutes_from_midnight(earliest),
        "期望窗结束_分钟": minutes_from_midnight(latest),
        "允许窗开始_分钟": max(0, minutes_from_midnight(earliest) - 30),
        "允许窗结束_分钟": min(1439, minutes_from_midnight(latest) + 30),
        "服务时间_分钟": service_minutes(product, noodle, ginger, garlic),
    }
    if longitude is None or latitude is None or not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        raise ValueError("请提供有效的收货坐标。")
    if float(payload.get("配送重量_kg", 0)) <= 0 or minutes_from_midnight(latest) <= minutes_from_midnight(earliest):
        raise ValueError("重量必须大于零，最晚送达时间须晚于最早到达时间。")
    order = {**payload, **enriched, "订单编号": f"YL{now:%Y%m%d%H%M%S}{uuid4().hex[:12].upper()}", "提交时间": now.isoformat(timespec="seconds"), "状态": STATUS_FLOW[1], "状态序号": 1, "数据模式": "等待整日统一调度", "报价明细": quote, "预估费用_元": quote["预估费用_元"], "路线GeoJSON": None}
    try:
        order["保存路径"] = save_order_to_excel(order)
        order["保存状态"] = "已保存到本机演示订单表"
    except Exception as exc:
        order["保存状态"] = f"本机保存失败：{exc}"
    save_order_record(order)
    own_orders.insert(0, order)
    return order


def verify_customer_order(order_id: str, phone_tail: str) -> dict[str, Any] | None:
    """客户需要订单编号和联系电话后四位；核验只授予该订单的会话权限。"""
    with _db_connection() as connection:
        row = connection.execute("SELECT payload FROM orders WHERE order_id=?", (order_id.strip().upper(),)).fetchone()
    item = json.loads(row[0]) if row else None
    if item and len(phone_tail) == 4 and phone_tail.isdigit() and str(item.get("联系电话", "")).endswith(phone_tail):
        allowed = set(st.session_state.get("verified_order_ids", []))
        allowed.add(item["订单编号"])
        st.session_state["verified_order_ids"] = sorted(allowed)
        return item
    return None


def customer_order(order_id: str) -> dict[str, Any] | None:
    return next((item for item in init_orders() if item["订单编号"] == order_id), None)


def customer_update(order_id: str, changes: dict[str, Any], receipt: bool = False) -> None:
    if not customer_order(order_id):
        raise ValueError("请先核验该订单。")
    with _db_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT payload FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if row is None:
            raise ValueError("订单不存在。")
        order = json.loads(row[0])
        if receipt:
            if order["状态"] != "已送达":
                raise ValueError("仅已送达订单可以签收，请刷新状态。")
            order.update({"状态": "签收完成", "状态序号": 5, "签收结果": "正常签收"})
        elif "异常反馈" in changes:
            order["异常反馈"] = changes["异常反馈"]
        connection.execute("UPDATE orders SET payload=?, updated_at=? WHERE order_id=?",
                           (json.dumps(order, ensure_ascii=False), beijing_now().isoformat(), order_id))


def find_order(order_id: str, include_saved: bool = False) -> dict[str, Any] | None:
    return next((item for item in init_orders(include_saved) if item.get("订单编号") == order_id), None)


def persist_order(order: dict[str, Any]) -> None:
    save_order_record(order)
    path_text = order.get("保存路径")
    if not path_text:
        return
    try:
        path = ROOT / str(path_text)
        frame = pd.read_excel(path)
        mask = frame["订单编号"].astype(str) == str(order["订单编号"])
        if mask.any():
            for key, value in order.items():
                if key not in {"状态序号", "保存路径", "保存状态"}:
                    frame.loc[mask, key] = _excel_value(value)
            frame.to_excel(path, index=False)
    except Exception:
        pass


def advance_order(order: dict[str, Any]) -> None:
    index = min(int(order.get("状态序号", 0)) + 1, len(STATUS_FLOW) - 1)
    order["状态序号"], order["状态"] = index, STATUS_FLOW[index]
    persist_order(order)


def set_order_status(order: dict[str, Any], status: str) -> None:
    if status not in STATUS_FLOW:
        raise ValueError(f"未知订单状态：{status}")
    order["状态"] = status
    order["状态序号"] = STATUS_FLOW.index(status)
    if status == "配送途中":
        if not order.get("车辆编号"):
            order["车辆编号"] = f"YL-冷链-{(sum(ord(c) for c in str(order.get('订单编号', ''))) % 8) + 1:02d}"
        order["发车时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    persist_order(order)
