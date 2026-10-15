"""热部署时使已驻留的业务模块与页面保持同一版本，不重建订单数据库。"""
import importlib
import json
from pathlib import Path
import sys
import threading

_LOCK = threading.RLock()
VERSION_FILE = Path(__file__).with_name("release_version.json")


def ensure_current_release():
    with _LOCK:
        version = json.loads(VERSION_FILE.read_text(encoding="utf-8"))["version"]
        for name in ("storage", "warehouses", "order_state", "warehouse_routing", "batch_solver", "arrival_estimate", "batch_dispatch", "live_operations", "maps", "warehouse_ui", "gps_simulator", "customer_dialogue", "order_archive", "ui"):
            # 新进程中的模块交给正常 import；只刷新已完整加载的旧模块。
            # 主动导入全部业务模块会拖慢首屏，并在并发会话启动时撞上半初始化模块。
            module = sys.modules.get(f"功能组件_页面共用代码.{name}")
            if module is not None and not getattr(module.__spec__, "_initializing", False) and getattr(module, "RELEASE_VERSION", None) != version:
                importlib.reload(module)
