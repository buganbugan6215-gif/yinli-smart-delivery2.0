"""共享事务存储：本地 SQLite 或外部 PostgreSQL；连接失败不降级写本地。"""
import os
import re
import sqlite3
import sys
import streamlit as st

RELEASE_VERSION = "2026-10-15-route-eta-v28"


def database_url():
    if os.getenv("YL_DATABASE_URL"):
        return os.environ["YL_DATABASE_URL"]
    try:
        return st.secrets.get("YL_DATABASE_URL")
    except (FileNotFoundError, RuntimeError):
        return None


class LocalConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def postgres_sql(sql):
    sql = sql.replace("?", "%s")
    if sql.startswith("INSERT OR IGNORE INTO"):
        return sql.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1) + " ON CONFLICT DO NOTHING"
    if sql.startswith("INSERT OR REPLACE INTO"):
        table = re.search(r"INTO (\w+)", sql)[1]
        columns = {"delivery_drafts": ("delivery_day", "payload"),
                   "warehouse_selection": ("day", "count"),
                   "app_settings": ("name", "payload")}
        key, value = columns[table]
        return sql.replace("INSERT OR REPLACE INTO", "INSERT INTO", 1) + f" ON CONFLICT ({key}) DO UPDATE SET {value}=excluded.{value}"
    return sql


class CloudConnection:
    def __init__(self, url):
        try:
            self._lease = _cloud_pool(url).connection()
            self.conn = self._lease.__enter__()
            # 所有业务事务遵守同一把锁，保护拆单、确认及客户反馈的原子更新。
            self.conn.execute("SET LOCAL lock_timeout = '15s'")
            self.conn.execute("SET LOCAL statement_timeout = '30s'")
            self.conn.execute("SELECT pg_advisory_xact_lock(731902617)")
            self.conn.execute("CREATE SCHEMA IF NOT EXISTS yinli_private")
            self.conn.execute("SET LOCAL search_path TO yinli_private")
        except Exception:
            if hasattr(self, "conn"):
                self._lease.__exit__(*sys.exc_info())
            raise RuntimeError("云端订单库连接失败，请检查数据库状态及 Secrets；本次未切换到本地存储。") from None

    def execute(self, sql, params=()):
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            return self.conn.execute("SELECT 1")
        try:
            return self.conn.execute(postgres_sql(sql), params)
        except Exception:
            raise RuntimeError("云端订单库操作失败，本次事务将回滚；请检查数据库权限和连接。") from None

    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        try:
            self._lease.__exit__(kind, value, tb)
        except Exception:
            raise RuntimeError("云端事务未能完成，请重新查询订单确认保存结果。") from None


@st.cache_resource(show_spinner=False)
def _cloud_pool(url):
    from psycopg_pool import ConnectionPool
    return ConnectionPool(conninfo=url, kwargs={"connect_timeout": 10, "sslmode": "require", "prepare_threshold": None},
                          min_size=0, max_size=4, timeout=10, open=True)


def connect(path):
    url = database_url()
    if url:
        connection = CloudConnection(url)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=15, factory=LocalConnection)
        connection.execute("PRAGMA journal_mode=WAL")
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL)")
    except Exception:
        connection.__exit__(*sys.exc_info())
        raise
    return connection
