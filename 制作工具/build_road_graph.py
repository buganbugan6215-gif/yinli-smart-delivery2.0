"""从竞赛货车路网提取云端可直接计算的压缩图；不包含客户信息。"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import geopandas as gpd

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
source = Path(args.source)
lines = gpd.read_file(source, layer="lines").to_crs(4326)
edges = []
for row in lines.itertuples(index=False):
    direction = str(row.oneway).strip().lower()
    if direction not in {"no", "yes", "-1"}:
        raise ValueError(f"未知道路方向: {direction}")
    edges.append([int(row.u), int(row.v), float(row.length_m), direction,
                  [[float(x), float(y)] for x, y, *_ in row.geometry.coords]])
payload = {"crs": "EPSG:4326", "unit": "m", "source": source.name,
           "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
           "attribution": "道路来源：竞赛整理路网 / © OpenStreetMap contributors，ODbL 1.0",
           "edges": edges}
target = Path(args.output)
target.parent.mkdir(parents=True, exist_ok=True)
with gzip.open(target, "wt", encoding="utf-8") as output:
    json.dump(payload, output, ensure_ascii=False, separators=(",", ":"))
print(f"{len(edges)} edges, {target.stat().st_size} bytes")
