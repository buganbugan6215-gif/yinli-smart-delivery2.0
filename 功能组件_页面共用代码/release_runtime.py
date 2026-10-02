"""热部署时使已驻留的业务模块与页面保持同一版本，不重建订单数据库。"""
import importlib
import json
from pathlib import Path
import threading

_LOCK = threading.RLock()
VERSION_FILE = Path(__file__).with_name("release_version.json")


def ensure_current_release():
    with _LOCK:
        version = json.loads(VERSION_FILE.read_text(encoding="utf-8"))["version"]
        for name in ("order_state", "batch_solver", "batch_dispatch", "ui"):
            module = importlib.import_module(f"功能组件_页面共用代码.{name}")
            if getattr(module, "RELEASE_VERSION", None) != version:
                importlib.reload(module)
