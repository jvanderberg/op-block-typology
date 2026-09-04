"""Stage 7: total the 2020 Census race/ethnicity counts by block type.

No single block is reported. Every table sums whole categories of blocks
(hundreds of blocks, thousands of people), which is also what makes the
2020 disclosure-avoidance noise tolerable: block-level noise is independent
across blocks and largely cancels in sums, and it cancels exactly where a
category covers whole block groups.

Tables (outputs/tables/*.csv, and outputs/results.md):
  A  race composition by block type, 2020 Census, all Oak Park blocks
  A2 same, excluding blocks whose population is mostly group quarters
  B  where each group lives: distribution of each race group across block types
  C  sensitivity: the single-family cutoff at 100% and 90% instead of 95%
  D  block groups classified by their own unit mix: 2020 counts and ACS
     2020-2024 estimates (with 90% margins of error)
  E  within-block-group contrast: only block groups that contain more than
     one block type, so the comparison holds neighbourhood constant
  F  housing-unit mix behind each block type (parcel-derived)
Figures: outputs/fig_race_by_block_type.png, outputs/fig_where_groups_live.png
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from config import (CATEGORIES, CATEGORY_LABELS, GQ_MAX_SHARE, INTERIM_DIR, OUT_DIR,  # noqa: E402
                    RACE_COLORS, RACE_FOLD_INTO_OTHER, RACE_GROUPS, SF_ONLY_MIN_SHARE,
                    SF_ONLY_SENSITIVITY)
from provenance import Stage  # noqa: E402

TABLE_DIR = os.path.join(OUT_DIR, "tables")
RACE_COLS = [c for c, _ in RACE_GROUPS]
RACE_LABEL = dict(RACE_GROUPS)
ORDER = [c for c in CATEGORIES if c != "no_housing"]


def fold(df):
    """Fold AIAN, NHPI and 'some other race' into nh_other (and their MOEs)."""
    df = df.copy()
    df["nh_other"] = df[list(RACE_FOLD_INTO_OTHER)].sum(axis=1)
    if "nh_other_moe" in df.columns:
        df["nh_other_moe"] = (df[[c + "_moe" for c in RACE_FOLD_INTO_OTHER]] ** 2).sum(axis=1) ** 0.5
    return df


def composition(df, by, pop="pop", extra_sums=()):
    g = df.groupby(by)
    out = pd.DataFrame({"n_blocks": g.size(), "pop_2020": g[pop].sum()})
    for c in extra_sums:
        out[c] = g[c].sum()
    for c in RACE_COLS:
        out[c] = g[c].sum()
        out["pct_" + c] = (100 * out[c] / out["pop_2020"]).round(1)
    for c in extra_sums:
        out[c] = out[c].round(0)
    tot = df.sum(numeric_only=True)
    total = {"n_blocks": len(df), "pop_2020": tot[pop]}
    for c in extra_sums:
        total[c] = round(tot[c])
    for c in RACE_COLS:
        total[c] = tot[c]
        total["pct_" + c] = round(100 * tot[c] / tot[pop], 1)
    out.loc["all_blocks"] = pd.Series(total)
    out = out.reindex([c for c in ORDER + ["no_housing", "all_blocks"] if c in out.index])
    out.index.name = "category"
    return out


def distribution(df, by):
    """Share of each race group's village total that lives in each block type."""
    g = df.groupby(by)[RACE_COLS + ["pop"]].sum()
    g = g.reindex([c for c in ORDER + ["no_housing"] if c in g.index])
    d = (100 * g / g.sum()).round(1)
    d.columns = ["pct_of_" + c for c in d.columns]
    d.insert(0, "pop_2020", g["pop"])
    d.index.name = "category"
    return d


def acs_composition(bg):
    g = bg.groupby("category")
    out = pd.DataFrame({"n_block_groups": g.size(), "pop_acs": g["pop"].sum(),
                        "pop_acs_moe": (g["pop_moe"].apply(lambda s: (s ** 2).sum() ** 0.5))})
    for c in RACE_COLS:
        out[c] = g[c].sum()
        out[c + "_moe"] = g[c + "_moe"].apply(lambda s: (s ** 2).sum() ** 0.5)
        p = out[c] / out["pop_acs"]
        # Census Bureau approximation for the MOE of a proportion.
        inner = out[c + "_moe"] ** 2 - (p ** 2) * out["pop_acs_moe"] ** 2
        inner = inner.where(inner > 0, out[c + "_moe"] ** 2 + (p ** 2) * out["pop_acs_moe"] ** 2)
        out["pct_" + c] = (100 * p).round(1)
        out["pct_" + c + "_moe"] = (100 * inner ** 0.5 / out["pop_acs"]).round(1)
    out = out.reindex([c for c in ORDER if c in out.index])
    out.index.name = "category"
    return out


