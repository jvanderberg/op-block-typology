"""Stage 3: give every parcel a point location, with the rule that produced it.

Rules, tried in order (first hit wins; the rule is recorded per row):
  1. arcgis_pin14  - the parcel polygon whose 14-digit name equals the PIN.
                     A point inside the polygon (shapely representative_point)
                     is used, so it cannot fall on a street.
  2. arcgis_pin10  - the polygon whose 10-digit pin10 equals the PIN's first
                     10 digits: condominium units resolve to their building's
                     parcel; some base parcels only carry the 10-digit key.
  3. address_point - the Assessor address point for the PIN (lat/lon from the
                     Cook County Address Points dataset in the source db).
  4. address_match - the PIN's site address, normalised (upper case, single
                     spaces) and with a trailing unit token removed, matched
                     to an Oak Park address point with the same normalised
                     address.
  5. unlocated     - none of the above; carried forward with no coordinates.

Output: data/interim/s03_parcels_located.csv (all s01 rows plus lat, lon,
coord_source, arcgis_name, parceltype).
"""
import json
import os
import re

import pandas as pd
from shapely.geometry import shape

from config import INTERIM_DIR, RAW_DIR
from provenance import Stage


def norm(addr):
    if not isinstance(addr, str):
        return None
    return re.sub(r"\s+", " ", addr.upper().strip())


def strip_unit(addr):
    """'1005 WASHINGTON BLVD 1A' -> '1005 WASHINGTON BLVD'; leaves '123 MAIN ST' alone."""
    if addr is None:
        return None
    parts = addr.split(" ")
    if len(parts) >= 4 and re.fullmatch(r"[A-Z0-9-]{1,5}", parts[-1]) and parts[-1] not in (
            "AVE", "ST", "BLVD", "PL", "CT", "RD", "DR", "PKY", "PKWY", "TER", "LN", "N", "S", "E", "W"):
        return " ".join(parts[:-1])
    return addr


def main():
    with Stage("s03_locate", __file__) as st:
        s01 = os.path.join(INTERIM_DIR, "s01_parcels.csv")
        s01ap = os.path.join(INTERIM_DIR, "s01_address_points.csv")
        gj = os.path.join(RAW_DIR, "arcgis_parcels_oak_park.geojson")
        st.input(s01, role="parcels")
        st.input(s01ap, role="address points")
        st.input(gj, role="parcel polygons")
        df = pd.read_csv(s01, dtype={"pin": str, "class": str, "nbhd": str, "char_apts": str})
        ap = pd.read_csv(s01ap, dtype={"pin": str})
        by_addr = {}
        for r in ap.itertuples(index=False):
            k = norm(r.address)
            if k and k not in by_addr:
                by_addr[k] = (r.lat, r.lon)
        with open(gj) as f:
            feats = json.load(f)["features"]

        by14, by10 = {}, {}
        n_bad_geom = 0
        for ft in feats:
            pr = ft["properties"]
            if ft.get("geometry") is None:
                n_bad_geom += 1
                continue
            geom = shape(ft["geometry"])
            if geom.is_empty:
                n_bad_geom += 1
                continue
            pt = geom.representative_point()
            rec = (pt.y, pt.x, pr.get("name"), pr.get("parceltype"))
            name = pr.get("name") or ""
            if name and name not in by14:
                by14[name] = rec
            p10 = pr.get("pin10") or ""
            # Prefer a base/condominium parcel over ancillary records for the
            # 10-digit key; first occurrence in objectid order otherwise.
            if p10 and (p10 not in by10 or
                        (by10[p10][3] not in ("BaseParcel", "CondominiumParcel")
                         and rec[3] in ("BaseParcel", "CondominiumParcel"))):
                by10[p10] = rec
        st.note(f"polygons: {len(feats)} features, {n_bad_geom} without usable geometry, "
                f"{len(by14)} distinct 14-digit names, {len(by10)} distinct pin10")

        lat, lon, src, aname, ptype = [], [], [], [], []
        for r in df.itertuples(index=False):
            rec = by14.get(r.pin)
            rule = "arcgis_pin14"
            if rec is None:
                rec = by10.get(r.pin[:10])
                rule = "arcgis_pin10"
            if rec is None and pd.notna(r.ap_lat) and pd.notna(r.ap_lon):
                rec = (r.ap_lat, r.ap_lon, None, None)
                rule = "address_point"
            if rec is None:
                k = norm(r.address)
                hit = by_addr.get(k) or by_addr.get(strip_unit(k))
                if hit:
                    rec = (hit[0], hit[1], None, None)
                    rule = "address_match"
            if rec is None:
                lat.append(None); lon.append(None); src.append("unlocated")
                aname.append(None); ptype.append(None)
            else:
                lat.append(rec[0]); lon.append(rec[1]); src.append(rule)
                aname.append(rec[2]); ptype.append(rec[3])
        df["lat"], df["lon"], df["coord_source"] = lat, lon, src
        df["arcgis_name"], df["parceltype"] = aname, ptype

        st.note("coordinate source counts: " +
                ", ".join(f"{k}={v}" for k, v in df.coord_source.value_counts().items()))
        un = df[df.coord_source == "unlocated"]
        st.note("unlocated by class: " +
                ", ".join(f"{k}={v}" for k, v in un["class"].value_counts().items()))
        # Sanity: every located point must be inside Oak Park's bounding box.
        loc = df[df.lat.notna()]
        assert loc.lat.between(41.84, 41.93).all() and loc.lon.between(-87.82, -87.76).all(), \
            "coordinates outside the Oak Park bounding box"
        out = os.path.join(INTERIM_DIR, "s03_parcels_located.csv")
        df.to_csv(out, index=False)
        st.output(out, role="parcels with point location and locating rule")


if __name__ == "__main__":
    main()
