# Oak Park block typology and race

Which kinds of blocks do Oak Park residents of each race live on? This repo
classifies every one of Oak Park's 1,058 Census blocks by the housing on it,
using the Cook County Assessor's parcel records, then totals the 2020 Census
race and ethnicity counts for each kind of block.

Results: **[outputs/results.md](outputs/results.md)**. Map of block types:
`outputs/map.html`. Provenance of every number: **[PROVENANCE.md](PROVENANCE.md)**.

## The short answer

Oak Park's blocks fall into four kinds: single-family only (462 blocks),
2-6 unit buildings dominate (70), 7+ unit buildings dominate (208), and mixed
houses and apartments (220). 98 blocks have no housing.

| Block type | Blocks | 2020 population | White | Black | Hispanic | Asian |
|---|---|---|---|---|---|---|
| Single-family only | 462 | 18,464 | 68.7% | 10.4% | 8.6% | 4.4% |
| 2-6 unit buildings dominate | 70 | 2,837 | 45.8% | 28.9% | 12.2% | 5.9% |
| 7+ unit buildings dominate | 208 | 21,327 | 51.7% | 27.7% | 9.2% | 6.5% |
| Mixed (houses + apartments) | 220 | 11,857 | 66.0% | 12.8% | 9.7% | 4.9% |
| All Oak Park | 1058 | 54,583 | 60.2% | 18.7% | 9.3% | 5.4% |

White and Hispanic groups are non-Hispanic White and Hispanic of any race; Black
and Asian are non-Hispanic single-race. Read the other way round: 58% of Oak
Park's Black residents live on blocks dominated by 7+ unit buildings and 19% on
single-family-only blocks; for White residents the figures are 34% and 39%.

The contrast survives holding the neighbourhood constant. Inside block groups
that contain both kinds of block, the 2-6 unit and 7+ unit blocks are about 20
points less White and 20 points more Black than the single-family blocks of the
same block group (results.md, section E). Because the 2020 Census's privacy
noise moves people between blocks within a block group, that within-group
figure is a lower bound.

## How it works

Nine numbered stages, run in order by `run.sh`. Each reads only fetched
snapshots or earlier stage outputs, logs every count and decision to
`outputs/audit.log`, and writes a provenance record with the sha256 of every
file it read and wrote. The last stage verifies the chain.

