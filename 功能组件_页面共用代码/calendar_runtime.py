"""使 Streamlit 热更新后的页面与已加载的订单服务使用同一版收单规则。"""
import importlib
import sys
import threading

_LOCK = threading.RLock()
_VERSION = "2026-09-23-20h-v2"
_PACKAGE = "功能组件_页面共用代码"


def ensure_current_calendar():
    # 页面脚本更新时，旧进程可能仍保留模块及 from-import 的函数引用。
    # 仅刷新无状态日期模块，保留订单数据库、会话和订单服务的其他状态。
    with _LOCK:
        calendar = importlib.import_module(f"{_PACKAGE}.delivery_calendar")
        if getattr(calendar, "POLICY_VERSION", None) != _VERSION:
            calendar = importlib.reload(calendar)
        for module_name, names in {
            "order_state": ("beijing_now", "delivery_day"),
            "batch_dispatch": ("beijing_now", "batch_closed"),
            "gps_simulator": ("as_beijing",),
        }.items():
            module = sys.modules.get(f"{_PACKAGE}.{module_name}")
            if module is not None:
                for name in names:
                    setattr(module, name, getattr(calendar, name))
        return calendar
