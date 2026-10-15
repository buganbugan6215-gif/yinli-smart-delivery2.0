"""完整业务备份：包含订单、线路、草案、仓库选择和计价设置。"""
import json
from datetime import timedelta
from 功能组件_页面共用代码 import order_state as state
from 功能组件_页面共用代码.delivery_calendar import beijing_now

RELEASE_VERSION = "2026-10-15-vehicle-motion-v35"
TABLES = {"orders": ("order_id", "updated_at", "payload"),
          "delivery_batches": ("delivery_day", "payload"),
          "delivery_drafts": ("delivery_day", "payload"),
          "warehouse_selection": ("day", "count"),
          "app_settings": ("name", "payload")}


def tables(conn):
    from 功能组件_页面共用代码.batch_dispatch import _tables
    _tables(conn)
    conn.execute("CREATE TABLE IF NOT EXISTS warehouse_selection (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (name TEXT PRIMARY KEY, payload TEXT NOT NULL)")


def recent_orders(orders, now=None):
    today = (now or beijing_now()).date()
    lower = (today-timedelta(days=29)).isoformat()
    upper = today.isoformat()
    return [o for o in orders if lower <= str(o.get("提交时间", ""))[:10] <= upper
            or lower <= str(o.get("期望送达日期", "")) <= upper]


def export_backup():
    if not state.st.session_state.get("staff_authenticated"):
        raise ValueError("需要工作人员权限。")
    rates = state.pricing_settings()
    with state._db_connection() as conn:
        tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        data = {name: [list(row) for row in conn.execute(f"SELECT {','.join(cols)} FROM {name}").fetchall()] for name, cols in TABLES.items()}
    if not any(r[0] == "pricing" for r in data["app_settings"]):
        data["app_settings"].append(["pricing", json.dumps({**rates, "仓配成本版本":"第二版20261010", "速度规则版本":"2026-10-03-60-30"}, ensure_ascii=False)])
    return json.dumps({"格式":"银犁订单完整备份1", "导出时间":beijing_now().isoformat(), "表":data}, ensure_ascii=False).encode("utf-8")


def restore_backup(raw):
    if not state.st.session_state.get("staff_authenticated"):
        raise ValueError("需要工作人员权限。")
    if len(raw) > 100*1024*1024:
        raise ValueError("备份超过 100 MB，请联系管理员迁移。")
    try:
        backup = json.loads(raw)
        assert backup["格式"] == "银犁订单完整备份1"
        data = backup["表"]
        assert set(data) == set(TABLES)
        for name, cols in TABLES.items():
            assert isinstance(data[name], list)
            keys = set()
            for row in data[name]:
                assert isinstance(row, list) and len(row) == len(cols) and isinstance(row[0], str) and row[0] not in keys
                keys.add(row[0])
                if "payload" in cols:
                    payload = json.loads(row[-1])
                    assert isinstance(payload, dict)
                    if name == "orders":
                        assert payload["订单编号"] == row[0]
                        assert payload["状态"] in state.STATUS_FLOW or payload["状态"] == state.CANCELLED_STATUS
        order_ids = {r[0] for r in data["orders"]}
        for name in ("delivery_batches", "delivery_drafts"):
            for row in data[name]:
                payload = json.loads(row[1])
                assert payload["配送日期"] == row[0]
                assert all(a["订单编号"] in order_ids for a in payload["订单结果"])
    except (AssertionError, KeyError, TypeError, ValueError):
        raise ValueError("备份格式或关联记录不完整，未导入任何数据。") from None
    with state._db_connection() as conn:
        tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        if any(conn.execute(f"SELECT 1 FROM {name} LIMIT 1").fetchone() for name in TABLES):
            raise ValueError("当前数据库已有业务记录，请使用空数据库迁移，避免覆盖新订单或破坏线路。")
        for name, cols in TABLES.items():
            for row in data[name]:
                conn.execute(f"INSERT INTO {name} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", tuple(row))
    return len(data["orders"])
