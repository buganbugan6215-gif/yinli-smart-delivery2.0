from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import folium


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "网站数据_页面读取的指标"
DEPOT = [30.851137170192068, 104.26104981303031]


def load_geojson(name: str) -> dict[str, Any]:
    path = DATA_DIR / name
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


def create_chengdu_map(zoom_start: int = 10) -> tuple[folium.Map, folium.GeoJson | None]:
    fmap = folium.Map(location=DEPOT, zoom_start=zoom_start, tiles=None, control_scale=True, prefer_canvas=True)
    # 只绘制随项目交付的道路 GeoJSON，断网时地图仍可运行。

    major_data = load_geojson("road_major.geojson")
    minor_data = load_geojson("road_minor.geojson")
    if major_data.get("features"):
        folium.GeoJson(
            major_data,
            name="主干道路",
            style_function=lambda _: {"color": "#6f8190", "weight": 1.7, "opacity": 0.58},
            smooth_factor=1.5,
            show=True,
        ).add_to(fmap)

    minor_layer = None
    if minor_data.get("features"):
        minor_layer = folium.GeoJson(
            minor_data,
            name="细支道路（放大显示）",
            style_function=lambda _: {"color": "#aeb9c0", "weight": 0.85, "opacity": 0.48},
            smooth_factor=2,
            show=False,
        ).add_to(fmap)

    folium.Marker(
        DEPOT,
        tooltip="银犁配送中心",
        icon=folium.Icon(color="darkgreen", icon="home"),
    ).add_to(fmap)
    return fmap, minor_layer


def add_zoom_detail_behavior(fmap: folium.Map, minor_layer: folium.GeoJson | None, threshold: int = 13) -> None:
    if minor_layer is None:
        return
    map_name = fmap.get_name()
    minor_name = minor_layer.get_name()
    script = f"""
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
      const map = {map_name};
      const minor = {minor_name};
      const syncRoadDetail = function() {{
        if (map.getZoom() >= {threshold}) {{
          if (!map.hasLayer(minor)) minor.addTo(map);
        }} else if (map.hasLayer(minor)) {{
          map.removeLayer(minor);
        }}
      }};
      map.on('zoomend', syncRoadDetail);
      syncRoadDetail();
    }});
    </script>
    """
    fmap.get_root().html.add_child(folium.Element(script))


def add_route_features(fmap: folium.Map, geojson: dict[str, Any], product_code: str | None = None) -> None:
    colors = {"N": "#1750df", "G": "#ff8133"}
    labels = {"N": "鲜面专线", "G": "姜蒜专线"}
    groups: dict[str, folium.FeatureGroup] = {}
    for code in ("N", "G"):
        groups[code] = folium.FeatureGroup(name=labels[code], show=product_code in (None, code))
        groups[code].add_to(fmap)
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        code = str(props.get("product_code", "N"))
        if product_code and code != product_code:
            continue
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])
        if geometry.get("type") != "LineString" or not coords or code not in groups:
            continue
        folium.PolyLine(
            [[point[1], point[0]] for point in coords],
            color=colors[code],
            weight=4,
            opacity=0.86,
            tooltip=props.get("label", labels[code]),
        ).add_to(groups[code])


def add_customer_points(fmap: folium.Map, geojson: dict[str, Any], product_code: str | None = None) -> None:
    colors = {"N": "#1750df", "G": "#ff8133"}
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        code = str(props.get("product_code", "N"))
        if product_code and code != product_code:
            continue
        coords = feature.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        popup = "<b>{}</b><br>品类：{}<br>配送量：{} kg<br>时间要求：{}".format(
            props.get("label", "客户"), props.get("product", "暂无"), props.get("demand_kg", "暂无"), props.get("time_window", "暂无")
        )
        folium.CircleMarker(
            [coords[1], coords[0]], radius=4.5, color=colors.get(code, "#1750df"),
            fill=True, fill_opacity=0.88, popup=popup, tooltip=props.get("label", "客户")
        ).add_to(fmap)
