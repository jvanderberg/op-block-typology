"""Stage 10: multi-family buildings by historic district, with year built.

Buildings come from s04 (one row per building; condo units collapsed to the
10-digit parent, multi-PIN apartment properties collapsed to their
Commercial Valuation keypin). A building is multi-family when it has 2 or
more dwelling units in one structure (config MF_UNIT_TYPES / MF_MIN_UNITS):
2-6 unit buildings, 7+ unit buildings, condominium buildings. Townhomes
are one unit per PIN and are excluded.

District: the Village of Oak Park historic-district polygon containing the
building's point (the representative point of its parcel polygon, from s03).
Zoning: the Village zoning polygon containing the same point.

Year built, first rule that yields a value (recorded in yr_source):
  char_yrblt          2026 residential characteristics record (2-6 unit buildings)
  condo_chars         Assessor Condominium Unit Characteristics: minimum year
                      built over the building's units (phased buildings keep
                      the first phase)
  commval             Assessor Commercial Valuation `yearbuilt` for the PIN
                      (apartment-class row preferred over other rows)
  char_yrblt_anyyear  a residential characteristics record for the PIN in any
                      assessment year 2020-2026 (PINs since reclassified)
  manual              a published source recorded in config MANUAL_YEAR_BUILT
                      (applied after the class-history rule)
  class_history       the PIN is absent from the assessment roll, or vacant
                      (class 1xx, 200, 241, 290), or non-residential in an
                      earlier year and residential later: year built = first
                      residential year - 1 (buildings completed 2020 or later)
  unknown             none of the above

Condominium conversions (config CONDO_CONVERSION_*): a condo building whose
recorded year is close to the year its units first appear on the roll is
checked against the predecessor parcels captured in stage 2. If a predecessor
had a residential or apartment class and the units' first-year assessed value
is below CONDO_CONVERSION_MAX_AV_RATIO times the predecessors' value, the
building existed before the condominium declaration and the recorded year is
the conversion year, not the construction year. Under policy "exclude" such buildings are kept in the
output with excluded=True (and yr_predecessor holding the predecessor's year
built where the assessor recorded one) and dropped by stages 11 and 12; under
"redate" they take the predecessor's year. Vacant, commercial or condominium
predecessors mean new construction or a re-declaration and the recorded year
stands (yr_source condo_chars_newbuild). Candidates with no predecessor found
keep their year with yr_source condo_chars_unverified.

Outputs: data/interim/s10_mf_buildings.csv (one row per multi-family
building, with excluded / exclude_reason / yr_predecessor columns), data/interim/s10_district_parcels.csv (all residential units by
district and bucket, for context), data/interim/s10_district_zoning.csv
(area of each district by zoning district).
"""
import json
import os
import re

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

from config import (CONDO_CONVERSION_MAX_AV_RATIO, CONDO_CONVERSION_POLICY, HISTORIC_DISTRICTS, INTERIM_DIR, MANUAL_YEAR_BUILT, MF_MIN_UNITS,
                    MF_UNIT_TYPES, PREDECESSOR_EXISTING_CLASSES, RAW_DIR, SOCRATA_CONDO_YEAR)
from provenance import Stage

VACANT_CLASSES = {"100", "190", "200", "241", "290"}


def pin14(s):
    return re.sub(r"\D", "", s or "")


def is_residential_class(c):
    return isinstance(c, str) and (c[:1] in ("2", "3") or c == "EX") and c not in VACANT_CLASSES


