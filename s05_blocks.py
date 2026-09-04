"""Stage 5: assign parcels to 2020 Census blocks and classify every block.

Geometry: TIGER/Line 2020 blocks and block groups for Illinois, clipped to
the Oak Park village polygon (a block is "in Oak Park" when its
representative point falls inside the place polygon; Oak Park's borders
follow streets, so blocks do not straddle the boundary).

Assignment: each located parcel point is joined to the block polygon that
contains it (predicate: within). Parcels that land in a block outside the
place, or in no block, are logged and excluded.

Classification, by share of the block's housing units (config.py):
  no_housing      no units
  single_family   sf share >= SF_ONLY_MIN_SHARE
  small_mf_2_6    small_mf share >= DOMINANT_SHARE
  large_mf_7plus  large_mf share >= DOMINANT_SHARE
  mixed           everything else with housing
Sensitivity columns repeat the rule at each SF_ONLY_SENSITIVITY cutoff, and
with every estimated 7+ building unit count replaced by LARGE_MF_MIN_UNITS
(category_estmin).

Reconciliation: the 2020 Census housing-unit count per block (HOUSING20;
an exact "invariant" in the 2020 disclosure-avoidance system) is compared
with the parcel-derived count. Blocks where the census exceeds parcels by
CENSUS_GAP_MIN_UNITS and CENSUS_GAP_MIN_SHARE are flagged census_gap.

Outputs: data/interim/s05_blocks.csv, data/interim/s05_blocks.geojson,
data/interim/s05_blockgroups.csv (same aggregation by block group).
"""
import os

import geopandas as gpd
import pandas as pd

from config import (CATEGORIES, CENSUS_GAP_MIN_SHARE, CENSUS_GAP_MIN_UNITS, DOMINANT_SHARE,
                    INTERIM_DIR, LARGE_MF_MIN_UNITS, PLACE_GEOID, RAW_DIR, SF_ONLY_MIN_SHARE,
                    SF_ONLY_SENSITIVITY)
from provenance import Stage

BUCKETS = ("sf", "small_mf", "large_mf")


def classify(row, sf_min):
    tot = row["units"]
    if tot <= 0:
        return "no_housing"
    if row["units_sf"] / tot >= sf_min:
        return "single_family"
    if row["units_small_mf"] / tot >= DOMINANT_SHARE:
        return "small_mf_2_6"
    if row["units_large_mf"] / tot >= DOMINANT_SHARE:
        return "large_mf_7plus"
    return "mixed"


def aggregate(df, key):
    g = df.groupby(key)
    out = pd.DataFrame({
        "n_parcels": g.size(),
        "units": g["units"].sum(),
        "n_buildings_res": g.apply(lambda x: x.loc[x.units > 0, "building_id"].nunique()),
    })
    for b in BUCKETS:
        out[f"units_{b}"] = g.apply(lambda x, b=b: x.loc[x.bucket == b, "units"].sum())
        out[f"bldgs_{b}"] = g.apply(lambda x, b=b: x.loc[x.bucket == b, "building_id"].nunique())
    out["units_estimated"] = g.apply(lambda x: x.loc[x.units_source.str.startswith("estimate"), "units"].sum())
    # Robustness: the same aggregation with every estimated large-MF parcel
    # set to the class minimum (LARGE_MF_MIN_UNITS) instead of its AV estimate.
    est = df.units_source.str.startswith("estimate")
    n_est = df.loc[est].groupby(key).size().reindex(out.index).fillna(0)
    out["units_large_mf_estmin"] = out["units_large_mf"] - out["units_estimated"] + LARGE_MF_MIN_UNITS * n_est
    out["units_estmin"] = out["units"] - out["units_estimated"] + LARGE_MF_MIN_UNITS * n_est
    for b in BUCKETS:
        out[f"share_{b}"] = (out[f"units_{b}"] / out["units"]).where(out["units"] > 0, 0.0).round(4)
    out["category"] = out.apply(classify, axis=1, sf_min=SF_ONLY_MIN_SHARE)
    for s in SF_ONLY_SENSITIVITY:
        out[f"category_sf{int(s*100)}"] = out.apply(classify, axis=1, sf_min=s)
    alt = out.rename(columns={"units": "units_avest", "units_large_mf": "units_large_mf_avest",
                              "units_estmin": "units", "units_large_mf_estmin": "units_large_mf"})
    out["category_estmin"] = alt.apply(classify, axis=1, sf_min=SF_ONLY_MIN_SHARE)
    return out.reset_index()


