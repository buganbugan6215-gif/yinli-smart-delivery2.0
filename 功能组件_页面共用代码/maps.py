from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import folium
from branca.element import MacroElement, Template
from functools import lru_cache
from html import escape

RELEASE_VERSION = "2026-10-15-smooth-stops-v39"


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "网站数据_页面读取的指标"
DEPOT = [30.851137170192068, 104.26104981303031]


class ResponsiveFitBounds(MacroElement):
    """地图容器完成布局后重新按路线范围定位。"""

    _template = Template("""
    {% macro script(this, kwargs) %}
    (function () {
      const map = {{ this._parent.get_name() }};
      const bounds = {{ this.bounds_json }};
      const fit = function () {
        const container = map.getContainer();
        if (container.clientWidth < 100 || container.clientHeight < 100) return;
        map.invalidateSize({pan: false});
        map.fitBounds(bounds, {padding: [20, 20], maxZoom: 14, animate: false});
      };
      new ResizeObserver(fit).observe(map.getContainer());
      requestAnimationFrame(fit);
      setTimeout(fit, 300);
      setTimeout(fit, 1200);
    })();
    {% endmacro %}
    """)

    def __init__(self, bounds: list[list[float]]) -> None:
        super().__init__()
        self.bounds_json = json.dumps(bounds)


class AnimatedVehicle(MacroElement):
    """按行驶时间轴连续移动 Leaflet 标记，地图缩放时位置仍落在道路线上。"""

    _template = Template("""
    {% macro script(this, kwargs) %}
    (function () {
      const map = {{ this._parent.get_name() }};
      const marker = {{ this.marker_name }};
      const path = {{ this.timeline_json }};
      const started = {{ this.started_ms }};
      const factor = {{ this.factor }};
      const demo = {{ this.demo_json }};
      let lastDrawn = 0;
      let running = false;
      function position() {
        const now = Date.now();
        if (now - lastDrawn < 32) { requestAnimationFrame(position); return; }
        lastDrawn = now;
        const elapsed = demo && map._yinliPlayback
          ? map._yinliPlayback.elapsed(now)
          : Math.max(0, (now - started) / 1000 * factor);
        let low = 0, high = path.length - 1;
        while (low < high) {
          const mid = Math.floor((low + high) / 2);
          if (path[mid][2] < elapsed) low = mid + 1;
          else high = mid;
        }
        const next = Math.max(1, low);
        const before = path[next - 1], after = path[next];
        const span = after[2] - before[2];
        const ratio = span <= 0 ? 1 : Math.max(0, Math.min(1, (elapsed - before[2]) / span));
        marker.setLatLng([before[0] + (after[0] - before[0]) * ratio,
                          before[1] + (after[1] - before[1]) * ratio]);
        if (elapsed < path[path.length - 1][2]) requestAnimationFrame(position);
        else running = false;
      }
      function play() { if (!running) { running = true; requestAnimationFrame(position); } }
      if (demo) map.on('yinli:replay', play);
      play();
    })();
    {% endmacro %}
    """)

    def __init__(self, marker: folium.Marker, timeline: list[list[float]], started_ms: int, factor: int, demo: bool = False) -> None:
        super().__init__()
        self.marker_name = marker.get_name()
        self.timeline_json = json.dumps(timeline)
        self.started_ms = started_ms
        self.factor = factor
        self.demo_json = json.dumps(demo)


class PlaybackControl(MacroElement):
    """浏览器内调速，改变倍率时保留已走过的道路时间。"""

    _template = Template("""
    {% macro script(this, kwargs) %}
    (function () {
      const map = {{ this._parent.get_name() }};
      let factor = 10, anchor = Date.now();
      let elapsedAtAnchor = 0;
      map._yinliPlayback = {
        elapsed(now) { return Math.max(0, elapsedAtAnchor + (now - anchor) / 1000 * factor); },
        setFactor(value) {
          const now = Date.now();
          elapsedAtAnchor = this.elapsed(now);
          anchor = now;
          factor = value;
        },
        replay() { elapsedAtAnchor = 0; anchor = Date.now(); map.fire('yinli:replay'); }
      };
      const panel = document.createElement('div');
      panel.className = 'yinli-playback';
      panel.innerHTML = '<label for="yinli-speed">演示行驶倍率 <strong>10.0×</strong></label>' +
        '<input id="yinli-speed" type="range" min="1" max="20" step="0.1" value="10" aria-label="演示行驶倍率">' +
        '<button type="button">从起点重播</button>';
      Object.assign(panel.style, {position:'absolute', top:'12px', left:'58px', right:'50px', zIndex:'1000',
        display:'flex', alignItems:'center', gap:'12px', padding:'9px 14px', borderRadius:'10px',
        background:'rgba(239,244,252,.96)', color:'#1d2a3a', boxShadow:'0 2px 12px #23385130'});
      const input = panel.querySelector('input');
      input.style.flex = '1';
      panel.querySelector('button').style.cssText = 'border:1px solid #a9b9d2;border-radius:7px;padding:5px 10px;background:#fff;color:#123579;cursor:pointer';
      const label = panel.querySelector('strong');
      input.addEventListener('input', () => {
        map._yinliPlayback.setFactor(Number(input.value));
        label.textContent = Number(input.value).toFixed(1) + '×';
      });
      panel.querySelector('button').addEventListener('click', () => map._yinliPlayback.replay());
      L.DomEvent.disableClickPropagation(panel);
      L.DomEvent.disableScrollPropagation(panel);
      map.getContainer().appendChild(panel);
    })();
    {% endmacro %}
    """)

    def __init__(self) -> None:
        super().__init__()


