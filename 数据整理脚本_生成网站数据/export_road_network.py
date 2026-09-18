from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box, mapping
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "7.0-修复孤立客户拓扑节点.gpkg"
OUTPUT = ROOT / "网站数据_页面读取的指标"


def rounded_coordinates(value):
    if isinstance(value, (list, tuple)):
        if value and isinstance(value[0], (float, int)):
            return [round(float(item), 6) for item in value]
        return [rounded_coordinates(item) for item in value]
    return value


def feature_collection(frame: gpd.GeoDataFrame) -> dict:
    features = []
    for highway, group in frame.groupby("highway", dropna=False):
        merged = unary_union(group.geometry.tolist())
        geometry = mapping(merged)
        geometry["coordinates"] = rounded_coordinates(geometry["coordinates"])
        features.append({
            "type": "Feature",
            "properties": {"road_class": str(highway or "other")},
            "geometry": geometry,
        })
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    customer_layers = [
        gpd.read_file(SOURCE, layer="面条客户点", engine="pyogrio"),
        gpd.read_file(SOURCE, layer="姜蒜客户点", engine="pyogrio"),
        gpd.read_file(SOURCE, layer="配送中心", engine="pyogrio"),
    ]
    all_points = gpd.GeoDataFrame(
        geometry=pd.concat([item.geometry for item in customer_layers], ignore_index=True),
        crs="EPSG:4326",
    )
    minx, miny, maxx, maxy = all_points.total_bounds
    clip_box = box(minx - 0.035, miny - 0.035, maxx + 0.035, maxy + 0.035)

    roads = gpd.read_file(SOURCE, layer="lines", engine="pyogrio", columns=["highway", "name", "geometry"])
    roads = roads[roads.geometry.intersects(clip_box)].copy()
    roads["highway"] = roads["highway"].fillna("other").astype(str)

    major_names = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link"}
    minor_names = {"secondary", "secondary_link", "tertiary", "tertiary_link"}
    major = roads[roads["highway"].isin(major_names)].copy()
    minor = roads[
        roads["highway"].isin(minor_names)
        & (roads["name"].notna() | roads["highway"].isin({"tertiary", "tertiary_link", "unclassified"}))
    ].copy()
    major.geometry = major.geometry.simplify(0.00016, preserve_topology=True).normalize()
    minor.geometry = minor.geometry.simplify(0.00032, preserve_topology=True).normalize()
    major = major.loc[~major.geometry.to_wkb().duplicated()].copy()
    minor = minor.loc[~minor.geometry.to_wkb().duplicated()].copy()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "road_major.geojson").write_text(json.dumps(feature_collection(major), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUTPUT / "road_minor.geojson").write_text(json.dumps(feature_collection(minor), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"major={len(major)} minor={len(minor)}")


if __name__ == "__main__":
    main()
