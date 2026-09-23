"""按北京时间自然日收单；23:59 所在分钟结束后切换下一配送批次。"""
from datetime import date, datetime, time, timedelta, timezone

BEIJING = timezone(timedelta(hours=8), name="Asia/Shanghai")


def beijing_now() -> datetime:
    return datetime.now(BEIJING)


def as_beijing(value: datetime | None = None) -> datetime:
    value = value or beijing_now()
    return value.replace(tzinfo=BEIJING) if value.tzinfo is None else value.astimezone(BEIJING)


def delivery_day(value: datetime | None = None) -> date:
    return as_beijing(value).date() + timedelta(days=1)


def batch_closed(day: str | date, value: datetime | None = None) -> bool:
    day = date.fromisoformat(str(day))
    return as_beijing(value) >= datetime.combine(day, time.min, tzinfo=BEIJING)


def cutoff_label(day: str | date) -> str:
    day = date.fromisoformat(str(day))
    return f"{day - timedelta(days=1):%Y-%m-%d} 23:59（北京时间，含该分钟）"
