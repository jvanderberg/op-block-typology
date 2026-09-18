"""Stage 2: fetch every upstream file the pipeline needs, and record it.

Each download is written verbatim to data/raw/ and registered with its URL,
byte size and sha256. A file that already exists is not re-downloaded (delete
it to force a refresh); its hash is still recorded so a re-run documents
exactly which snapshot was used. Live services (ArcGIS, Socrata, Census
Reporter) can change between runs, which is why the snapshot is what gets
committed and hashed, not the URL alone.

Downloads:
  1. Cook County parcel polygons for municipality = Oak Park (ArcGIS, paged),
     plus a supplemental query for any 10-digit PIN in s01 that the
     municipality query missed.
  2. Assessor Commercial Valuation rows for Oak Park township (unit counts
     for class 3 apartment buildings).
  3. TIGER/Line 2020 blocks, block groups and places for Illinois.
  4. 2020 P.L. 94-171 summary file for Illinois.
  5. ACS 5-year block-group race table via Census Reporter.
  6. Village of Oak Park historic district polygons (ArcGIS layer 13).
  7. Assessor Condominium Unit Characteristics for Oak Park (year built
     per condo building).
  8. Village of Oak Park zoning district polygons (ArcGIS layer 8).
"""
import json
import os
import time
import zipfile

import pandas as pd
import requests

from config import (ACS_GEO_QUERY, HTTP_USER_AGENT, SOCRATA_CONDO_URL, SOCRATA_CONDO_YEAR,
                    VOP_HISTORIC_DISTRICTS_URL, VOP_ZONING_FIELDS, VOP_ZONING_URL, ACS_TABLES, ARCGIS_FIELDS, ARCGIS_MUNICIPALITY,
                    ARCGIS_PAGE, ARCGIS_PARCELS_URL, CENSUSREPORTER_URL, HTTP_RETRIES,
                    HTTP_TIMEOUT, INTERIM_DIR, PL_URL, RAW_DIR, SOCRATA_COMMVAL_TOWNSHIP,
                    SOCRATA_COMMVAL_URL, TIGER_BG_URL, TIGER_BLOCKS_URL, TIGER_PLACE_URL)
from provenance import Stage


def get(url, params=None, stream=False):
    last = None
    for attempt in range(HTTP_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=HTTP_TIMEOUT, stream=stream,
                             headers={"User-Agent": HTTP_USER_AGENT})
            r.raise_for_status()
            return r
        except requests.RequestException as e:  # noqa: PERF203
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed after {HTTP_RETRIES} attempts: {url}: {last}")


def download(st, url, dest, role):
    if os.path.exists(dest):
        st.note(f"exists, not re-downloaded: {dest}")
    else:
        st.note(f"GET {url}")
        with get(url, stream=True) as r, open(dest, "wb") as f:
            for chunk in r.iter_content(8 * 1024 * 1024):
                f.write(chunk)
    st.output(dest, role=role, extra={"url": url})
    return dest


def unzip(st, path, dest_dir):
    """Extract every member and register each as an output of this stage, so
    later stages that read a member (shapefile, PL segment) trace to the zip."""
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        names = sorted(z.namelist())
        z.extractall(dest_dir)
    st.note(f"unzipped {os.path.basename(path)} -> {dest_dir}: {names}")
    for n in names:
        st.output(os.path.join(dest_dir, n), role=f"member of {os.path.basename(path)}",
                  extra={"from_zip": os.path.basename(path)})


