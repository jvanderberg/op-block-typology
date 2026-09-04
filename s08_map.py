"""Stage 8: self-contained Leaflet map of block types.

The map shows the parcel-derived classification of every block (which is
public assessor data, not census data) and each block's housing-unit mix.
It deliberately shows no census population or race figures for individual
blocks; those are reported only as category totals in results.md.

Output: outputs/map.html (block polygons embedded as GeoJSON).
"""
import json
import os

from config import CATEGORIES, CATEGORY_COLORS, CATEGORY_LABELS, INTERIM_DIR, OUT_DIR, SF_ONLY_MIN_SHARE
from provenance import Stage

KEEP = ("block_geoid", "category", "units", "units_sf", "units_small_mf", "units_large_mf",
        "bldgs_sf", "bldgs_small_mf", "bldgs_large_mf", "n_parcels", "HOUSING20", "census_gap")

HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Oak Park block types</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 html,body{margin:0;height:100%;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#0b0b0b}
 #map{height:100%}
 .panel{background:#fcfcfb;padding:10px 12px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.25);font-size:13px;max-width:280px}
 .panel h1{font-size:15px;margin:0 0 6px}
 .panel p{margin:4px 0;color:#52514e}
 .sw{display:inline-block;width:14px;height:14px;border-radius:3px;vertical-align:-2px;margin-right:6px;border:1px solid rgba(0,0,0,.15)}
 .row{margin:3px 0}
 .leaflet-popup-content{font-size:13px} .leaflet-popup-content b{font-weight:600}
</style></head><body>
<div id="map"></div>
<script>
const COLORS = __COLORS__;
const LABELS = __LABELS__;
const COUNTS = __COUNTS__;
const data = __GEOJSON__;
const map = L.map('map', {preferCanvas:true}).setView([41.885, -87.79], 14);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
  {attribution:'&copy; OpenStreetMap contributors &copy; CARTO', maxZoom: 19}).addTo(map);
function style(f){ const c=f.properties.category; return {color:'#fcfcfb', weight:1, fillColor:COLORS[c], fillOpacity: c==='no_housing'?0.5:0.75}; }
function popup(p){
  const pct = (n)=> p.units>0 ? Math.round(100*n/p.units)+'%' : '-';
  return '<b>'+LABELS[p.category]+'</b><br>Block '+p.block_geoid+
    '<br>Housing units on parcels: '+Math.round(p.units)+' (2020 Census: '+p.HOUSING20+')'+
    '<br>Single-family: '+Math.round(p.units_sf)+' ('+pct(p.units_sf)+') in '+p.bldgs_sf+' buildings'+
    '<br>2-6 unit buildings: '+Math.round(p.units_small_mf)+' ('+pct(p.units_small_mf)+') in '+p.bldgs_small_mf+
    '<br>7+ unit buildings: '+Math.round(p.units_large_mf)+' ('+pct(p.units_large_mf)+') in '+p.bldgs_large_mf+
    (p.census_gap ? '<br><i>Census counts more units than the parcel data (likely tax-exempt housing).</i>' : '');
}
const layer = L.geoJSON(data, {style, onEachFeature:(f,l)=>{ l.bindPopup(popup(f.properties)); l.on('mouseover',()=>l.setStyle({weight:2,color:'#0b0b0b'})); l.on('mouseout',()=>layer.resetStyle(l)); }}).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png', {pane:'markerPane', maxZoom:19}).addTo(map);
const legend = L.control({position:'topright'});
legend.onAdd = function(){
  const d = L.DomUtil.create('div','panel');
  let h = '<h1>Oak Park blocks by housing type</h1><p>2020 Census blocks classified from Cook County Assessor 2026 parcel data. Single-family = at least __SFMIN__ of units are houses or townhomes; a building size "dominates" at 50% or more of units.</p>';
  for (const c of Object.keys(LABELS)) h += '<div class="row"><span class="sw" style="background:'+COLORS[c]+'"></span>'+LABELS[c]+' <span style="color:#52514e">('+COUNTS[c]+')</span></div>';
  h += '<p>Click a block for its unit mix. No census population figures are shown per block.</p>';
  d.innerHTML = h; return d; };
legend.addTo(map);
</script></body></html>
"""


def main():
    with Stage("s08_map", __file__) as st:
        src = os.path.join(INTERIM_DIR, "s05_blocks.geojson")
        st.input(src, role="block polygons with category")
        with open(src) as f:
            gj = json.load(f)
        feats = []
        counts = {c: 0 for c in CATEGORIES}
        for ft in gj["features"]:
            p = ft["properties"]
            counts[p["category"]] += 1
            props = {k: p[k] for k in KEEP}
            props["census_gap"] = bool(p["census_gap"])
            geom = ft["geometry"]
            # 6 decimals (~10 cm) keeps the file small without visible change.
            def rnd(coords):
                return [rnd(c) for c in coords] if isinstance(coords[0], list) else [round(coords[0], 6), round(coords[1], 6)]
            geom = {"type": geom["type"], "coordinates": rnd(geom["coordinates"])}
            feats.append({"type": "Feature", "properties": props, "geometry": geom})
        feats.sort(key=lambda f: f["properties"]["block_geoid"])
        labels = {c: CATEGORY_LABELS[c] for c in CATEGORIES}
        html = (HTML.replace("__COLORS__", json.dumps(CATEGORY_COLORS, sort_keys=True))
                    .replace("__LABELS__", json.dumps(labels))
                    .replace("__COUNTS__", json.dumps(counts))
                    .replace("__SFMIN__", f"{SF_ONLY_MIN_SHARE:.0%}")
                    .replace("__GEOJSON__", json.dumps({"type": "FeatureCollection", "features": feats},
                                                       separators=(",", ":"))))
        out = os.path.join(OUT_DIR, "map.html")
        with open(out, "w") as f:
            f.write(html)
        st.note(f"map: {len(feats)} blocks; counts {counts}")
        st.output(out, role="interactive block-type map")


if __name__ == "__main__":
    main()
