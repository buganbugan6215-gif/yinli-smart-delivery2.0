"""仅接入第二版正式结果的原仓与 D5，不导入候选池或历史客户。"""
import json
from pathlib import Path

RELEASE_VERSION = "2026-10-10-dual-depot-v16"
CONFIG = Path(__file__).resolve().parents[1] / "路网数据" / "仓配参数.json"


def config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def depots(count=1):
    if count not in (1, 2):
        raise ValueError("仓库数量只能选择单仓或双仓。")
    return config()["仓库"][:count]


def selection(day):
    from 功能组件_页面共用代码.order_state import _db_connection
    with _db_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS warehouse_selection (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        row = conn.execute("SELECT count FROM warehouse_selection WHERE day=?", (str(day),)).fetchone()
    return int(row[0]) if row else 1


def save_selection(day, count):
    depots(count)
    from 功能组件_页面共用代码.batch_dispatch import _tables
    from 功能组件_页面共用代码.order_state import _db_connection
    with _db_connection() as conn:
        _tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM delivery_batches WHERE delivery_day=?", (str(day),)).fetchone():
            raise ValueError("该批次已确认，仓库模式随已发布方案锁定。")
        conn.execute("CREATE TABLE IF NOT EXISTS warehouse_selection (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")
        conn.execute("INSERT OR REPLACE INTO warehouse_selection VALUES (?, ?)", (str(day), count))


def snapshot(count):
    return {"仓库": depots(count), "规则": config()["规则"]}


def current(plan):
    from 功能组件_页面共用代码.batch_solver import load_graph
    count = selection(plan["配送日期"])
    return (plan.get("仓库数量", 1) == count and plan.get("仓配配置") == snapshot(count)
            and plan.get("路网指纹") == load_graph()[-1])


def label(count):
    return "单仓 · 原配送中心" if count == 1 else "双仓 · 原仓＋新增配送点"