def md_table(df, cols, fmt=None):
    fmt = fmt or {}
    lines = ["| " + " | ".join(["category"] + [cols[c] for c in cols]) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for idx, r in df.iterrows():
        cells = [CATEGORY_LABELS.get(idx, str(idx).replace("_", " "))]
        for c in cols:
            v = r[c]
            if pd.isna(v):
                cells.append("")
            elif c in fmt:
                cells.append(fmt[c].format(v))
            elif isinstance(v, float) and not float(v).is_integer():
                cells.append(f"{v:.1f}")
            else:
                cells.append(f"{int(v):,}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def stacked_bar(ax, table, title):
    rows = [c for c in ORDER + ["all_blocks"] if c in table.index]
    labels = [CATEGORY_LABELS.get(r, "All Oak Park") for r in rows]
    left = [0.0] * len(rows)
    for col, color in zip(RACE_COLS, RACE_COLORS):
        vals = [table.loc[r, "pct_" + col] for r in rows]
        bars = ax.barh(labels, vals, left=left, color=color, height=0.55,
                       edgecolor="#fcfcfb", linewidth=2, label=RACE_LABEL[col])
        for b, v in zip(bars, vals):
            if v >= 6:
                ax.text(b.get_x() + b.get_width() / 2, b.get_y() + b.get_height() / 2,
                        f"{v:.0f}%", ha="center", va="center", fontsize=9, color="#0b0b0b")
        left = [l + v for l, v in zip(left, vals)]
    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    ax.set_xlabel("Share of 2020 population (%)", color="#52514e")
    ax.set_title(title, loc="left", fontsize=12, color="#0b0b0b")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#d9d8d3")
    ax.tick_params(colors="#52514e", length=0)
    ax.set_facecolor("#fcfcfb")


def main():
    with Stage("s07_analyze", __file__) as st:
        st.param(SF_ONLY_MIN_SHARE=SF_ONLY_MIN_SHARE, SF_ONLY_SENSITIVITY=SF_ONLY_SENSITIVITY,
                 GQ_MAX_SHARE=GQ_MAX_SHARE)
        os.makedirs(TABLE_DIR, exist_ok=True)
        p_blocks = os.path.join(INTERIM_DIR, "s05_blocks.csv")
        p_cen = os.path.join(INTERIM_DIR, "s06_blocks_census2020.csv")
        p_bg = os.path.join(INTERIM_DIR, "s05_blockgroups.csv")
        p_acs = os.path.join(INTERIM_DIR, "s06_blockgroups_acs.csv")
        for p, r in ((p_blocks, "block typology"), (p_cen, "2020 block counts"),
                     (p_bg, "block-group typology"), (p_acs, "ACS block-group race")):
            st.input(p, role=r)
        blocks = pd.read_csv(p_blocks, dtype={"block_geoid": str, "bg_geoid": str})
        cen = fold(pd.read_csv(p_cen, dtype={"block_geoid": str}))
        df = blocks.merge(cen, on="block_geoid", how="inner")
        assert len(df) == len(blocks) == len(cen), "block join lost rows"
        assert (df["pop"] == df.POP20).all()
        df["gq_share"] = (df.gq_total / df["pop"]).where(df["pop"] > 0, 0.0)
        df["gq_heavy"] = df.gq_share > GQ_MAX_SHARE
        st.note(f"blocks: {len(df)}; population {df['pop'].sum()}; group-quarters-heavy blocks "
                f"(> {GQ_MAX_SHARE:.0%} GQ): {int(df.gq_heavy.sum())} with {int(df.loc[df.gq_heavy, 'pop'].sum())} people")

        tables, results = {}, {}
        # A: headline composition by block type.
        A = composition(df, "category", extra_sums=("hu_total", "hu_occupied", "units"))
        tables["A_race_by_block_type_2020"] = A
        A2 = composition(df[~df.gq_heavy], "category", extra_sums=("hu_total",))
        tables["A2_race_by_block_type_2020_excl_gq"] = A2
        # B: where each group lives.
        B = distribution(df, "category")
        tables["B_where_each_group_lives_2020"] = B
        # C: sensitivity to the single-family cutoff.
        for s in SF_ONLY_SENSITIVITY:
            col = f"category_sf{int(s * 100)}"
            tables[f"C_sensitivity_sf{int(s * 100)}"] = composition(df, col, extra_sums=("hu_total",))
        tables["C_sensitivity_estimated_units_min"] = composition(df, "category_estmin", extra_sums=("hu_total",))
        st.note(f"blocks reclassified when estimated large-MF units are set to the minimum: "
                f"{int((df.category != df.category_estmin).sum())}")
        # D: block groups classified by their own mix.
        bg = pd.read_csv(p_bg, dtype={"bg_geoid": str})
        acs = fold(pd.read_csv(p_acs, dtype={"bg_geoid": str}))
        bgc = df.groupby("bg_geoid")[RACE_COLS + ["pop", "hu_total"]].sum().reset_index()
        bg2 = bg.merge(bgc, on="bg_geoid").rename(columns={"category": "category"})
        D1 = composition(bg2.assign(n=1), "category", extra_sums=("hu_total", "units"))
        D1 = D1.rename(columns={"n_blocks": "n_block_groups"})
        tables["D1_block_groups_2020"] = D1
        D2 = acs_composition(bg.merge(acs, on="bg_geoid"))
        tables["D2_block_groups_acs_2020_2024"] = D2
        st.note("block-group categories: " + ", ".join(f"{k}={int((bg.category == k).sum())}" for k in CATEGORIES))
        # E: within-block-group contrast.
        multi = df.groupby("bg_geoid")["category"].transform(lambda s: s[s != "no_housing"].nunique()) > 1
        sub = df[multi & (df.category != "no_housing")]
        E = composition(sub, "category", extra_sums=("hu_total",))
        E["n_block_groups"] = sub.groupby("category")["bg_geoid"].nunique()
        E.loc["all_blocks", "n_block_groups"] = sub.bg_geoid.nunique()
        tables["E_within_block_group_contrast_2020"] = E
        # Paired version: mean difference in each group's share between
        # single-family blocks and every other housing block type inside the
        # same block group, weighted by the smaller of the two populations.
        pairs = []
        for g, grp in sub.groupby("bg_geoid"):
            sf = grp[grp.category == "single_family"]
            if sf.empty or sf["pop"].sum() == 0:
                continue
            for cat in ("small_mf_2_6", "large_mf_7plus", "mixed"):
                o = grp[grp.category == cat]
                if o.empty or o["pop"].sum() == 0:
                    continue
                w = min(sf["pop"].sum(), o["pop"].sum())
                rec = {"bg_geoid": g, "vs": cat, "weight": w}
                for c in RACE_COLS:
                    rec["diff_" + c] = 100 * (o[c].sum() / o["pop"].sum() - sf[c].sum() / sf["pop"].sum())
                pairs.append(rec)
        pairs = pd.DataFrame(pairs)
        rows = []
        for cat, grp in pairs.groupby("vs"):
            r = {"category": cat, "n_pairs": len(grp), "weight": grp.weight.sum()}
            for c in RACE_COLS:
                r["diff_pct_" + c] = round((grp["diff_" + c] * grp.weight).sum() / grp.weight.sum(), 1)
            rows.append(r)
        E2 = pd.DataFrame(rows).set_index("category").reindex(["small_mf_2_6", "large_mf_7plus", "mixed"])
        tables["E2_paired_difference_vs_single_family_2020"] = E2
        # F: housing mix behind each block type.
        F = df.groupby("category").agg(n_blocks=("block_geoid", "size"), units_parcels=("units", "sum"),
                                       units_sf=("units_sf", "sum"), units_small_mf=("units_small_mf", "sum"),
                                       units_large_mf=("units_large_mf", "sum"), units_estimated=("units_estimated", "sum"),
                                       hu_census_2020=("hu_total", "sum"), bldgs_sf=("bldgs_sf", "sum"),
                                       bldgs_small_mf=("bldgs_small_mf", "sum"), bldgs_large_mf=("bldgs_large_mf", "sum"),
                                       census_gap_blocks=("census_gap", "sum"))
        F = F.reindex(ORDER + ["no_housing"])
        for c in ("units_parcels", "units_sf", "units_small_mf", "units_large_mf", "units_estimated"):
            F[c] = F[c].round(0)
        for b in ("sf", "small_mf", "large_mf"):
            F["pct_units_" + b] = (100 * F["units_" + b] / F.units_parcels).where(F.units_parcels > 0, 0).round(1)
        tables["F_housing_mix_by_block_type"] = F

        for name, t in tables.items():
            p = os.path.join(TABLE_DIR, name + ".csv")
            t.to_csv(p)
            st.output(p, role="table " + name)
            results[name] = json.loads(t.to_json(orient="index"))

        # ---- figures ---------------------------------------------------------
        plt.rcParams.update({"font.family": "sans-serif", "font.size": 10})
        fig, ax = plt.subplots(figsize=(10, 4.6), facecolor="#fcfcfb")
        stacked_bar(ax, A, "Race and ethnicity of residents by block type, Oak Park, 2020 Census")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False, fontsize=9)
        fig.tight_layout()
        p_fig = os.path.join(OUT_DIR, "fig_race_by_block_type.png")
        fig.savefig(p_fig, dpi=160, metadata={"Software": None})
        plt.close(fig)
        st.output(p_fig, role="figure: race composition by block type")

        fig, ax = plt.subplots(figsize=(10, 4.6), facecolor="#fcfcfb")
        cat_colors = ["#2a78d6", "#1baf7a", "#eb6834", "#4a3aa7", "#d9d8d3"]
        groups = [c for c in RACE_COLS if c != "nh_other"]
        left = [0.0] * len(groups)
        Bplot = B.reindex(ORDER + ["no_housing"])
        for cat, color in zip(ORDER + ["no_housing"], cat_colors):
            vals = [Bplot.loc[cat, "pct_of_" + c] for c in groups]
            bars = ax.barh([RACE_LABEL[c] for c in groups], vals, left=left, color=color, height=0.55,
                           edgecolor="#fcfcfb", linewidth=2, label=CATEGORY_LABELS[cat])
            for b, v in zip(bars, vals):
                if v >= 6:
                    ax.text(b.get_x() + b.get_width() / 2, b.get_y() + b.get_height() / 2, f"{v:.0f}%",
                            ha="center", va="center", fontsize=9,
                            color="#0b0b0b" if cat in ("no_housing", "small_mf_2_6") else "#ffffff")
            left = [l + v for l, v in zip(left, vals)]
        ax.set_xlim(0, 100)
        ax.invert_yaxis()
        ax.set_xlabel("Share of the group's Oak Park residents (%)", color="#52514e")
        ax.set_title("Where each group lives: residents by block type, Oak Park, 2020 Census", loc="left", fontsize=12)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors="#52514e", length=0)
        ax.set_facecolor("#fcfcfb")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False, fontsize=9)
        fig.tight_layout()
        p_fig2 = os.path.join(OUT_DIR, "fig_where_groups_live.png")
        fig.savefig(p_fig2, dpi=160, metadata={"Software": None})
        plt.close(fig)
        st.output(p_fig2, role="figure: distribution of each group across block types")

        # ---- results.md --------------------------------------------------------
        pct_cols = {"pct_" + c: RACE_LABEL[c].replace(" (non-Hispanic)", "") for c in RACE_COLS}
        village = A.loc["all_blocks"]
        md = [
            "# Race and ethnicity by block type, Oak Park, Illinois",
            "",
            "Every number below is produced by the pipeline in this repository from the",
            "sources listed in PROVENANCE.md. Blocks are 2020 Census blocks; block types come",
            "from the Cook County Assessor's 2026 parcel data; residents come from the 2020",
            "Census (P.L. 94-171 table P2). Totals are reported for whole categories of",
            "blocks only, never for individual blocks.",
            "",
            "## Block types",
            "",
            f"A block is **single-family only** when at least {SF_ONLY_MIN_SHARE:.0%} of its housing units are",
            "single-family houses (detached, or attached townhomes). It is **2-6 unit** or **7+ unit** when",
            "buildings of that size hold at least half of its units. Everything else with housing is",
            "**mixed**: typically houses alongside 2-flats, small apartment buildings or a condo building.",
            "",
            md_table(F, {"n_blocks": "Blocks", "units_parcels": "Units (parcels)", "hu_census_2020": "Units (2020 Census)",
                         "pct_units_sf": "% single-family", "pct_units_small_mf": "% in 2-6 unit bldgs",
                         "pct_units_large_mf": "% in 7+ unit bldgs", "units_estimated": "Units estimated"}),
            "",
            "## A. Who lives on each block type (2020 Census)",
            "",
            f"Oak Park's 2020 population was {int(village.pop_2020):,}: "
            + ", ".join(f"{village['pct_' + c]:.1f}% {RACE_LABEL[c]}" for c in RACE_COLS[:4]) + ".",
            "",
            md_table(A, {"n_blocks": "Blocks", "pop_2020": "Population", **pct_cols}),
            "",
            "![race by block type](fig_race_by_block_type.png)",
            "",
            "## B. Where each group lives",
            "",
            "Share of each group's Oak Park residents living on each block type.",
            "",
            md_table(B, {"pop_2020": "Population", **{"pct_of_" + c: RACE_LABEL[c].replace(" (non-Hispanic)", "")
                                                       for c in RACE_COLS}}),
            "",
            "![where groups live](fig_where_groups_live.png)",
            "",
            "## C. Sensitivity to the single-family cutoff",
            "",
        ]
        for s in SF_ONLY_SENSITIVITY:
            t = tables[f"C_sensitivity_sf{int(s * 100)}"]
            md += [f"Single-family cutoff at {s:.0%} of units:", "",
                   md_table(t, {"n_blocks": "Blocks", "pop_2020": "Population", **pct_cols}), ""]
        t = tables["C_sensitivity_estimated_units_min"]
        md += ["Every estimated 7+ building unit count (buildings absent from the Commercial Valuation",
               "dataset, whose units are estimated from assessed value) replaced by the class minimum of 7:", "",
               md_table(t, {"n_blocks": "Blocks", "pop_2020": "Population", **pct_cols}), ""]
        md += [
            "## D. Block groups classified by their own housing mix",
            "",
            "Census block groups are the smallest geography with published ACS estimates, and their",
            "2020 counts carry far less disclosure-avoidance noise than blocks. Each block group is",
            "classified by the same rule applied to all of its units. Most Oak Park block groups are",
            "internally mixed, so this is a coarser cut.",
            "",
            "2020 Census counts:", "",
            md_table(D1, {"n_block_groups": "Block groups", "pop_2020": "Population", **pct_cols}),
            "",
            "ACS 2020-2024 five-year estimates (percent, with 90% margin of error):", "",
            md_table(D2, {"n_block_groups": "Block groups", "pop_acs": "Population",
                          **{"pct_" + c: RACE_LABEL[c].replace(" (non-Hispanic)", "") for c in RACE_COLS[:4]},
                          **{"pct_" + c + "_moe": "MOE " + RACE_LABEL[c].split(" ")[0] for c in RACE_COLS[:4]}}),
            "",
            "## E. Within-block-group contrast",
            "",
            "Only block groups that contain more than one block type, so each comparison holds the",
            "neighbourhood constant. This is the comparison most exposed to the 2020 disclosure-avoidance",
            "noise, which shifts people between blocks within a block group and therefore shrinks",
            "differences; treat it as a lower bound on the true contrast.",
            "",
            md_table(E, {"n_block_groups": "Block groups", "n_blocks": "Blocks", "pop_2020": "Population", **pct_cols}),
            "",
            "Paired difference in percentage points versus the single-family blocks of the same block",
            "group (weighted by the smaller population of each pair; positive = higher share on this block type):",
            "",
            md_table(E2, {"n_pairs": "Pairs", **{"diff_pct_" + c: RACE_LABEL[c].replace(" (non-Hispanic)", "")
                                                  for c in RACE_COLS}},
                     fmt={"diff_pct_" + c: "{:+.1f}" for c in RACE_COLS}),
            "",
            "## A2. Excluding group-quarters blocks",
            "",
            f"Blocks where more than {GQ_MAX_SHARE:.0%} of residents live in group quarters (nursing homes,",
            "dormitories) removed.",
            "",
            md_table(A2, {"n_blocks": "Blocks", "pop_2020": "Population", **pct_cols}),
            "",
            "## Notes on the 2020 Census numbers",
            "",
            "The 2020 Census applied differential privacy (the TopDown Algorithm) to every count below",
            "the state level. Block-level race counts are noisy and biased toward looking more diverse",
            "than they are; total housing units per block are exact. Sums over hundreds of blocks, as",
            "reported here, cancel most of that noise, and cancel it entirely where a block type covers",
            "whole block groups. Section D uses block-group counts, which are much less noisy, as a check.",
            "",
        ]
        p_md = os.path.join(OUT_DIR, "results.md")
        with open(p_md, "w") as f:
            f.write("\n".join(md))
        st.output(p_md, role="results narrative with all tables")
        p_json = os.path.join(OUT_DIR, "results.json")
        with open(p_json, "w") as f:
            json.dump(results, f, indent=1, sort_keys=True)
        st.output(p_json, role="all tables as JSON")
        st.note("headline (2020, all blocks): " + "; ".join(
            f"{CATEGORY_LABELS[c]}: white {A.loc[c, 'pct_nh_white']}%, black {A.loc[c, 'pct_nh_black']}%, "
            f"hispanic {A.loc[c, 'pct_hispanic']}%, asian {A.loc[c, 'pct_nh_asian']}% (pop {int(A.loc[c, 'pop_2020']):,})"
            for c in ORDER))


if __name__ == "__main__":
    main()
