"""Stage 6: extract 2020 Census race/ethnicity counts for every Oak Park
block, and ACS block-group race estimates, from the fetched files.

2020 P.L. 94-171 (Illinois state file, pipe-delimited, no header row):
  ilgeo2020.pl   geographic header; SUMLEV (col 3) 750 = block, GEOCODE
                 (col 10) = 15-digit block GEOID, LOGRECNO (col 8) links
                 to the data segments.
  il000012020.pl segment 1: 5 link fields, P1 (71 cells), P2 (73 cells).
                 P2 = Hispanic or Latino, and not Hispanic or Latino by race.
  il000022020.pl segment 2: 5 link fields, P3 (71), P4 (73), H1 (3).
                 H1 = housing units: total, occupied, vacant.
  il000032020.pl segment 3: 5 link fields, P5 (10). P5 = group quarters
                 population by major type.
Column positions come from config.py and are verified here three ways:
the state row's P2 total must equal the published Illinois population; every
block's P2 total must equal the TIGER POP20 attribute; every block's H1 total
must equal TIGER HOUSING20 (an exact invariant under the 2020 disclosure
avoidance system).

Race categories kept (P2 cells): total; Hispanic or Latino; not Hispanic:
White alone, Black or African American alone, American Indian and Alaska
Native alone, Asian alone, Native Hawaiian and Other Pacific Islander alone,
Some Other Race alone, Two or More Races.

ACS: table B03002 (same categories, 5-year estimates with 90% margins of
error) per block group, from the Census Reporter snapshot.

Outputs: data/interim/s06_blocks_census2020.csv,
         data/interim/s06_blockgroups_acs.csv
"""
import json
import os

import pandas as pd

from config import (INTERIM_DIR, PL_GEO_GEOCODE_IDX, PL_GEO_LOGRECNO_IDX, PL_GEO_SUMLEV_IDX,
                    PL_H1_FIRST_IDX, PL_P2_FIRST_IDX, PL_SEG_LOGRECNO_IDX, PL_STATE_TOTAL_POP,
                    PL_SUMLEV_BLOCK, RAW_DIR)
from provenance import Stage

# P2 cell offsets (0-based within P2) -> output column.
P2_CELLS = {0: "pop", 1: "hispanic", 4: "nh_white", 5: "nh_black", 6: "nh_aian",
            7: "nh_asian", 8: "nh_nhpi", 9: "nh_other", 10: "nh_two_plus"}
P5_FIRST_IDX = 5            # segment 3: P0050001 is the first data cell
P5_CELLS = {0: "gq_total", 1: "gq_institutional", 5: "gq_noninstitutional"}
# B03002 column suffix -> output column (same categories as P2).
ACS_CELLS = {"001": "pop", "012": "hispanic", "003": "nh_white", "004": "nh_black",
             "005": "nh_aian", "006": "nh_asian", "007": "nh_nhpi", "008": "nh_other",
             "009": "nh_two_plus"}


def read_pl_blocks(st, wanted):
    geo = os.path.join(RAW_DIR, "pl", "ilgeo2020.pl")
    seg1 = os.path.join(RAW_DIR, "pl", "il000012020.pl")
    seg2 = os.path.join(RAW_DIR, "pl", "il000022020.pl")
    seg3 = os.path.join(RAW_DIR, "pl", "il000032020.pl")
    for p in (geo, seg1, seg2, seg3):
        st.input(p, role="2020 P.L. 94-171 Illinois")
    logrec = {}
    state_logrec = None
    with open(geo, encoding="latin-1") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            if parts[PL_GEO_SUMLEV_IDX] == "040":
                state_logrec = parts[PL_GEO_LOGRECNO_IDX]
            if parts[PL_GEO_SUMLEV_IDX] == PL_SUMLEV_BLOCK and parts[PL_GEO_GEOCODE_IDX] in wanted:
                logrec[parts[PL_GEO_LOGRECNO_IDX]] = parts[PL_GEO_GEOCODE_IDX]
    st.note(f"geo header: matched {len(logrec)} of {len(wanted)} wanted blocks; state LOGRECNO {state_logrec}")
    assert len(logrec) == len(wanted), "some Oak Park blocks are missing from the PL geo header"
    rows = {g: {"block_geoid": g} for g in logrec.values()}
    with open(seg1, encoding="latin-1") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            lr = parts[PL_SEG_LOGRECNO_IDX]
            if lr == state_logrec:
                tot = int(parts[PL_P2_FIRST_IDX])
                assert tot == PL_STATE_TOTAL_POP, f"P2 column check failed: state P2 total {tot}"
                st.note(f"layout check: state P2_001 = {tot} = published Illinois 2020 population")
            if lr in logrec:
                for off, col in P2_CELLS.items():
                    rows[logrec[lr]][col] = int(parts[PL_P2_FIRST_IDX + off])
    with open(seg2, encoding="latin-1") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            lr = parts[PL_SEG_LOGRECNO_IDX]
            if lr in logrec:
                rows[logrec[lr]]["hu_total"] = int(parts[PL_H1_FIRST_IDX])
                rows[logrec[lr]]["hu_occupied"] = int(parts[PL_H1_FIRST_IDX + 1])
                rows[logrec[lr]]["hu_vacant"] = int(parts[PL_H1_FIRST_IDX + 2])
    with open(seg3, encoding="latin-1") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            lr = parts[PL_SEG_LOGRECNO_IDX]
            if lr in logrec:
                for off, col in P5_CELLS.items():
                    rows[logrec[lr]][col] = int(parts[P5_FIRST_IDX + off])
    df = pd.DataFrame(sorted(rows.values(), key=lambda r: r["block_geoid"]))
    parts_sum = df[["hispanic", "nh_white", "nh_black", "nh_aian", "nh_asian", "nh_nhpi",
                    "nh_other", "nh_two_plus"]].sum(axis=1)
    assert (parts_sum == df["pop"]).all(), "P2 categories do not sum to P2 total"
    assert (df.hu_occupied + df.hu_vacant == df.hu_total).all(), "H1 cells do not sum"
    assert (df.gq_total <= df["pop"]).all(), "group quarters exceed population"
    return df


