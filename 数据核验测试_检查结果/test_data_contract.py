import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "网站数据_页面读取的指标"


def test_required_files_exist():
    required = ["summaries.json", "customers.csv", "routes_noodle.csv", "routes_ginger.csv", "arrivals_noodle.csv", "arrivals_ginger.csv", "reuse_schedule.csv", "sensitivity.csv", "customer_points.geojson", "route_features.geojson"]
    assert all((DATA / name).exists() for name in required)


def test_summary_is_source_backed():
    summary = json.loads((DATA / "summaries.json").read_text(encoding="utf-8"))
    assert summary["noodle"]["vehicles_used"] == 6
    assert round(summary["noodle"]["total_distance_km"], 3) == 594.837
    assert round(summary["noodle"]["total_cost"], 3) == 3076.953
    assert summary["ginger"]["vehicles_used"] == 6
    assert round(summary["ginger"]["ontime_rate"], 3) == 0.767


def test_routes_cover_each_customer_once():
    for name in ["routes_noodle.csv", "routes_ginger.csv"]:
        frame = pd.read_csv(DATA / name, encoding="utf-8-sig")
        assert int(frame["客户数"].sum()) == 30
        assert frame["车辆编号"].notna().all()


def test_cost_closure():
    summary = json.loads((DATA / "summaries.json").read_text(encoding="utf-8"))
    for key in ["noodle", "ginger"]:
        s = summary[key]
        parts = sum(float(v) for v in s["cost_breakdown"].values() if v is not None)
        assert abs(parts - float(s["total_cost"])) < 1e-6


def test_no_absolute_local_paths_in_app_code():
    for path in [ROOT / "app.py", *sorted((ROOT / "pages").glob("*.py")), *sorted((ROOT / "功能组件_页面共用代码").glob("*.py"))]:
        text = path.read_text(encoding="utf-8")
        assert "D:\\A-university" not in text