def main():
    with Stage("s10_districts", __file__) as st:
        st.param(MF_UNIT_TYPES=MF_UNIT_TYPES, MF_MIN_UNITS=MF_MIN_UNITS, CONDO_CONVERSION_POLICY=CONDO_CONVERSION_POLICY,
                 districts={k: v["local_year"] for k, v in HISTORIC_DISTRICTS.items()})
        p_units = os.path.join(INTERIM_DIR, "s04_parcel_units.csv")
        p_hist = os.path.join(INTERIM_DIR, "s01_class_history.csv")
        p_dist = os.path.join(RAW_DIR, "vop_historic_districts.geojson")
        p_zone = os.path.join(RAW_DIR, "vop_zoning.geojson")
        p_condo = os.path.join(RAW_DIR, f"socrata_3r7i-mrz4_oak_park_{SOCRATA_CONDO_YEAR}.json")
        p_cv = os.path.join(RAW_DIR, "socrata_csik-bsws_oak_park.json")
        p_conv = os.path.join(RAW_DIR, "condo_conversion_check.json")
        st.input(p_conv, role="condo conversion check")
        with open(p_conv) as f:
            conv = json.load(f)["checks"]
        for p, r in ((p_units, "parcel units"), (p_hist, "class history"), (p_dist, "historic districts"),
                     (p_zone, "zoning"), (p_condo, "condo characteristics"), (p_cv, "commercial valuation")):
            st.input(p, role=r)

        df = pd.read_csv(p_units, dtype={"pin": str, "class": str, "building_id": str, "units_source": str,
                                         "unit_type": str, "bucket": str, "address": str})
        hist = pd.read_csv(p_hist, dtype={"pin": str, "class": str})

        # --- polygons ------------------------------------------------------
        with open(p_dist) as f:
            dgj = json.load(f)
        districts = {ft["properties"]["NAME"].strip(): shape(ft["geometry"]) for ft in dgj["features"]}
        assert set(districts) == set(HISTORIC_DISTRICTS), f"district names differ: {set(districts)}"
        with open(p_zone) as f:
            zgj = json.load(f)
        zones = [(ft["properties"]["ZONED"], shape(ft["geometry"])) for ft in zgj["features"]]
        st.note(f"districts: {list(districts)}; zoning polygons: {len(zones)}")

        loc = df[df.lat.notna()].copy()
        pts = gpd.GeoDataFrame(loc, geometry=gpd.points_from_xy(loc.lon, loc.lat), crs=4326)
        dg = gpd.GeoDataFrame({"district": list(districts)}, geometry=list(districts.values()), crs=4326)
        zg = gpd.GeoDataFrame({"zone": [z for z, _ in zones]}, geometry=[g for _, g in zones], crs=4326)
        j = gpd.sjoin(pts, dg, how="left", predicate="within").drop(columns="index_right")
        assert j.pin.is_unique, "a parcel fell in two historic districts"
        j = gpd.sjoin(j, zg, how="left", predicate="within").drop(columns="index_right")
        dup = j.pin.duplicated(keep="first")
        if dup.any():
            st.note(f"{int(dup.sum())} parcels sit on a zoning polygon seam; first zone kept")
            j = j[~dup]
        j["district"] = j.district.fillna("Rest of Oak Park")
        j["zone"] = j.zone.fillna("")
        st.note("located parcels by district: " + ", ".join(f"{k}={v}" for k, v in j.district.value_counts().items()))
        st.note(f"parcels without a zoning polygon: {int((j.zone == '').sum())}")

        # --- year-built lookups --------------------------------------------
        with open(p_condo) as f:
            condo = pd.DataFrame(json.load(f))
        condo["char_yrblt"] = pd.to_numeric(condo.char_yrblt, errors="coerce")
        condo_yr = condo[condo.char_yrblt > 0].groupby("pin10").char_yrblt.min().to_dict()
        with open(p_cv) as f:
            cv_rows = json.load(f)
        cv_yr = {}
        for r in sorted(cv_rows, key=lambda r: ("3-" not in (r.get("class_es") or ""), -int(float(r["year"])))):
            yb = r.get("yearbuilt")
            if yb in (None, "", "0", "0.0"):
                continue
            for p in [pin14(x) for x in (r.get("pins") or "").split(",")] + [pin14(r.get("keypin"))]:
                if p and p not in cv_yr:
                    cv_yr[p] = int(float(yb))
        anyyear = hist[hist.char_yrblt > 0].groupby("pin").char_yrblt.max().to_dict()
        first_res, first_seen, min_year = {}, {}, int(hist.year.min())
        for pin, g in hist.groupby("pin"):
            g = g.sort_values("year")
            first_seen[pin] = int(g.year.iloc[0])
            res = g[g["class"].map(is_residential_class)]
            if len(res):
                first_res[pin] = int(res.year.iloc[0])
        n_pins = len(hist.pin.unique())
        st.note(f"year lookups: condo buildings {len(condo_yr)}, commval PINs {len(cv_yr)}, "
                f"any-year characteristics {len(anyyear)}, class history {n_pins} PINs from {min_year}")

        def class_history_year(pins):
            """Year built inferred from the roll: the earliest 'first residential
            year' across the building's PINs, minus one, only when the PIN was
            absent or non-residential in an earlier year of the history."""
            best = None
            for p in pins:
                fr = first_res.get(p)
                if fr is None:
                    continue
                if first_seen.get(p, min_year) > min_year or fr > first_seen.get(p, min_year):
                    best = fr if best is None else min(best, fr)
            return best - 1 if best else None

        def year_built(b, pins):
            t = b.unit_type
            if t == "small_mf":
                y = b.char_yrblt
                if pd.notna(y) and y > 0:
                    return int(y), "char_yrblt"
            if t == "condo" and b.building_id in condo_yr:
                return int(condo_yr[b.building_id]), "condo_chars"
            for p in pins:
                if p in cv_yr:
                    return cv_yr[p], "commval"
            for p in pins:
                if p in anyyear:
                    return int(anyyear[p]), "char_yrblt_anyyear"
            y = class_history_year(pins)
            if y:
                return y, "class_history"
            for p in [b.building_id] + pins:
                if p in MANUAL_YEAR_BUILT:
                    return MANUAL_YEAR_BUILT[p][0], "manual"
            return None, "unknown"

        def addr_key(a):
            """'257 W WASHINGTON BLVD 1A' -> '257 WASHINGTON'; None when unparsable."""
            b = base_addr(a)
            if not b:
                return None
            parts = [w for w in b.split(" ") if w not in ("N", "S", "E", "W", "AVE", "ST", "BLVD", "RD", "PL", "CT", "LN", "PKY", "TER", "DR")]
            return " ".join(parts[:2]) if len(parts) >= 2 else None

        def conversion_verdict(pin10, address):
            """(verdict, predecessor_year) for a condo building: 'conversion',
            'newbuild', 'unverified', or None when not a candidate."""
            c = conv.get(pin10)
            if c is None:
                return None, None
            preds = c["predecessors"]
            if not preds:
                return "unverified", None
            existing = [p for p in preds if p["class"] in PREDECESSOR_EXISTING_CLASSES]
            if not existing:
                return "newbuild", None
            pred_av = c.get("predecessor_av", 0) or 0
            ratio = (c.get("condo_av_first_year", 0) / pred_av) if pred_av > 0 else float("inf")
            if ratio >= CONDO_CONVERSION_MAX_AV_RATIO:
                return "newbuild", None       # value jump: the old building was replaced
            # Two condo buildings declared in the same block in the same year share
            # a predecessor set; attribute by address (house number + street) when
            # a predecessor matches this building's address, else use them all.
            key = addr_key(address)
            matched = [p for p in existing if addr_key(p["address"]) == key]
            use = matched or existing
            yrs = sorted({y for p in use for y in p["char_yrblt"]})
            return "conversion", (yrs[0] if yrs else None)

        # --- buildings -------------------------------------------------------
        mf = j[j.unit_type.isin(MF_UNIT_TYPES)].copy()
        # Large buildings absent from the Commercial Valuation data keep one
        # building_id per PIN in s04, yet the assessor often splits one
        # structure across several PINs (equal AV on each, or one address with
        # unit suffixes). Merge such PINs into one building when they share a
        # normalised base address, or share class, building AV and year built
        # and lie within 100 m of each other. Units are summed; every merge is
        # logged.
        def base_addr(a):
            if not isinstance(a, str):
                return None
            a = re.sub(r"\s+", " ", a.upper().strip())
            parts = a.split(" ")
            if len(parts) >= 4 and re.fullmatch(r"[A-Z0-9-]{1,5}", parts[-1]) and parts[-1] not in (
                    "AVE", "ST", "BLVD", "PL", "CT", "RD", "DR", "PKY", "PKWY", "TER", "LN", "N", "S", "E", "W"):
                return " ".join(parts[:-1])
            return a
        est = mf[(mf.unit_type == "large_mf") & (mf.building_id == mf.pin)].copy()
        est["base"] = est.address.map(base_addr)
        merges = 0
        for _, g in est.groupby("base"):
            if len(g) > 1 and g.base.iloc[0]:
                target = g.pin.min()
                mf.loc[mf.pin.isin(g.pin), "building_id"] = target
                merges += 1
                st.note(f"merge by address: {sorted(g.pin)} -> {target} ({g.base.iloc[0]})")
        est = mf[(mf.unit_type == "large_mf") & (mf.building_id == mf.pin)].copy()
        est["yr_key"] = [year_built(r, [r.pin])[0] for r in est.itertuples(index=False)]
        for _, g in est.groupby(["class", "mailed_bldg", "yr_key"], dropna=False):
            if len(g) > 1:
                gg = gpd.GeoDataFrame(g, geometry=gpd.points_from_xy(g.lon, g.lat), crs=4326).to_crs(26971)
                c = gg.geometry.unary_union.centroid
                if gg.geometry.distance(c).max() <= 100:
                    target = g.pin.min()
                    mf.loc[mf.pin.isin(g.pin), "building_id"] = target
                    merges += 1
                    st.note(f"merge by class/AV/year within 100 m: {sorted(g.pin)} -> {target} "
                            f"({g.address.iloc[0]}; class {g['class'].iloc[0]}, AV {g.mailed_bldg.iloc[0]:.0f}, built {g.yr_key.iloc[0]})")
        st.note(f"multi-PIN merges applied: {merges}")
        rows = []
        for bid, g in mf.groupby("building_id"):
            g = g.sort_values("pin")
            f = g.iloc[0]
            pins = list(g.pin)
            units = float(g.units.sum())
            yr, src = year_built(f, pins)
            excluded, reason, yr_pred = False, "", None
            if f.unit_type == "condo":
                verdict, yr_pred = conversion_verdict(bid, f.address)
                if verdict == "conversion":
                    if CONDO_CONVERSION_POLICY == "redate" and yr_pred is not None:
                        yr, src = yr_pred, "predecessor_chars"
                    elif CONDO_CONVERSION_POLICY == "redate":
                        yr, src = None, "conversion_year_unknown"
                    else:
                        excluded, reason = True, "condo_conversion"
                elif verdict == "newbuild":
                    src = "condo_chars_newbuild"
                elif verdict == "unverified":
                    src = "condo_chars_unverified"
            rows.append({"building_id": bid, "address": base_addr(f.address) if len(g) > 1 else f.address,
                         "district": f.district, "zone": f.zone,
                         "unit_type": f.unit_type, "bucket": f.bucket, "units": units, "n_pins": len(g),
                         "classes": "|".join(sorted(set(g["class"]))), "units_source": f.units_source,
                         "yrblt": yr, "yr_source": src, "excluded": excluded, "exclude_reason": reason,
                         "yr_predecessor": yr_pred, "lat": f.lat, "lon": f.lon})
        b = pd.DataFrame(rows)
        b = b[b.units >= MF_MIN_UNITS].sort_values(["district", "building_id"]).reset_index(drop=True)
        st.note(f"multi-family buildings (>= {MF_MIN_UNITS} units): {len(b)} with {b.units.sum():.0f} units")
        st.note("year source: " + ", ".join(f"{k}={v}" for k, v in b.yr_source.value_counts().items()))
        ex = b[b.excluded]
        rd = b[b.yr_source.isin(("predecessor_chars", "conversion_year_unknown"))]
        st.note(f"condo conversions redated: {len(rd)} buildings, {rd.units.sum():.0f} units: " + "; ".join(
            f"{r.address} ({r.district}, {r.units:.0f} u, year used {int(r.yrblt) if pd.notna(r.yrblt) else 'unknown'})" for _, r in rd.iterrows()))
        st.note(f"condo conversions excluded: {len(ex)} buildings, {ex.units.sum():.0f} units: " + "; ".join(
            f"{r.address} ({r.district}, {r.units:.0f} u, recorded {int(r.yrblt) if pd.notna(r.yrblt) else '?'}, "
            f"predecessor built {int(r.yr_predecessor) if pd.notna(r.yr_predecessor) else 'unknown'})" for _, r in ex.iterrows()))
        unk = b[b.yr_source == "unknown"]
        st.note(f"unknown year: {len(unk)} buildings, {unk.units.sum():.0f} units: " + "; ".join(
            f"{r.address} ({r.district}, {r.units:.0f} u, {r.classes})" for _, r in unk.iterrows()))
        ch = b[b.yr_source == "class_history"]
        man = b[b.yr_source == "manual"]
        st.note("manually dated (config MANUAL_YEAR_BUILT, with source): " + "; ".join(
            f"{r.address} {r.yrblt} ({r.units:.0f} u) <{MANUAL_YEAR_BUILT.get(r.building_id, ('', ''))[1]}>" for _, r in man.iterrows()))
        st.note("class-history dated: " + "; ".join(f"{r.address} {r.yrblt} ({r.units:.0f} u)" for _, r in ch.iterrows()))
        for d in list(HISTORIC_DISTRICTS) + ["Rest of Oak Park"]:
            s = b[(b.district == d) & ~b.excluded]
            st.note(f"  {d}: {len(s)} MF buildings kept, {s.units.sum():.0f} units, "
                    f"{int(s.yrblt.isna().sum())} undated; excluded {int(((b.district == d) & b.excluded).sum())}")
        out = os.path.join(INTERIM_DIR, "s10_mf_buildings.csv")
        b.to_csv(out, index=False)
        st.output(out, role="multi-family buildings with district, zone, year built")

        # --- context: all residential units by district and bucket -------------
        ctx = (j[j.units > 0].groupby(["district", "bucket"]).agg(units=("units", "sum"), parcels=("pin", "size"),
                                                                  buildings=("building_id", "nunique"))
               .reset_index().sort_values(["district", "bucket"]))
        out2 = os.path.join(INTERIM_DIR, "s10_district_parcels.csv")
        ctx.to_csv(out2, index=False)
        st.output(out2, role="housing units by district and bucket")

        # --- district area by zoning district ---------------------------------
        dz = gpd.overlay(dg, zg, how="intersection")
        dz = dz.to_crs(26971)   # NAD83 / Illinois East (ft-> m); area in square metres
        dz["area_sqm"] = dz.geometry.area
        dzt = dz.groupby(["district", "zone"]).area_sqm.sum().reset_index()
        tot = dzt.groupby("district").area_sqm.transform("sum")
        dzt["share"] = (dzt.area_sqm / tot).round(4)
        dzt = dzt.sort_values(["district", "zone"]).reset_index(drop=True)
        out3 = os.path.join(INTERIM_DIR, "s10_district_zoning.csv")
        dzt.to_csv(out3, index=False)
        st.output(out3, role="district area by zoning district")


if __name__ == "__main__":
    main()