def fetch_arcgis_parcels(st, pins10_needed):
    dest = os.path.join(RAW_DIR, "arcgis_parcels_oak_park.geojson")
    if os.path.exists(dest):
        st.note(f"exists, not re-downloaded: {dest}")
        st.output(dest, role="Cook County parcel polygons (ArcGIS snapshot)",
                  extra={"url": ARCGIS_PARCELS_URL})
        return dest
    feats = []
    offset = 0
    while True:
        r = get(ARCGIS_PARCELS_URL, params={
            "where": f"municipality='{ARCGIS_MUNICIPALITY}'",
            "outFields": ARCGIS_FIELDS, "outSR": 4326, "f": "geojson",
            "orderByFields": "objectid", "resultOffset": offset,
            "resultRecordCount": ARCGIS_PAGE})
        page = r.json()
        if "error" in page:
            raise RuntimeError(page["error"])
        got = page.get("features", [])
        feats.extend(got)
        st.note(f"arcgis page offset={offset} features={len(got)}")
        if len(got) < ARCGIS_PAGE:
            break
        offset += ARCGIS_PAGE
    st.note(f"arcgis municipality='{ARCGIS_MUNICIPALITY}': {len(feats)} features")
    have10 = {f["properties"].get("pin10") for f in feats}
    missing = sorted(p for p in pins10_needed if p not in have10)
    st.note(f"10-digit PINs in s01 not returned by the municipality query: {len(missing)}")
    extra = 0
    for i in range(0, len(missing), 200):
        chunk = missing[i:i + 200]
        where = "pin10 IN (" + ",".join(f"'{p}'" for p in chunk) + ")"
        r = get(ARCGIS_PARCELS_URL, params={
            "where": where, "outFields": ARCGIS_FIELDS, "outSR": 4326,
            "f": "geojson", "orderByFields": "objectid"})
        page = r.json()
        if "error" in page:
            raise RuntimeError(page["error"])
        for f in page.get("features", []):
            f["properties"]["supplemental_fetch"] = True
            feats.append(f)
            extra += 1
    st.note(f"supplemental pin10 fetch returned {extra} features")
    feats.sort(key=lambda f: (f["properties"].get("objectid") or 0))
    with open(dest, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, sort_keys=True)
    st.output(dest, role="Cook County parcel polygons (ArcGIS snapshot)",
              extra={"url": ARCGIS_PARCELS_URL, "where": f"municipality='{ARCGIS_MUNICIPALITY}'"})
    return dest


def fetch_commval(st):
    dest = os.path.join(RAW_DIR, "socrata_csik-bsws_oak_park.json")
    if os.path.exists(dest):
        st.note(f"exists, not re-downloaded: {dest}")
    else:
        rows, offset = [], 0
        while True:
            r = get(SOCRATA_COMMVAL_URL, params={
                "$where": f"township='{SOCRATA_COMMVAL_TOWNSHIP}'",
                "$order": "keypin,year", "$limit": 5000, "$offset": offset})
            got = r.json()
            rows.extend(got)
            if len(got) < 5000:
                break
            offset += 5000
        with open(dest, "w") as f:
            json.dump(rows, f, sort_keys=True, indent=0)
        st.note(f"socrata csik-bsws township='{SOCRATA_COMMVAL_TOWNSHIP}': {len(rows)} rows")
    st.output(dest, role="Assessor Commercial Valuation Data, Oak Park rows",
              extra={"url": SOCRATA_COMMVAL_URL})


def fetch_acs(st):
    dest = os.path.join(RAW_DIR, "censusreporter_acs_bg.json")
    if os.path.exists(dest):
        st.note(f"exists, not re-downloaded: {dest}")
    else:
        r = get(CENSUSREPORTER_URL, params={"geo_ids": ACS_GEO_QUERY,
                                            "table_ids": ",".join(ACS_TABLES)})
        obj = r.json()
        if "error" in obj:
            raise RuntimeError(obj["error"])
        with open(dest, "w") as f:
            json.dump(obj, f, sort_keys=True, indent=0)
        st.note(f"census reporter release={obj.get('release')} geos={len(obj.get('data', {}))}")
    with open(dest) as f:
        rel = json.load(f).get("release")
    st.output(dest, role="ACS 5-year block-group tables via Census Reporter",
              extra={"url": CENSUSREPORTER_URL, "geo_ids": ACS_GEO_QUERY,
                     "tables": list(ACS_TABLES), "release": rel})