def read_acs(st):
    path = os.path.join(RAW_DIR, "censusreporter_acs_bg.json")
    st.input(path, role="ACS block-group tables (Census Reporter snapshot)")
    with open(path) as f:
        obj = json.load(f)
    rel = obj["release"]
    st.note(f"ACS release: {rel['id']} ({rel['name']}, {rel['years']})")
    rows = []
    for geo, tables in sorted(obj["data"].items()):
        assert geo.startswith("15000US"), geo
        t = tables["B03002"]
        r = {"bg_geoid": geo[7:], "acs_release": rel["id"]}
        for suf, col in ACS_CELLS.items():
            r[col] = t["estimate"]["B03002" + suf]
            r[col + "_moe"] = t["error"]["B03002" + suf]
        rows.append(r)
    df = pd.DataFrame(rows)
    parts_sum = df[[c for c in ACS_CELLS.values() if c != "pop"]].sum(axis=1)
    assert (parts_sum == df["pop"]).all(), "B03002 categories do not sum to total"
    return df


def main():
    with Stage("s06_census", __file__) as st:
        s05 = os.path.join(INTERIM_DIR, "s05_blocks.csv")
        st.input(s05, role="Oak Park block list with TIGER POP20/HOUSING20")
        blocks = pd.read_csv(s05, dtype={"block_geoid": str, "bg_geoid": str})
        wanted = set(blocks.block_geoid)
        pl = read_pl_blocks(st, wanted)
        chk = blocks[["block_geoid", "POP20", "HOUSING20"]].merge(pl, on="block_geoid")
        assert len(chk) == len(blocks)
        bad_pop = int((chk.POP20 != chk["pop"]).sum())
        bad_hu = int((chk.HOUSING20 != chk.hu_total).sum())
        st.note(f"cross-check vs TIGER attributes: POP20 mismatches {bad_pop}, HOUSING20 mismatches {bad_hu}")
        assert bad_pop == 0 and bad_hu == 0, "PL block counts disagree with TIGER"
        st.note(f"Oak Park 2020: population {pl['pop'].sum()}, housing units {pl.hu_total.sum()} "
                f"({pl.hu_occupied.sum()} occupied), group quarters population {pl.gq_total.sum()} "
                f"in {(pl.gq_total > 0).sum()} blocks")
        tot = pl["pop"].sum()
        st.note("village race shares 2020: " + ", ".join(
            f"{c} {pl[c].sum() / tot:.1%}" for c in ("nh_white", "nh_black", "hispanic", "nh_asian", "nh_two_plus")))
        out = os.path.join(INTERIM_DIR, "s06_blocks_census2020.csv")
        pl.to_csv(out, index=False)
        st.output(out, role="2020 Census P2/H1/P5 per Oak Park block")

        acs = read_acs(st)
        bgs = set(blocks.bg_geoid)
        assert set(acs.bg_geoid) == bgs, f"ACS block groups differ from TIGER: {set(acs.bg_geoid) ^ bgs}"
        st.note(f"ACS block groups: {len(acs)}; population estimate {acs['pop'].sum():.0f}")
        out2 = os.path.join(INTERIM_DIR, "s06_blockgroups_acs.csv")
        acs.to_csv(out2, index=False)
        st.output(out2, role="ACS B03002 per Oak Park block group, with MOE")


if __name__ == "__main__":
    main()
