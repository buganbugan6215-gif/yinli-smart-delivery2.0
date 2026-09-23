"""按北京时间收单；每天 20:00 起切换到再下一天的配送批次。"""
from datetime import date, datetime, time, timedelta, timezone

BEIJING = timezone(timedelta(hours=8), name="Asia/Shanghai")


def beijing_now() -> datetime:
    return datetime.now(BEIJING)


def as_beijing(value: datetime | None = None) -> datetime:
    value = value or beijing_now()
    return value.replace(tzinfo=BEIJING) if value.tzinfo is None else value.astimezone(BEIJING)


def delivery_day(value: datetime | None = None) -> date:
    current = as_beijing(value)
    days_ahead = 1 if current.time() < time(20, 0) else 2
    return current.date() + timedelta(days=days_ahead)


def batch_closed(day: str | date, value: datetime | None = None) -> bool:
    day = date.fromisoformat(str(day))
    cutoff_day = day - timedelta(days=1)
    return as_beijing(value) >= datetime.combine(cutoff_day, time(20, 0), tzinfo=BEIJING)


def cutoff_label(day: str | date) -> str:
    day = date.fromisoformat(str(day))
    return f"{day - timedelta(days=1):%Y-%m-%d} 20:00（北京时间；20:00 起停止接收该配送日订单）"