def fetch_districts(st):
    dest = os.path.join(RAW_DIR, "vop_historic_districts.geojson")
    if os.path.exists(dest):
        st.note(f"exists, not re-downloaded: {dest}")
    else:
        r = get(VOP_HISTORIC_DISTRICTS_URL, params={"where": "1=1", "outFields": "*",
                                                    "outSR": 4326, "f": "geojson"})
        obj = r.json()
        if "error" in obj:
            raise RuntimeError(obj["error"])
        obj["features"].sort(key=lambda f: f["properties"].get("OBJECTID", 0))
        with open(dest, "w") as f:
            json.dump(obj, f, sort_keys=True)
        st.note("historic districts: " + ", ".join(
            f"{f['properties']['NAME'].strip()} ({f['properties']['TYPE']})" for f in obj["features"]))
    st.output(dest, role="Village of Oak Park historic district polygons",
              extra={"url": VOP_HISTORIC_DISTRICTS_URL})


def fetch_zoning(st):
    dest = os.path.join(RAW_DIR, "vop_zoning.geojson")
    if os.path.exists(dest):
        st.note(f"exists, not re-downloaded: {dest}")
    else:
        r = get(VOP_ZONING_URL, params={"where": "1=1", "outFields": VOP_ZONING_FIELDS,
                                        "outSR": 4326, "f": "geojson", "resultRecordCount": 2000})
        obj = r.json()
        if "error" in obj:
            raise RuntimeError(obj["error"])
        obj["features"].sort(key=lambda f: (f["properties"].get("ZONED") or "", json.dumps(f["geometry"])[:200]))
        with open(dest, "w") as f:
            json.dump(obj, f, sort_keys=True)
        st.note(f"zoning: {len(obj['features'])} polygons, zones "
                + ", ".join(sorted({f["properties"].get("ZONED") or "" for f in obj["features"]})))
    st.output(dest, role="Village of Oak Park zoning district polygons", extra={"url": VOP_ZONING_URL})


def fetch_condo_chars(st):
    dest = os.path.join(RAW_DIR, f"socrata_3r7i-mrz4_oak_park_{SOCRATA_CONDO_YEAR}.json")
    if os.path.exists(dest):
        st.note(f"exists, not re-downloaded: {dest}")
    else:
        rows, offset = [], 0
        while True:
            r = get(SOCRATA_CONDO_URL, params={
                "$where": f"township_code='27' AND year='{SOCRATA_CONDO_YEAR}'",
                "$order": "pin", "$limit": 5000, "$offset": offset})
            got = r.json()
            rows.extend(got)
            if len(got) < 5000:
                break
            offset += 5000
        with open(dest, "w") as f:
            json.dump(rows, f, sort_keys=True, indent=0)
        st.note(f"socrata 3r7i-mrz4 township 27 year {SOCRATA_CONDO_YEAR}: {len(rows)} condo unit rows")
    st.output(dest, role="Assessor Condominium Unit Characteristics, Oak Park",
              extra={"url": SOCRATA_CONDO_URL, "year": SOCRATA_CONDO_YEAR})


def main():
    with Stage("s02_fetch", __file__) as st:
        s01 = os.path.join(INTERIM_DIR, "s01_parcels.csv")
        st.input(s01, role="parcel list (for supplemental PIN fetch)")
        pins10 = set(pd.read_csv(s01, dtype={"pin": str}).pin.str[:10])
        fetch_arcgis_parcels(st, pins10)
        fetch_commval(st)
        for url, name in ((TIGER_BLOCKS_URL, "tl_2020_17_tabblock20.zip"),
                          (TIGER_BG_URL, "tl_2020_17_bg.zip"),
                          (TIGER_PLACE_URL, "tl_2020_17_place.zip")):
            p = download(st, url, os.path.join(RAW_DIR, name), role="TIGER/Line 2020 " + name)
            unzip(st, p, os.path.join(RAW_DIR, name.split("_")[-1].replace(".zip", "")
                                      .replace("tabblock20", "blocks")))
        p = download(st, PL_URL, os.path.join(RAW_DIR, "il2020.pl.zip"),
                     role="2020 P.L. 94-171 summary file, Illinois")
        unzip(st, p, os.path.join(RAW_DIR, "pl"))
        fetch_acs(st)
        fetch_districts(st)
        fetch_condo_chars(st)
        fetch_zoning(st)


if __name__ == "__main__":
    main()
