"""Stage 4: count housing units on every parcel and group parcels into
buildings.

Unit rules (all class lists live in config.py):
  sf_detached  classes 202-209, 234, 278, 218 ............ 1 unit per PIN
  sf_attached  classes 210, 295 (townhome / row house) .... 1 unit per PIN
  small_mf     classes 211, 212 .......................... char_apts word
               ("Two".."Six"); missing -> SMALL_MF_DEFAULT_UNITS, flagged
  condo        class 299 ................................. 1 unit per PIN;
               building = 10-digit parent PIN; a building with more than
               SMALL_MF_MAX_UNITS units is a large building
  large_mf     classes 313-318, 390, 391, 397, 213 ....... total units from
               the Assessor Commercial Valuation Data (csik-bsws), allocated
               across the PINs of a multi-PIN property in proportion to
               building assessed value; PINs absent from that dataset get
               max(LARGE_MF_MIN_UNITS, round(building AV / median AV per
               unit of the covered buildings of the same class)), flagged
  exempt_res   class EX with a residential characteristics record ...
               1 unit (Single-Family) or char_apts units (Multi-Family)
  none         everything else (vacant, garages, commercial, railroad) . 0

Override: a PIN that the Commercial Valuation Data lists as an apartment
property (class 3-xx with tot_units) is counted as large_mf with those units
whatever its 2026 class says. Rows of other classes that carry tot_units
(mostly 2-36 mixed-use rows) are used only for PINs already classed
large_mf here, in place of the assessed-value estimate. This catches new apartment towers carried as
exempt or commercial PINs in the assessed-values file (e.g. 150 Forest Ave,
1005 Lake St). Each override is logged with both classes.

Bucket (what the block classification counts):
  sf        = sf_detached + sf_attached + exempt single-family
  small_mf  = small_mf + condo buildings with <= 6 units + exempt multi-family
  large_mf  = large_mf + condo buildings with >= 7 units

Outputs: data/interim/s04_parcel_units.csv (one row per PIN, with units,
unit_type, bucket, units_source, building_id) and
data/interim/s04_buildings.csv (one row per building).
"""
import json
import os
import re
from collections import defaultdict

import numpy as np
import pandas as pd

from config import (CHAR_APTS_WORDS, CONDO_CLASSES, EXEMPT_CLASS, INTERIM_DIR,
                    LARGE_MF_CLASSES, LARGE_MF_MIN_UNITS, RAW_DIR, SF_ATTACHED_CLASSES,
                    SF_DETACHED_CLASSES, SMALL_MF_CLASSES, SMALL_MF_DEFAULT_UNITS,
                    SMALL_MF_MAX_UNITS, YEAR)
from provenance import Stage


class _Row(dict):
    """dict with attribute access; 'class' is a keyword so itertuples() cannot expose it."""
    __getattr__ = dict.__getitem__


def pin14(s):
    return re.sub(r"\D", "", s or "")


def commval_units(st, pins_in_scope, av_bldg):
    """Map PIN -> (units, keypin, year) from the Commercial Valuation rows.

    Each row describes one property (keypin) that may span several PINs and
    carries tot_units for the whole property. Units are allocated across the
    row's PINs that are in scope, weighted by 2026 building AV (equal split
    when the AVs are all zero/missing). Only rows with an apartment class
    (class_es containing '3-') and a tot_units value are used; the newest
    year wins if a keypin repeats.
    """
    path = os.path.join(RAW_DIR, "socrata_csik-bsws_oak_park.json")
    st.input(path, role="Commercial Valuation Data (unit counts)")
    with open(path) as f:
        rows = json.load(f)
    rows = [r for r in rows if r.get("tot_units") not in (None, "")]
    n_apt = sum(1 for r in rows if "3-" in (r.get("class_es") or ""))
    st.note(f"commval: {len(rows)} rows with tot_units ({n_apt} apartment-class 3-xx, "
            f"{len(rows) - n_apt} other classes, mostly 2-36 mixed-use)")
    best = {}
    for r in rows:
        k = pin14(r["keypin"])
        is_apt = "3-" in (r.get("class_es") or "")
        if k not in best:
            best[k] = r
            continue
        b_apt = "3-" in (best[k].get("class_es") or "")
        if (is_apt, int(float(r["year"]))) > (b_apt, int(float(best[k]["year"]))):
            best[k] = r
    out, n_multi, n_alloc_pins = {}, 0, 0
    for k, r in sorted(best.items()):
        pins = [pin14(p) for p in (r.get("pins") or "").split(",") if pin14(p)]
        pins = sorted(set(pins)) or [k]
        inscope = [p for p in pins if p in pins_in_scope]
        if not inscope:
            st.note(f"commval keypin {k} ({r.get('address')}) has no PIN in the 2026 parcel list; skipped")
            continue
        tot = float(r["tot_units"])
        if len(inscope) > 1:
            n_multi += 1
        w = np.array([max(0.0, float(av_bldg.get(p, 0) or 0)) for p in inscope])
        w = w / w.sum() if w.sum() > 0 else np.full(len(inscope), 1.0 / len(inscope))
        for p, wi in zip(inscope, w):
            if p in out:
                st.note(f"commval PIN {p} appears under two keypins; keeping first ({out[p][1]})")
                continue
            out[p] = (tot * wi, k, int(float(r["year"])), len(inscope), r.get("yearbuilt"))
            n_alloc_pins += 1
    st.note(f"commval: {len(best)} properties, {n_multi} span several PINs, "
            f"{n_alloc_pins} PINs received an allocation")
    return out


