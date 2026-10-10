"""从第二版使用的 GPKG 同时生成计算路网与完整范围的轻量底图。"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    source = Path(args.source)
    root = Path(__file__).resolve().parents[1]
    frames = [gpd.read_file(source, layer=layer).to_crs(4326) for layer in ("主干道", "其他道路")]
    roads = pd.concat(frames, ignore_index=True)
    edges = []
    for row in roads.itertuples(index=False):
        if row.oneway not in ("no", "yes", "-1") or row.length_m <= 0:
            raise ValueError("路网方向或距离无效")
        edges.append([int(row.u), int(row.v), float(row.length_m), row.oneway,
                      [[float(x), float(y)] for x, y, *_ in row.geometry.coords]])
    meta = {"crs": "EPSG:4326", "unit": "m", "source": source.name,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "bounds": roads.total_bounds.tolist(), "edge_count": len(edges),
            "attribution": "道路来源：竞赛第二版整理路网 / © OpenStreetMap contributors，ODbL 1.0"}
    with gzip.open(root/"路网数据/chengdu_truck.json.gz", "wt", encoding="utf-8") as f:
        json.dump({**meta, "edges": edges}, f, ensure_ascii=False, separators=(",", ":"))
    (root/"路网数据/路网来源.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    for frame, name, tolerance in zip(frames, ("road_major.geojson", "road_minor.geojson"), (.00016, .00032)):
        # 只简化展示几何；上方计算图始终保留原始道路长度与几何。
        frame = frame.copy()
        if name == "road_minor.geojson":
            frame = frame[frame["highway"].isin({"secondary", "secondary_link", "tertiary", "tertiary_link"})].copy()
        frame.geometry = frame.geometry.simplify(tolerance).normalize()
        frame = frame.loc[~frame.geometry.to_wkb().duplicated()]
        geometry = [[[round(x, 6), round(y, 6)] for x, y, *_ in g.coords] for g in frame.geometry]
        data = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
                "geometry": {"type": "MultiLineString", "coordinates": geometry}}]}
        (root/"网站数据_页面读取的指标"/name).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=True))


if __name__ == "__main__":
    main()
