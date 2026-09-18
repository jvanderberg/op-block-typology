"""Stage 12: data file for the interactive explorer (separate repo,
~/git/op-historic-mf, github.com/jvanderberg/op-historic-mf).

Takes the multi-family building table from s10 and writes the two historic
districts of interest (Frank Lloyd Wright, Ridgeland - Oak Park) as a compact
JSON file the Vite app loads at runtime, plus the designation metadata from
config so the app has no hand-typed dates. Every building carries its year
built, unit count, size class (2, 3, 4, 5, 6, 7+), type, zone, year source
and the assessor building id, so a viewer can trace any bar back to parcels.

Output: outputs/explorer_data/mf_buildings.json (the explorer repo copies it
with `npm run data`).
"""
import json
import os

import pandas as pd

from config import HISTORIC_DISTRICTS, INTERIM_DIR, OUT_DIR
from provenance import Stage, sha256_file

EXPLORER_DISTRICTS = ("Frank Lloyd Wright", "Ridgeland - Oak Park")
SIZE_CLASSES = ("2", "3", "4", "5", "6", "7+")


def size_class(units):
    u = int(round(units))
    return "7+" if u >= 7 else str(u)


def main():
    with Stage("s12_explorer_data", __file__) as st:
        st.param(EXPLORER_DISTRICTS=EXPLORER_DISTRICTS, SIZE_CLASSES=SIZE_CLASSES)
        src = os.path.join(INTERIM_DIR, "s10_mf_buildings.csv")
        st.input(src, role="multi-family buildings")
        b = pd.read_csv(src, dtype={"building_id": str, "address": str, "zone": str, "yr_source": str})
        b = b[b.district.isin(EXPLORER_DISTRICTS)].sort_values(["district", "yrblt", "building_id"])
        districts = []
        for name in EXPLORER_DISTRICTS:
            cfg = HISTORIC_DISTRICTS[name]
            districts.append({"name": name, "slug": cfg["slug"], "localYear": cfg["local_year"],
                              "localDate": cfg["local_date"], "localOrdinance": cfg["local_ordinance"],
                              "nrYear": cfg["nr_year"], "nrDate": cfg["nr_date"],
                              "boundaryNote": cfg["boundary_note"], "sensitivityYear": cfg["sensitivity_year"]})
        buildings = []
        for r in b.itertuples(index=False):
            buildings.append({
                "id": r.building_id, "address": r.address if isinstance(r.address, str) else "",
                "district": HISTORIC_DISTRICTS[r.district]["slug"],
                "year": int(r.yrblt) if pd.notna(r.yrblt) else None,
                "units": int(round(r.units)), "size": size_class(r.units),
                "type": r.unit_type, "zone": r.zone if isinstance(r.zone, str) else "",
                "yearSource": r.yr_source, "pins": int(r.n_pins),
            })
        out_obj = {
            "generated": {"stage": "s12_explorer_data", "source": "data/interim/s10_mf_buildings.csv",
                          "sourceSha256": sha256_file(src)},
            "sizeClasses": list(SIZE_CLASSES),
            "districts": districts,
            "buildings": buildings,
        }
        for d in EXPLORER_DISTRICTS:
            s = b[b.district == d]
            st.note(f"{d}: {len(s)} buildings, {s.units.sum():.0f} units, undated {int(s.yrblt.isna().sum())}; "
                    "by size: " + ", ".join(f"{k}={v}" for k, v in
                                            pd.Series([size_class(u) for u in s.units]).value_counts().sort_index().items()))
        out_dir = os.path.join(OUT_DIR, "explorer_data")
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, "mf_buildings.json")
        with open(out, "w") as f:
            json.dump(out_obj, f, indent=0, sort_keys=True)
        st.output(out, role="explorer data (FLW + Ridgeland multi-family buildings)")


if __name__ == "__main__":
    main()