def main():
    with Stage("s05_blocks", __file__) as st:
        st.param(SF_ONLY_MIN_SHARE=SF_ONLY_MIN_SHARE, DOMINANT_SHARE=DOMINANT_SHARE,
                 SF_ONLY_SENSITIVITY=SF_ONLY_SENSITIVITY, CENSUS_GAP_MIN_UNITS=CENSUS_GAP_MIN_UNITS,
                 CENSUS_GAP_MIN_SHARE=CENSUS_GAP_MIN_SHARE, PLACE_GEOID=PLACE_GEOID)
        s04 = os.path.join(INTERIM_DIR, "s04_parcel_units.csv")
        st.input(s04, role="parcel units")
        place_shp = os.path.join(RAW_DIR, "place", "tl_2020_17_place.shp")
        blocks_shp = os.path.join(RAW_DIR, "blocks", "tl_2020_17_tabblock20.shp")
        bg_shp = os.path.join(RAW_DIR, "bg", "tl_2020_17_bg.shp")
        for p in (place_shp, blocks_shp, bg_shp):
            st.input(p, role="TIGER/Line 2020 shapefile")
            st.input(p.replace(".shp", ".dbf"), role="TIGER/Line 2020 attribute table")

        place = gpd.read_file(place_shp)
        place = place[place.GEOID == PLACE_GEOID].to_crs(4326)
        assert len(place) == 1, "place polygon not found"
        poly = place.geometry.iloc[0]
        st.note(f"place {PLACE_GEOID} {place.NAMELSAD.iloc[0]}: area {poly.area:.6f} sq deg")

        blocks = gpd.read_file(blocks_shp, mask=poly).to_crs(4326)
        blocks["in_place"] = blocks.representative_point().within(poly)
        st.note(f"blocks intersecting place bbox/mask: {len(blocks)}; inside: {int(blocks.in_place.sum())}")
        inside = blocks[blocks.in_place].copy()
        st.note(f"inside blocks: POP20 sum {int(inside.POP20.sum())}, HOUSING20 sum {int(inside.HOUSING20.sum())}, "
                f"tracts {sorted(inside.TRACTCE20.unique())}")

        df = pd.read_csv(s04, dtype={"pin": str, "class": str, "building_id": str, "units_source": str,
                                     "bucket": str, "unit_type": str})
        loc = df[df.lat.notna()].copy()
        st.note(f"parcels: {len(df)}; located: {len(loc)}; unlocated (excluded): {len(df) - len(loc)} "
                f"carrying {df.loc[df.lat.isna(), 'units'].sum():.0f} units")
        pts = gpd.GeoDataFrame(loc, geometry=gpd.points_from_xy(loc.lon, loc.lat), crs=4326)
        joined = gpd.sjoin(pts, blocks[["GEOID20", "in_place", "geometry"]], how="left", predicate="within")
        assert joined.pin.is_unique, "a parcel point fell in more than one block"
        n_none = int(joined.GEOID20.isna().sum())
        n_out = int((joined.in_place == False).sum())  # noqa: E712
        st.note(f"parcels in no block: {n_none} ({joined.loc[joined.GEOID20.isna(), 'units'].sum():.0f} units); "
                f"in a block outside the place: {n_out} ({joined.loc[joined.in_place == False, 'units'].sum():.0f} units)")
        if n_out:
            st.note("outside-place parcels: " + "; ".join(
                f"{r.pin} {r['class']} {r.address}" for _, r in joined[joined.in_place == False].head(20).iterrows()))
        ok = joined[joined.in_place == True].drop(columns="geometry")  # noqa: E712
        ok["block_geoid"] = ok.GEOID20
        ok["bg_geoid"] = ok.GEOID20.str[:12]
        st.note(f"parcels assigned to Oak Park blocks: {len(ok)} with {ok.units.sum():.0f} units")

        # --- block aggregation ------------------------------------------------
        agg = aggregate(ok, "block_geoid")
        inside["BLOCKGRPCE20"] = inside.BLOCKCE20.str[0]   # block group = first digit of the block number
        allb = inside[["GEOID20", "TRACTCE20", "BLOCKGRPCE20", "BLOCKCE20", "HOUSING20", "POP20", "ALAND20"]].rename(
            columns={"GEOID20": "block_geoid"})
        out = allb.merge(agg, on="block_geoid", how="left")
        num = [c for c in out.columns if c.startswith(("n_", "units", "bldgs_", "share_"))]
        out[num] = out[num].fillna(0)
        for c in [c for c in out.columns if c.startswith("category")]:
            out[c] = out[c].fillna("no_housing")
        out["bg_geoid"] = out.block_geoid.str[:12]
        out["census_gap_units"] = out.HOUSING20 - out.units
        out["census_gap"] = ((out.census_gap_units >= CENSUS_GAP_MIN_UNITS) &
                             (out.census_gap_units >= CENSUS_GAP_MIN_SHARE * out.HOUSING20))
        st.note(f"blocks with no parcels: {int(out.n_parcels.eq(0).sum())} "
                f"(HOUSING20 in them: {int(out.loc[out.n_parcels.eq(0), 'HOUSING20'].sum())})")
        st.note(f"unit reconciliation: parcels {out.units.sum():.0f} vs census HOUSING20 {int(out.HOUSING20.sum())} "
                f"(ratio {out.units.sum() / out.HOUSING20.sum():.3f}); "
                f"blocks flagged census_gap: {int(out.census_gap.sum())} "
                f"carrying {int(out.loc[out.census_gap, 'census_gap_units'].sum())} unaccounted units")
        top = out.sort_values("census_gap_units", ascending=False).head(12)
        st.note("largest census gaps (block, HOUSING20, parcel units, category): " + "; ".join(
            f"{r.block_geoid} {int(r.HOUSING20)} {r.units:.0f} {r.category}" for _, r in top.iterrows()))
        st.note(f"blocks whose category changes when estimated large-MF units are set to the minimum "
                f"({LARGE_MF_MIN_UNITS}): {int((out.category != out.category_estmin).sum())}")
        for c in ["category", "category_estmin"] + [f"category_sf{int(s*100)}" for s in SF_ONLY_SENSITIVITY]:
            vc = out[c].value_counts()
            st.note(f"{c}: " + ", ".join(f"{k}={int(vc.get(k, 0))}" for k in CATEGORIES))
        for cat in CATEGORIES:
            sub = out[out.category == cat]
            st.note(f"  {cat}: {len(sub)} blocks, {sub.units.sum():.0f} units, HOUSING20 {int(sub.HOUSING20.sum())}, "
                    f"POP20 {int(sub.POP20.sum())}")

        out = out.sort_values("block_geoid").reset_index(drop=True)
        p_csv = os.path.join(INTERIM_DIR, "s05_blocks.csv")
        out.to_csv(p_csv, index=False)
        st.output(p_csv, role="one row per Oak Park block with unit mix and category")
        gj = inside[["GEOID20", "geometry"]].rename(columns={"GEOID20": "block_geoid"}).merge(
            out.drop(columns=["TRACTCE20", "BLOCKGRPCE20", "BLOCKCE20", "ALAND20"]), on="block_geoid")
        gj = gj.sort_values("block_geoid")
        p_gj = os.path.join(INTERIM_DIR, "s05_blocks.geojson")
        gj.to_file(p_gj, driver="GeoJSON")
        st.output(p_gj, role="block polygons with category (for the map)")

        # --- block-group aggregation -------------------------------------------
        bgs = gpd.read_file(bg_shp, mask=poly).to_crs(4326)
        bgs = bgs[bgs.representative_point().within(poly)]
        agg_bg = aggregate(ok, "bg_geoid")
        bgo = bgs[["GEOID"]].rename(columns={"GEOID": "bg_geoid"}).merge(agg_bg, on="bg_geoid", how="left")
        num = [c for c in bgo.columns if c.startswith(("n_", "units", "bldgs_", "share_"))]
        bgo[num] = bgo[num].fillna(0)
        for c in [c for c in bgo.columns if c.startswith("category")]:
            bgo[c] = bgo[c].fillna("no_housing")
        h = out.groupby("bg_geoid")[["HOUSING20", "POP20"]].sum().reset_index()
        bgo = bgo.merge(h, on="bg_geoid", how="left").sort_values("bg_geoid").reset_index(drop=True)
        assert set(bgo.bg_geoid) == set(out.bg_geoid), "block groups and blocks disagree"
        st.note(f"block groups: {len(bgo)}; category: " + ", ".join(
            f"{k}={int((bgo.category == k).sum())}" for k in CATEGORIES))
        p_bg = os.path.join(INTERIM_DIR, "s05_blockgroups.csv")
        bgo.to_csv(p_bg, index=False)
        st.output(p_bg, role="one row per Oak Park block group with unit mix and category")


if __name__ == "__main__":
    main()