def main():
    with Stage("s04_units", __file__) as st:
        st.param(SF_DETACHED_CLASSES=SF_DETACHED_CLASSES, SF_ATTACHED_CLASSES=SF_ATTACHED_CLASSES,
                 SMALL_MF_CLASSES=SMALL_MF_CLASSES, CONDO_CLASSES=CONDO_CLASSES,
                 LARGE_MF_CLASSES=LARGE_MF_CLASSES, SMALL_MF_DEFAULT_UNITS=SMALL_MF_DEFAULT_UNITS,
                 SMALL_MF_MAX_UNITS=SMALL_MF_MAX_UNITS, LARGE_MF_MIN_UNITS=LARGE_MF_MIN_UNITS)
        s03 = os.path.join(INTERIM_DIR, "s03_parcels_located.csv")
        st.input(s03, role="located parcels")
        df = pd.read_csv(s03, dtype={"pin": str, "class": str, "nbhd": str, "char_apts": str,
                                     "char_use": str, "arcgis_name": str, "parceltype": str})
        av_bldg = dict(zip(df.pin, df.mailed_bldg.fillna(0)))
        cv = commval_units(st, set(df.pin), av_bldg)

        # --- per-parcel type and raw units ---------------------------------
        unit_type, units, source, bid = [], [], [], []
        for r in df.to_dict("records"):
            r = _Row(r)
            c = r["class"]
            t, u, s, b = "none", 0.0, "class_rule", r.pin
            if c in SF_DETACHED_CLASSES:
                t, u = "sf_detached", 1.0
            elif c in SF_ATTACHED_CLASSES:
                t, u = "sf_attached", 1.0
            elif c in SMALL_MF_CLASSES:
                t = "small_mf"
                if r.char_apts in CHAR_APTS_WORDS:
                    u, s = float(CHAR_APTS_WORDS[r.char_apts]), "char_apts"
                else:
                    u, s = float(SMALL_MF_DEFAULT_UNITS), "default_missing_char_apts"
            elif c in CONDO_CLASSES:
                t, u, b = "condo", 1.0, r.pin[:10]
            elif c in LARGE_MF_CLASSES:
                t = "large_mf"
                if r.pin in cv:
                    u, s = cv[r.pin][0], f"commval_{cv[r.pin][2]}"
                    b = cv[r.pin][1]
                else:
                    u, s = np.nan, "estimate_pending"
            elif c == EXEMPT_CLASS and isinstance(r.char_use, str):
                if r.char_use == "Multi-Family" and r.char_apts in CHAR_APTS_WORDS:
                    t, u, s = "exempt_res", float(CHAR_APTS_WORDS[r.char_apts]), "exempt_char_apts"
                elif r.char_use == "Single-Family":
                    t, u, s = "exempt_res", 1.0, "exempt_single_family"
            unit_type.append(t); units.append(u); source.append(s); bid.append(b)
        df["unit_type"], df["units"], df["units_source"], df["building_id"] = unit_type, units, source, bid

        # --- Commercial Valuation override for PINs not classed residential-large
        n_over = 0
        apt_keypins = {pin14(r["keypin"]) for r in json.load(open(os.path.join(RAW_DIR, "socrata_csik-bsws_oak_park.json")))
                       if "3-" in (r.get("class_es") or "") and r.get("tot_units") not in (None, "")}
        for i in df.index[df.pin.isin(cv.keys()) & (df.unit_type != "large_mf")]:
            p = df.at[i, "pin"]
            if cv[p][0] <= 0:      # ancillary PIN of a multi-PIN property (0 units allocated)
                continue
            if cv[p][1] not in apt_keypins:   # a 2-36 row does not reclassify a small building
                continue
            st.note(f"commval override: PIN {p} ({df.at[i, 'address']}) is class {df.at[i, 'class']} in {YEAR} "
                    f"assessed values but an apartment property with {cv[p][0]:.1f} units in the "
                    f"{cv[p][2]} Commercial Valuation data; counted as large_mf "
                    f"(was {df.at[i, 'unit_type']} with {df.at[i, 'units']:.0f} units)")
            df.at[i, "unit_type"], df.at[i, "units"] = "large_mf", cv[p][0]
            df.at[i, "units_source"], df.at[i, "building_id"] = f"commval_{cv[p][2]}_override", cv[p][1]
            n_over += 1
        st.note(f"commval overrides applied: {n_over}")

        # --- estimate large-MF units for PINs the commval data does not cover
        lm = df[df.unit_type == "large_mf"]
        covered = lm[lm.units_source.str.startswith("commval")]
        covered = covered[(covered.units > 0) & (covered.mailed_bldg > 0)]
        av_per_unit_all = float((covered.mailed_bldg / covered.units).median())
        av_per_unit_cls = (covered.mailed_bldg / covered.units).groupby(covered["class"]).median().to_dict()
        st.note(f"large_mf AV-per-unit calibration: overall median {av_per_unit_all:,.0f}; "
                "by class " + ", ".join(f"{k}={v:,.0f} (n={int((covered['class']==k).sum())})"
                                        for k, v in sorted(av_per_unit_cls.items())))
        pend = df.units_source == "estimate_pending"
        for i in df.index[pend]:
            c = df.at[i, "class"]
            apu = av_per_unit_cls.get(c, av_per_unit_all)
            avb = float(df.at[i, "mailed_bldg"] or 0)
            raw = avb / apu if apu > 0 else 0.0
            if raw < 0.5:
                # Building AV below half a unit's worth: an ancillary parcel
                # (parking, yard) of an apartment property, not a building.
                df.at[i, "units"] = 0.0
                df.at[i, "units_source"] = "estimate_av/ancillary"
                continue
            est = max(LARGE_MF_MIN_UNITS, int(round(raw)))
            df.at[i, "units"] = float(est)
            df.at[i, "units_source"] = f"estimate_av/{'class' if c in av_per_unit_cls else 'all'}"
        st.note(f"large_mf: {len(lm)} PINs, {int(covered.shape[0])} with commval units, "
                f"{int(pend.sum())} estimated from AV (sum est. units {df.loc[pend,'units'].sum():.0f})")

        # --- buildings and buckets ----------------------------------------
        bld_units = df.groupby("building_id")["units"].sum()
        df["building_units"] = df.building_id.map(bld_units)

        def bucket(row):
            t = row.unit_type
            if t in ("sf_detached", "sf_attached"):
                return "sf"
            if t == "small_mf":
                return "small_mf"
            if t == "large_mf":
                return "large_mf"
            if t == "condo":
                return "small_mf" if row.building_units <= SMALL_MF_MAX_UNITS else "large_mf"
            if t == "exempt_res":
                return "sf" if row.units_source == "exempt_single_family" else "small_mf"
            return "none"
        df["bucket"] = df.apply(bucket, axis=1)

        for col in ("unit_type", "bucket", "units_source"):
            g = df.groupby(col)["units"].agg(["count", "sum"])
            st.note(f"{col}: " + ", ".join(f"{k}: {int(v['count'])} PINs / {v['sum']:.0f} units"
                                           for k, v in g.iterrows()))
        st.note(f"TOTAL housing units on parcels: {df.units.sum():.0f}")

        out = os.path.join(INTERIM_DIR, "s04_parcel_units.csv")
        df.to_csv(out, index=False)
        st.output(out, role="parcels with unit counts, type, bucket and source")

        # One row per building: location = first located PIN's point (condo
        # units all resolve to the parent polygon, so this is the parcel).
        b = (df.sort_values(["building_id", "pin"])
               .groupby("building_id")
               .agg(units=("units", "sum"), n_pins=("pin", "count"),
                    bucket=("bucket", "first"), unit_type=("unit_type", "first"),
                    lat=("lat", "first"), lon=("lon", "first"),
                    address=("address", "first"), classes=("class", lambda s: "|".join(sorted(set(s)))))
               .reset_index())
        outb = os.path.join(INTERIM_DIR, "s04_buildings.csv")
        b.to_csv(outb, index=False)
        st.note(f"buildings: {len(b)} (with housing: {(b.units > 0).sum()})")
        st.output(outb, role="one row per building")


if __name__ == "__main__":
    main()