@lru_cache(maxsize=4)
def load_geojson(name: str) -> dict[str, Any]:
    path = DATA_DIR / name
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


def nearby_roads(name: str, road_bounds=None) -> dict[str, Any]:
    """只发送线路附近的离线道路，避免把全域路网塞进地图组件。"""
    source = load_geojson(name)
    if road_bounds is None:
        return source
    west, south, east, north = road_bounds
    margin = .025
    west, south, east, north = west-margin, south-margin, east+margin, north+margin
    features = []
    for feature in source.get("features", []):
        if feature.get("geometry", {}).get("type") != "MultiLineString":
            features.append(feature)
            continue
        lines = [line for line in feature["geometry"]["coordinates"]
                 if line and not (max(p[0] for p in line) < west or min(p[0] for p in line) > east
                                  or max(p[1] for p in line) < south or min(p[1] for p in line) > north)]
        if lines:
            features.append({"type": "Feature", "properties": feature.get("properties", {}),
                             "geometry": {"type": "MultiLineString", "coordinates": lines}})
    return {"type": "FeatureCollection", "features": features}


def create_chengdu_map(zoom_start: int = 10, warehouses=None, road_bounds=None, detailed=False) -> tuple[folium.Map, folium.GeoJson | None]:
    fmap = folium.Map(location=DEPOT, zoom_start=zoom_start, zoom_snap=0.25,
                      tiles=None, control_scale=True, prefer_canvas=True)
    fmap.get_root().header.add_child(folium.Element("""<style>
    .leaflet-container { background:#e1e9f5; }
    .leaflet-popup-content-wrapper,.leaflet-popup-tip,.leaflet-tooltip,
    .leaflet-control-layers,.leaflet-bar a,.leaflet-control-attribution { background:#e7edf7; color:#1d2a3a; }
    .leaflet-bar a:hover { background:#dbe5f5; }
    </style>"""))
    # 只绘制随项目交付的道路 GeoJSON，断网时地图仍可运行。

    major_data = nearby_roads("road_major.geojson", road_bounds)
    if major_data.get("features"):
        folium.GeoJson(
            major_data,
            name="主干道路",
            style_function=lambda _: {"color": "#6f8190", "weight": 1.7, "opacity": 0.58},
            smooth_factor=1.5,
            show=True,
        ).add_to(fmap)

    minor_layer = None
    minor_data = nearby_roads("road_minor.geojson", road_bounds) if detailed else None
    if minor_data and minor_data.get("features"):
        minor_layer = folium.GeoJson(
            minor_data,
            name="细支道路（放大显示）",
            style_function=lambda _: {"color": "#aeb9c0", "weight": 0.85, "opacity": 0.48},
            smooth_factor=2,
            show=False,
        ).add_to(fmap)

    from 功能组件_页面共用代码.warehouses import depots
    for depot in warehouses if warehouses is not None else depots(1):
        lon, lat = depot["坐标"]
        folium.Marker([lat, lon], tooltip=depot["名称"],
                      icon=folium.Icon(color="darkblue" if depot["编号"] == "D0" else "blue", icon="home")).add_to(fmap)
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


def plan_map(plan, detailed=False):
    from 功能组件_页面共用代码.live_operations import PRODUCT_COLORS
    bounds = [[p[1], p[0]] for route in plan["线路"]
              for feature in route["路线GeoJSON"]["features"]
              for p in feature["geometry"]["coordinates"]]
    road_bounds = (min(p[1] for p in bounds), min(p[0] for p in bounds),
                   max(p[1] for p in bounds), max(p[0] for p in bounds)) if bounds else None
    fmap, minor = create_chengdu_map(warehouses=plan.get("仓库"), road_bounds=road_bounds, detailed=detailed)
    for route in plan["线路"]:
        product = route.get("品类", "鲜面条")
        color = PRODUCT_COLORS[product]
        style = {"color": color, "weight": 4, "opacity": .9, "dashArray": "8 8" if product == "姜蒜" else None}
        folium.GeoJson(route["路线GeoJSON"], name=route["线路编号"], style_function=lambda _, s=style: s,
                       tooltip=escape(f"{route['线路编号']} · {route.get('出发仓库', '原配送中心')} · {route['车辆编号']}")).add_to(fmap)
    for transfer in plan.get("补货", []):
        folium.GeoJson(transfer["路线GeoJSON"], name=f"{transfer['品类']}仓间补货",
                       style_function=lambda _: {"color": "#526c95", "weight": 3, "dashArray": "5 9", "opacity": .7},
                       tooltip=f"{transfer['品类']}补货 · {transfer['补货车数']}车").add_to(fmap)
    for assignment in plan["订单结果"]:
        coords = assignment["路线GeoJSON"]["features"][0]["geometry"]["coordinates"][-1]
        folium.CircleMarker([coords[1], coords[0]], radius=4, color="#244775", fill=True,
                            tooltip=escape(f"{assignment['订单编号']} · 第{assignment['配送顺序']}站")).add_to(fmap)
    if bounds:
        fmap.fit_bounds(bounds, padding=(28, 28), max_zoom=13)
    add_zoom_detail_behavior(fmap, minor, threshold=13)
    folium.LayerControl(collapsed=True).add_to(fmap)
    return fmap
