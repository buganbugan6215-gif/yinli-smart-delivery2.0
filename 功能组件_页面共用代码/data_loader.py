from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "网站数据_页面读取的指标"


@dataclass
class SiteData:
    summary: dict[str, Any] = field(default_factory=dict)
    routes: dict[str, pd.DataFrame] = field(default_factory=dict)
    arrivals: dict[str, pd.DataFrame] = field(default_factory=dict)
    customers: pd.DataFrame = field(default_factory=pd.DataFrame)
    reuse_schedule: pd.DataFrame = field(default_factory=pd.DataFrame)
    sensitivity: pd.DataFrame = field(default_factory=pd.DataFrame)
    history: dict[str, Any] = field(default_factory=dict)
    geojson: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _json(name: str, errors: list[str]) -> dict[str, Any]:
    path = DATA_DIR / name
    if not path.exists():
        errors.append(f"缺少数据文件：{name}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"无法读取 {name}：{exc}")
        return {}


def _csv(name: str, errors: list[str]) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        errors.append(f"缺少数据文件：{name}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception as exc:
        errors.append(f"无法读取 {name}：{exc}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_site_data() -> SiteData:
    errors: list[str] = []
    summary = _json("summaries.json", errors)
    history = _json("algorithm_history.json", errors)
    manifest = _json("manifest.json", errors)
    geojson = {
        "routes": _json("route_features.geojson", errors),
        "customers": _json("customer_points.geojson", errors),
    }
    routes = {
        "noodle": _csv("routes_noodle.csv", errors),
        "ginger": _csv("routes_ginger.csv", errors),
    }
    arrivals = {
        "noodle": _csv("arrivals_noodle.csv", errors),
        "ginger": _csv("arrivals_ginger.csv", errors),
    }
    return SiteData(
        summary=summary,
        routes=routes,
        arrivals=arrivals,
        customers=_csv("customers.csv", errors),
        reuse_schedule=_csv("reuse_schedule.csv", errors),
        sensitivity=_csv("sensitivity.csv", errors),
        history=history,
        geojson=geojson,
        manifest=manifest,
        errors=errors,
    )


def get_summary(data: SiteData, key: str) -> dict[str, Any]:
    return data.summary.get(key, {}) or {}


def safe_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing = [column for column in columns if column in frame.columns]
    return frame[existing].copy()
