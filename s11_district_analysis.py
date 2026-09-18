"""Stage 11: multi-family construction before and after historic-district
designation.

For each district, and for the rest of Oak Park as a comparison, count the
multi-family buildings and units still standing in 2026 by the year they
were built, and compare the period before the Village's local designation
with the period after it. Two framings are given:

  * by decade built (Table G), so the pre-designation collapse of apartment
    construction in the 1930s is visible and not mistaken for a district effect;
  * equal-length windows (Table H): the N years after designation (through
    2025) against the N years immediately before it, for the district and
    for the rest of the village over the same calendar years, with units per
    year and the district's share of village-wide construction in each window.

Sensitivity (Table H2): the same windows with each district's alternative
date from config (FLW 2012 local expansion; Ridgeland 1983 National Register).
Table I lists every multi-family building built after local designation.
Table J gives each district's area by zoning district.

Caveats carried into the results: the assessor's roll holds only buildings
standing in 2026 (anything demolished is missing from the "before" counts);
year built is the assessor's figure and is approximate for older buildings;
buildings with no obtainable year are reported separately.

Outputs: outputs/tables/G_*.csv .. J_*.csv, outputs/fig_mf_by_decade.png,
outputs/results_districts.md
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from config import (CATEGORY_COLORS, DECADE_END, DECADE_START, HISTORIC_DISTRICTS, INTERIM_DIR,  # noqa: E402
                    MF_ZONES, OUT_DIR)
from provenance import Stage  # noqa: E402

TABLE_DIR = os.path.join(OUT_DIR, "tables")
END_YEAR = 2025
AREAS = list(HISTORIC_DISTRICTS) + ["Rest of Oak Park"]


def window(b, area, y0, y1):
    s = b[(b.district == area) & (b.yrblt >= y0) & (b.yrblt <= y1)]
    return len(s), float(s.units.sum())


def windows_table(b, year_of):
    rows = []
    for d, cut in year_of.items():
        n = END_YEAR - cut + 1
        before = (cut - n, cut - 1)
        after = (cut, END_YEAR)
        rest = "Rest of Oak Park"
        db_, ub = window(b, d, *before)
        da, ua = window(b, d, *after)
        rb, rub = window(b, rest, *before)
        ra, rua = window(b, rest, *after)
        vb, vub = window(b[b.district != d].assign(district="x"), "x", *before)
        va, vua = window(b[b.district != d].assign(district="x"), "x", *after)
        unk = b[(b.district == d) & b.yrblt.isna()]
        rows.append({
            "district": d, "designated": cut, "window_years": n,
            "before": f"{before[0]}-{before[1]}", "after": f"{after[0]}-{after[1]}",
            "bldgs_before": db_, "units_before": ub, "bldgs_after": da, "units_after": ua,
            "units_per_year_before": round(ub / n, 2), "units_per_year_after": round(ua / n, 2),
            "rest_units_before": rub, "rest_units_after": rua,
            "rest_units_per_year_before": round(rub / n, 2), "rest_units_per_year_after": round(rua / n, 2),
            "district_share_of_village_units_before": round(100 * ub / (ub + vub), 1) if ub + vub else None,
            "district_share_of_village_units_after": round(100 * ua / (ua + vua), 1) if ua + vua else None,
            "bldgs_undated": len(unk), "units_undated": float(unk.units.sum()),
        })
    return pd.DataFrame(rows).set_index("district")


def md(df, cols, fmt=None):
    fmt = fmt or {}
    lines = ["| " + " | ".join([df.index.name or ""] + list(cols.values())) + " |", "|" + "---|" * (len(cols) + 1)]
    for idx, r in df.iterrows():
        cells = [str(idx)]
        for c in cols:
            v = r[c]
            if pd.isna(v):
                cells.append("")
            elif c in fmt:
                cells.append(fmt[c].format(v))
            elif isinstance(v, float) and float(v).is_integer():
                cells.append(f"{int(v):,}" if c not in ("designated",) else str(int(v)))
            elif isinstance(v, float):
                cells.append(f"{v:.1f}")
            elif isinstance(v, int):
                cells.append(f"{v:,}" if c not in ("designated",) else str(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    with Stage("s11_district_analysis", __file__) as st:
        st.param(END_YEAR=END_YEAR, designation_years={k: v["local_year"] for k, v in HISTORIC_DISTRICTS.items()},
                 sensitivity_years={k: v["sensitivity_year"] for k, v in HISTORIC_DISTRICTS.items()})
        p_b = os.path.join(INTERIM_DIR, "s10_mf_buildings.csv")
        p_ctx = os.path.join(INTERIM_DIR, "s10_district_parcels.csv")
        p_z = os.path.join(INTERIM_DIR, "s10_district_zoning.csv")
        for p, r in ((p_b, "MF buildings"), (p_ctx, "units by district"), (p_z, "district zoning")):
            st.input(p, role=r)
        b_all = pd.read_csv(p_b, dtype={"building_id": str, "zone": str, "address": str})
        excluded = b_all[b_all.excluded].copy()
        b = b_all[~b_all.excluded].copy()
        st.note(f"buildings: {len(b_all)}; excluded condo conversions: {len(excluded)} ({excluded.units.sum():.0f} units); analysed: {len(b)}")
        ctx = pd.read_csv(p_ctx)
        dz = pd.read_csv(p_z)
        os.makedirs(TABLE_DIR, exist_ok=True)
        tables = {}

        # G: by decade
        b["decade"] = (b.yrblt // 10 * 10).where(b.yrblt.notna()).astype("Int64")
        decades = list(range(DECADE_START, DECADE_END, 10))
        g_units = b.pivot_table(index="district", columns="decade", values="units", aggfunc="sum").reindex(AREAS)
        g_bldgs = b.pivot_table(index="district", columns="decade", values="units", aggfunc="size").reindex(AREAS)
        for t in (g_units, g_bldgs):
            for d in decades:
                if d not in t.columns:
                    t[d] = 0.0
        g_units = g_units[decades].fillna(0)
        g_bldgs = g_bldgs[decades].fillna(0)
        g_units["undated"] = b[b.yrblt.isna()].groupby("district").units.sum().reindex(AREAS).fillna(0)
        g_bldgs["undated"] = b[b.yrblt.isna()].groupby("district").size().reindex(AREAS).fillna(0)
        g_units["total"] = b.groupby("district").units.sum().reindex(AREAS)
        g_bldgs["total"] = b.groupby("district").size().reindex(AREAS)
        g_units.columns = [f"{int(c)}s" if not isinstance(c, str) else c for c in g_units.columns]
        g_bldgs.columns = [f"{int(c)}s" if not isinstance(c, str) else c for c in g_bldgs.columns]
        g_units.index.name = g_bldgs.index.name = "district"
        tables["G1_mf_units_by_decade_built"] = g_units
        tables["G2_mf_buildings_by_decade_built"] = g_bldgs

        # H: equal-length windows
        H = windows_table(b, {k: v["local_year"] for k, v in HISTORIC_DISTRICTS.items()})
        H2 = windows_table(b, {k: v["sensitivity_year"] for k, v in HISTORIC_DISTRICTS.items()})
        tables["H1_before_after_local_designation"] = H
        tables["H2_before_after_sensitivity_dates"] = H2

        # I: buildings built after local designation
        rows = []
        for d, cfg in HISTORIC_DISTRICTS.items():
            s = b[(b.district == d) & (b.yrblt >= cfg["local_year"])].sort_values(["yrblt", "address"])
            for _, r in s.iterrows():
                rows.append({"district": d, "designated": cfg["local_year"], "yrblt": int(r.yrblt), "address": r.address,
                             "units": r.units, "type": r.unit_type, "zone": r.zone, "yr_source": r.yr_source,
                             "building_id": r.building_id})
        I = pd.DataFrame(rows)
        tables["I_mf_built_after_designation"] = I.set_index("district") if len(I) else I

        # J: zoning
        dz["mf_zone"] = dz.zone.isin(MF_ZONES)
        J = dz.pivot_table(index="district", columns="zone", values="share", aggfunc="sum").fillna(0).round(3) * 100
        J["mf_zones_R5_R6_R7"] = dz[dz.mf_zone].groupby("district").share.sum().reindex(J.index).fillna(0) * 100
        J = J.round(1)
        tables["J_district_area_by_zoning"] = J

        # context: units by bucket
        K = ctx.pivot_table(index="district", columns="bucket", values="units", aggfunc="sum").reindex(AREAS).fillna(0)
        K["total"] = K.sum(axis=1)
        for c in ("sf", "small_mf", "large_mf"):
            K["pct_" + c] = (100 * K[c] / K.total).round(1)
        tables["K_district_housing_units_by_type_2026"] = K
        L = excluded.sort_values(["district", "address"])[["district", "address", "units", "yrblt", "yr_predecessor", "zone"]].rename(
            columns={"yrblt": "recorded_condo_year", "yr_predecessor": "predecessor_year_built"})
        tables["L_excluded_condo_conversions"] = L.set_index("district") if len(L) else L

        for name, t in tables.items():
            p = os.path.join(TABLE_DIR, name + ".csv")
            t.to_csv(p)
            st.output(p, role="table " + name)

        for d in AREAS:
            r = H.loc[d] if d in H.index else None
            if r is not None:
                st.note(f"{d}: designated {int(r.designated)}; {int(r.window_years)}-yr windows: before {int(r.bldgs_before)} bldgs/"
                        f"{r.units_before:.0f} units, after {int(r.bldgs_after)} bldgs/{r.units_after:.0f} units; rest of village "
                        f"before {r.rest_units_before:.0f}, after {r.rest_units_after:.0f}; undated {int(r.bldgs_undated)} bldgs/"
                        f"{r.units_undated:.0f} units")

        # ---- figure: units by decade, small multiples ------------------------
        fig, axes = plt.subplots(2, 2, figsize=(11, 7), facecolor="#fcfcfb", sharex=True)
        colors = {"Frank Lloyd Wright": "#2a78d6", "Ridgeland - Oak Park": "#eb6834", "Gunderson": "#1baf7a",
                  "Rest of Oak Park": "#4a3aa7"}
        for ax, d in zip(axes.flat, AREAS):
            vals = [g_units.loc[d, f"{x}s"] for x in decades]
            ax.bar([f"{x}s" for x in decades], vals, color=colors[d], width=0.7, edgecolor="#fcfcfb", linewidth=1)
            title = d
            if d in HISTORIC_DISTRICTS:
                cut = HISTORIC_DISTRICTS[d]["local_year"]
                xi = (cut - DECADE_START) / 10 - 0.5
                ax.axvline(xi, color="#0b0b0b", linewidth=1.2, linestyle="--")
                ax.text(xi + 0.15, ax.get_ylim()[1] * 0.92 if max(vals) else 1, f"designated {cut}", fontsize=9, color="#0b0b0b")
                title = f"{d} (local district {cut})"
            ax.set_title(title, loc="left", fontsize=11)
            ax.set_facecolor("#fcfcfb")
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            ax.tick_params(axis="x", rotation=60, labelsize=8, colors="#52514e")
            ax.tick_params(axis="y", colors="#52514e")
            ax.set_ylabel("units built", color="#52514e")
        fig.suptitle("Multi-family units still standing in 2026, by decade built (Cook County Assessor)", x=0.02, ha="left", fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        p_fig = os.path.join(OUT_DIR, "fig_mf_by_decade.png")
        fig.savefig(p_fig, dpi=160, metadata={"Software": None})
        plt.close(fig)
        st.output(p_fig, role="figure: MF units by decade built per district")

        # ---- results_districts.md -------------------------------------------
        dec_cols = {f"{x}s": f"{x}s" for x in decades if x >= 1890}
        pre1890 = {f"{x}s" for x in decades if x < 1890}
        G1 = g_units.copy()
        G1["pre-1890"] = G1[[c for c in G1.columns if c in pre1890]].sum(axis=1)
        G1cols = {"pre-1890": "pre-1890", **dec_cols, "undated": "undated", "total": "total"}
        lines = [
            "# Multi-family construction before and after historic-district designation, Oak Park",
            "",
            "Every number here is produced by `s10_districts.py` and `s11_district_analysis.py` from the",
            "Cook County Assessor's 2026 roll and the Village's GIS boundaries; lineage in PROVENANCE.md.",
            "",
            "## Districts and dates",
            "",
            "| District | Local designation (regulatory) | National Register | Note |",
            "|---|---|---|---|",
        ]
        for d, cfg in HISTORIC_DISTRICTS.items():
            lines.append(f"| {d} | {cfg['local_date']}" + (f" (Ord. {cfg['local_ordinance']})" if cfg['local_ordinance'] else "")
                         + f" | {cfg['nr_date']} | {cfg['boundary_note']} |")
        lines += [
            "",
            "Sources for the dates are listed in `config.py` (Village Code 7-9-3; Village district",
            "brochures and nomination report; Wednesday Journal 2014-11-25; Patch 2011-03-22; NRHP).",
            "Local designation is what brings demolition and exterior-alteration review; the National",
            "Register listing itself carries no control over private owners.",
            "",
            "## What counts",
            "",
            "A multi-family building has two or more dwelling units in one structure: 2-6 unit buildings,",
            "7+ unit buildings, and condominium buildings (counted as buildings, by the year the structure",
            "was built, whatever its tenure today). Townhomes are excluded. A building belongs to a district",
            "when its parcel's representative point lies inside the Village's district polygon. Only",
            "buildings standing on the 2026 assessment roll are visible: anything demolished is absent.",
            "",
            "## Housing units by district today (2026 roll)",
            "",
            md(K, {"total": "Units", "pct_sf": "% single-family", "pct_small_mf": "% in 2-6 unit bldgs",
                   "pct_large_mf": "% in 7+ unit bldgs"}),
            "",
            "## G. Multi-family units by decade built",
            "",
            md(G1, G1cols),
            "",
            "Buildings:",
            "",
            md(g_bldgs.assign(**{"pre-1890": g_bldgs[[c for c in g_bldgs.columns if c in pre1890]].sum(axis=1)}), G1cols),
            "",
            "![MF units by decade](fig_mf_by_decade.png)",
            "",
            "## H. Before and after local designation, equal-length windows",
            "",
            "The window after designation runs to 2025; the window before is the same number of years",
            "immediately preceding it. \"Rest of Oak Park\" is everything outside all three districts, over",
            "the same calendar years. \"Share\" is the district's share of all multi-family units built",
            "village-wide in that window.",
            "",
            md(H, {"designated": "Designated", "before": "Before", "after": "After",
                   "bldgs_before": "Bldgs before", "units_before": "Units before",
                   "bldgs_after": "Bldgs after", "units_after": "Units after",
                   "units_per_year_before": "Units/yr before", "units_per_year_after": "Units/yr after",
                   "rest_units_per_year_before": "Rest of OP units/yr before", "rest_units_per_year_after": "Rest of OP units/yr after",
                   "district_share_of_village_units_before": "Share before (%)", "district_share_of_village_units_after": "Share after (%)",
                   "units_undated": "Units undated"}),
            "",
            "Sensitivity, alternative dates (FLW 2012 local boundary expansion; Ridgeland 1983 National Register; Gunderson 2003 expansion):",
            "",
            md(H2, {"designated": "Cut year", "before": "Before", "after": "After", "units_before": "Units before",
                    "units_after": "Units after", "units_per_year_before": "Units/yr before", "units_per_year_after": "Units/yr after",
                    "rest_units_per_year_before": "Rest of OP units/yr before", "rest_units_per_year_after": "Rest of OP units/yr after",
                    "district_share_of_village_units_before": "Share before (%)", "district_share_of_village_units_after": "Share after (%)"}),
            "",
            "## I. Every multi-family building built after local designation",
            "",
        ]
        if len(I):
            lines.append("| District | Built | Address | Units | Type | Zone | Year source |")
            lines.append("|---|---|---|---|---|---|---|")
            for _, r in I.iterrows():
                lines.append(f"| {r.district} | {r.yrblt} | {r.address} | {r.units:.0f} | {r.type} | {r.zone} | {r.yr_source} |")
        else:
            lines.append("None.")
        lines += [
            "",
            "## J. District area by zoning district (share of land, %)",
            "",
            md(J, {c: c for c in J.columns}),
            "",
            "## Excluded condominium conversions",
            "",
            "The Assessor's condominium file records the year the units were declared, not the year",
            "the structure was built, for buildings converted to condominiums. These buildings were",
            "identified by finding the predecessor parcel (same assessor block, present the year before",
            "the units appear, absent after) with a residential or apartment class, and are excluded",
            "from every table above. The predecessor's own year built is shown where the Assessor",
            "recorded one.",
            "",
        ]
        if len(L):
            lines.append("| District | Address | Units | Recorded condo year | Predecessor built | Zone |")
            lines.append("|---|---|---|---|---|---|")
            for d, r in L.iterrows():
                py = "" if pd.isna(r.predecessor_year_built) else str(int(r.predecessor_year_built))
                lines.append(f"| {d} | {r.address} | {r.units:.0f} | {int(r.recorded_condo_year)} | {py} | {r.zone} |")
        else:
            lines.append("None.")
        lines += [
            "",
            "## Undated buildings",
            "",
        ]
        unk = b[b.yrblt.isna()]
        if len(unk):
            lines.append("| District | Address | Units | Type | Classes |")
            lines.append("|---|---|---|---|---|")
            for _, r in unk.sort_values(["district", "units"], ascending=[True, False]).iterrows():
                lines.append(f"| {r.district} | {r.address} | {r.units:.0f} | {r.unit_type} | {r.classes} |")
        else:
            lines.append("None.")
        lines += ["", "## Caveats", "",
                  "- Survivorship: the assessor's roll lists only buildings standing in 2026. Multi-family buildings",
                  "  demolished before or after designation are not counted anywhere.",
                  "- Year built is the assessor's figure. For buildings dated from the class history (completed",
                  "  2020 or later) it is the year before the PIN first carried a residential class.",
                  "- The Frank Lloyd Wright polygon is the boundary as expanded in 2009/2012; the 1972 boundary is",
                  "  smaller (1,491 of about 1,935 parcels). The sensitivity row with 2012 bounds this.",
                  "- Condominium buildings converted from existing buildings are excluded (see above); the",
                  "  remaining condominium buildings are dated by the Assessor's condominium file.",
                  ""]
        p_md = os.path.join(OUT_DIR, "results_districts.md")
        with open(p_md, "w") as f:
            f.write("\n".join(lines))
        st.output(p_md, role="district results narrative")
        p_json = os.path.join(OUT_DIR, "results_districts.json")
        with open(p_json, "w") as f:
            json.dump({k: json.loads(v.reset_index().to_json(orient="records")) for k, v in tables.items() if len(v)},
                      f, indent=1, sort_keys=True)
        st.output(p_json, role="district tables as JSON")


if __name__ == "__main__":
    main()
