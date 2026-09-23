"""按北京时间收单；每天 20:00 起切换到再下一天的配送批次。"""
from datetime import date, datetime, time, timedelta, timezone

BEIJING = timezone(timedelta(hours=8), name="Asia/Shanghai")
POLICY_VERSION = "2026-09-23-20h-v2"
CUTOFF = time(20, 0)


def beijing_now() -> datetime:
    return datetime.now(BEIJING)


def as_beijing(value: datetime | None = None) -> datetime:
    value = value or beijing_now()
    return value.replace(tzinfo=BEIJING) if value.tzinfo is None else value.astimezone(BEIJING)


def delivery_day(value: datetime | None = None) -> date:
    current = as_beijing(value)
    days_ahead = 1 if current.time() < CUTOFF else 2
    return current.date() + timedelta(days=days_ahead)


def batch_closed(day: str | date, value: datetime | None = None) -> bool:
    day = date.fromisoformat(str(day))
    cutoff_day = day - timedelta(days=1)
    return as_beijing(value) >= datetime.combine(cutoff_day, CUTOFF, tzinfo=BEIJING)


def cutoff_label(day: str | date) -> str:
    day = date.fromisoformat(str(day))
    return f"{day - timedelta(days=1):%Y-%m-%d} {CUTOFF:%H:%M}（北京时间；{CUTOFF:%H:%M} 起停止接收该配送日订单）"