| Stage | What it does |
|---|---|
| `s01_extract.py` | Pulls all 18,733 Oak Park parcels for the 2026 assessment year from the local mirror of the Assessor's Socrata data (`~/git/tax_appeal_app/data/properties.db`, fingerprinted). |
| `s02_fetch.py` | Downloads and hashes every upstream file: Cook County parcel polygons (ArcGIS), the Assessor's Commercial Valuation data (unit counts for 7+ unit buildings), TIGER/Line 2020 blocks, block groups and places, the 2020 P.L. 94-171 file for Illinois, and the ACS block-group race table (Census Reporter). |
| `s03_locate.py` | Gives each parcel a point inside its polygon (condo units resolve to the building's parcel); falls back to the Assessor address point, then an address match. 48 parcels (0.3%) stay unlocated. |
| `s04_units.py` | Counts housing units per parcel from the property class, `char_apts` for 2-6 unit buildings, condo unit counts per parent PIN, and the Commercial Valuation unit counts for 7+ unit buildings (allocated across multi-PIN properties by building assessed value); a PIN that dataset lists as an apartment property is counted as such even when the 2026 assessed-values file carries it as exempt or commercial (two new downtown towers). 27 of 336 large-building PINs are absent from that dataset; their units are estimated from assessed value and flagged (rows of other classes in that dataset that carry unit counts are used first). |
| `s05_blocks.py` | Point-in-polygon join of parcels to 2020 blocks; unit mix per block; classification; reconciliation against the exact 2020 housing-unit count per block; the same aggregation per block group. |
| `s06_census.py` | Parses the P.L. 94-171 file for every Oak Park block (P2 race/ethnicity, H1 occupancy, P5 group quarters), verifying the column layout against the state total and every block against the TIGER `POP20`/`HOUSING20` attributes. Extracts ACS B03002 per block group. |
| `s07_analyze.py` | Totals by block type; sensitivity to the cutoffs; block-group check with ACS margins of error; within-block-group contrast; figures; `results.md`. |
| `s08_map.py` | Self-contained Leaflet map of block types (no census figures per block). |
| `s10_districts.py` | Assigns every multi-family building (2+ units: 2-6 unit, 7+ unit, condo buildings) to a Village historic district and zoning district, and dates it from the residential characteristics, condo characteristics, Commercial Valuation data, any-year characteristics, the assessment-roll class history, or a cited published source, in that order. |
| `s11_district_analysis.py` | Multi-family units and buildings by decade built per district; equal-length windows before and after local designation against the rest of the village; every post-designation building listed; district area by zoning. Writes `outputs/results_districts.md`. |
| `s09_provenance.py` | Verifies every input hash matches its producer's output hash, that all stages used the same `config.py`, that outputs are unchanged, and writes `PROVENANCE.md`. Fails the run otherwise. |

All parameters (class lists, cutoffs, URLs, column positions) are in
`config.py`.

### Block classification

By share of housing units on the block:

- **single_family**: at least 95% of units are single-family houses. Detached
  houses (classes 202-209, 234, 278) and attached townhomes (210, 295) both
  count as single-family.
- **small_mf_2_6**: at least 50% of units are in 2-6 unit buildings (classes
  211, 212, and condo buildings with 6 or fewer units).
- **large_mf_7plus**: at least 50% of units are in 7+ unit buildings (classes
  313-318, 390, 391, 397, cooperatives 213, and condo buildings with 7 or more
  units).
- **mixed**: everything else with housing; nearly all are houses plus 2-flats,
  small apartment buildings, or a condo building.
- **no_housing**: no units on the block's parcels.

Condo buildings are classed by structure size, not tenure, so a 40-unit condo
tower is a 7+ unit building. Sensitivity runs at 100% and 90% for the
single-family cutoff, and with every estimated large-building unit count set
to the minimum of 7, are in `results.md`; the classification is stable.

### Data quality checks built in

- Located parcels carry 27,169 units against 25,953 exact 2020 Census units
  (ratio 1.05; the parcel data is 2026 and includes buildings finished since
  2020, and 1,288 units are AV-based estimates that may run high).
- 11 blocks have far more census units than parcel units (658 units in all);
  7 are already `large_mf_7plus`, so the gap cannot change their category.
  The likely cause is tax-exempt housing, which carries no unit count in the
  assessor data (housing authority and institutional buildings).
- Every P.L. 94-171 block count is cross-checked against the TIGER attribute
  file; every table's race categories are checked to sum to the total.

### 2020 Census privacy noise

The 2020 counts were protected by differential privacy (the TopDown
Algorithm). Block-level race counts are noisy and biased toward looking more
diverse than they are; housing-unit totals per block are exact. This repo
never reports a single block. Each block type sums hundreds of blocks, which
cancels most of the noise, and section D of the results repeats the analysis
at block-group level, where the noise is far smaller, with the same pattern.

## Historic districts: multi-family construction before and after designation

A second analysis, in `outputs/results_districts.md`, asks how much multi-family
housing was built inside each of Oak Park's historic districts before and after
the Village designated it. Boundaries are the Village GIS historic-district
polygons (the same layer the oak-park-properties map uses); local designation
dates are 1972 for the Frank Lloyd Wright district, 1994 for Ridgeland-Oak Park
and 2002 for Gunderson, with sources in `config.py`. Only buildings standing on
the 2026 roll are visible, so demolished buildings are missing from both sides.

Equal-length windows around the designation year, units in multi-family buildings:

| District | Designated | Window | Units before | Units after | Units/yr before | Units/yr after | Rest of Oak Park units/yr before | Rest of Oak Park units/yr after |
|---|---|---|---|---|---|---|---|---|
| Frank Lloyd Wright | 1972 | 54 yrs | 1,170 | 128 | 21.67 | 2.37 | 85.31 | 56.7 |
| Ridgeland-Oak Park | 1994 | 32 yrs | 987 | 419 | 30.84 | 13.09 | 68.59 | 66.34 |

The Frank Lloyd Wright district's share of village-wide multi-family construction fell from
11.6% in the 54 years before 1972 to 3.4% in the 54 years since; only seven
multi-family buildings (128 units) have been built inside it since designation, five of
them in 1973-1981. Ridgeland-Oak Park's share fell from 27.0% to 16.5%; its post-1994
multi-family construction is a dozen buildings, most of them condominiums around
2000-2006 and three large rental buildings completed in 2023 on Lake Street, Pleasant
Street and Washington Boulevard. Gunderson has had no multi-family construction since
the 1920s. Village-wide, apartment construction collapsed after 1930 everywhere, so
the decade tables in the results are the fairer reading; the districts' pre-designation
multi-family stock is overwhelmingly 1900-1930.

The Frank Lloyd Wright polygon is the boundary as expanded in 2009 (National Register)
and 2012 (local); the 1972 boundary is not available as GIS data. A sensitivity run
with 2012 as the cut, and one with 1983 (National Register) for Ridgeland, is in the results.

## Running it

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

Needs the source database at `~/git/tax_appeal_app/data/properties.db` and
network access for the first run (about 400 MB of Census downloads, which are
kept in `data/raw/` and not committed; their URLs and hashes are in
`PROVENANCE.md`). The smaller snapshots (parcel polygons, commercial valuation
rows, ACS table) are committed so the analysis stages are reproducible offline.

## Sources

- Cook County Assessor, Assessed Values (`uzyt-m557`), Parcel Addresses
  (`3723-97qp`), Residential Improvement Characteristics (`x54s-btds`), Address
  Points (`78yw-iddh`), via the local mirror built by `tax_appeal_app`.
- Cook County Assessor, Commercial Valuation Data (`csik-bsws`) and Condominium Unit
  Characteristics (`3r7i-mrz4`).
- Cook County GIS, Parcel_2022 FeatureServer.
- Village of Oak Park GIS: Historic Districts (layer 13) and Zoning Districts (layer 8) of the
  AGOL_VOP_Project MapServer.
- U.S. Census Bureau, TIGER/Line 2020; 2020 Census P.L. 94-171 Redistricting
  Data, Illinois; ACS 2020-2024 5-year table B03002 via Census Reporter.
