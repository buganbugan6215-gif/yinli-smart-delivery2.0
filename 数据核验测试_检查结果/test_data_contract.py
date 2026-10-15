import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "网站数据_页面读取的指标"


def test_runtime_road_layers_exist_and_are_geojson():
    for name in ("road_major.geojson", "road_minor.geojson"):
        path = DATA / name
        assert path.is_file()
        layer = json.loads(path.read_text(encoding="utf-8"))
        assert layer["type"] == "FeatureCollection"
        assert layer["features"]


def test_no_absolute_local_paths_in_app_code():
    for path in [ROOT / "app.py", *sorted((ROOT / "pages").glob("*.py")), *sorted((ROOT / "功能组件_页面共用代码").glob("*.py"))]:
        text = path.read_text(encoding="utf-8")
        assert "D:\\A-university" not in text
