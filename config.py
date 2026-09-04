"""Single source of truth for every parameter in the pipeline.

Every stage imports from here. A run is fully described by this file, the
source database snapshot, and the upstream downloads recorded in
outputs/provenance/. Nothing in a stage script hard-codes a threshold, a
class list, or a URL.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(ROOT, "data", "raw")          # upstream snapshots, verbatim
INTERIM_DIR = os.path.join(ROOT, "data", "interim")  # stage outputs, one file per step
OUT_DIR = os.path.join(ROOT, "outputs")              # results, map, provenance
PROV_DIR = os.path.join(OUT_DIR, "provenance")
AUDIT_PATH = os.path.join(OUT_DIR, "audit.log")

# ---------------------------------------------------------------------------
# Source 1: Cook County Assessor data, local SQLite mirror of the Socrata
# datasets (built by ~/git/tax_appeal_app/src/ingest.ts). Fingerprinted at
# extract time; see s01_extract.py.
# ---------------------------------------------------------------------------
DB_PATH = os.path.expanduser("~/git/tax_appeal_app/data/properties.db")
YEAR = 2026                 # assessment year: 2026 mailed reassessment
TOWNSHIP_CODE = "27"        # Oak Park township (coterminous with the village)

# ---------------------------------------------------------------------------
# Source 2: Cook County GIS parcel polygons (ArcGIS FeatureServer).
# ---------------------------------------------------------------------------
ARCGIS_PARCELS_URL = ("https://gis.cookcountyil.gov/hosting/rest/services/"
                      "Hosted/Parcel_2022/FeatureServer/0/query")
ARCGIS_MUNICIPALITY = "Oak Park"
ARCGIS_PAGE = 2000          # server maxRecordCount
ARCGIS_FIELDS = "objectid,pin10,name,parceltype,latitude,longitude,geoid,assessorbldgclass"

# ---------------------------------------------------------------------------
# Source 3: Cook County Assessor Commercial Valuation Data (Socrata csik-bsws).
# Gives total residential unit counts for class 3 (7+ unit) apartment
# buildings. Oak Park rows exist only for the 2023 reassessment.
# ---------------------------------------------------------------------------
SOCRATA_COMMVAL_URL = "https://datacatalog.cookcountyil.gov/resource/csik-bsws.json"
SOCRATA_COMMVAL_TOWNSHIP = "Oak Park"

# ---------------------------------------------------------------------------
# Source 4: Census TIGER/Line 2020 geometries (state files, Illinois = 17).
# ---------------------------------------------------------------------------
TIGER_BLOCKS_URL = "https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_17_tabblock20.zip"
TIGER_BG_URL = "https://www2.census.gov/geo/tiger/TIGER2020/BG/tl_2020_17_bg.zip"
TIGER_PLACE_URL = "https://www2.census.gov/geo/tiger/TIGER2020/PLACE/tl_2020_17_place.zip"
PLACE_GEOID = "1754885"     # Oak Park village, IL
PLACE_NAME = "Oak Park"

# ---------------------------------------------------------------------------
# Source 5: 2020 Census P.L. 94-171 Redistricting summary file, Illinois.
# Block-level population by Hispanic origin and race (P2) and housing
# occupancy (H1). Pipe-delimited; layouts verified in s06_census.py against
# the state total and against TIGER POP20/HOUSING20 per block.
# ---------------------------------------------------------------------------
PL_URL = ("https://www2.census.gov/programs-surveys/decennial/2020/data/"
          "01-Redistricting_File--PL_94-171/Illinois/il2020.pl.zip")
PL_SUMLEV_BLOCK = "750"
# Column indexes (0-based) in the pipe-delimited files, per the 2020 PL
# technical documentation: geo header has 97 fields; segment 1 = 5 header
# fields + P1 (71) + P2 (73); segment 2 = 5 header + P3 (71) + P4 (73) + H1 (3).
PL_GEO_SUMLEV_IDX, PL_GEO_LOGRECNO_IDX, PL_GEO_GEOCODE_IDX = 2, 7, 9
PL_SEG_LOGRECNO_IDX = 4
PL_P2_FIRST_IDX = 5 + 71          # P0020001 in segment 1
PL_H1_FIRST_IDX = 5 + 71 + 73     # H0010001 in segment 2
PL_STATE_TOTAL_POP = 12812508     # Illinois 2020 resident population (check value)

# ---------------------------------------------------------------------------
# Source 6: ACS 5-year block-group estimates via the Census Reporter API
# (keyless mirror of api.census.gov; api.census.gov now requires a key). The
# response's `release` field is recorded verbatim so the vintage is auditable.
# Used only as a block-group-level cross-check of the block-level 2020 counts;
# the ACS is not published below block group.
# ---------------------------------------------------------------------------
CENSUSREPORTER_URL = "https://api.censusreporter.org/1.0/data/show/latest"
ACS_TABLES = ("B03002", "B01003")   # Hispanic origin by race; total population
ACS_GEO_QUERY = f"150|16000US{PLACE_GEOID}"   # all block groups in the place

# ---------------------------------------------------------------------------
# Housing-unit rules by Assessor property class.
# ---------------------------------------------------------------------------
# Detached single-family (class 2, one dwelling): one unit each.
SF_DETACHED_CLASSES = ("202", "203", "204", "205", "206", "207", "208", "209",
                       "234", "278", "218")
# Attached single-family (townhome / row house): one unit each. Counted in
# the single-family bucket (owner-occupied, ground-entry, one household).
SF_ATTACHED_CLASSES = ("210", "295")
# Small apartment buildings, 2-6 units: units from char_apts.
SMALL_MF_CLASSES = ("211", "212")
CHAR_APTS_WORDS = {"Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6}
SMALL_MF_DEFAULT_UNITS = 2        # used when char_apts is missing; flagged
# Condominium units: one unit per PIN; the building is the 10-digit parent.
CONDO_CLASSES = ("299",)
# Large apartment buildings (7+ units, class 3) and cooperatives (213):
# units from the Commercial Valuation dataset where present, else estimated.
LARGE_MF_CLASSES = ("313", "314", "315", "318", "390", "391", "397", "213")
LARGE_MF_MIN_UNITS = 7
# Exempt parcels that carry a residential characteristics record are counted
# by that record (owner-occupied exempt houses, a few small apartments).
EXEMPT_CLASS = "EX"
# Everything else (vacant, garages, commercial, railroad, ancillary): 0 units.

# Size boundary between "small" (2-6) and "large" (7+) multi-family
# buildings, applied to condo buildings by unit count.
SMALL_MF_MAX_UNITS = 6

# ---------------------------------------------------------------------------
# Block classification, by share of housing units.
# ---------------------------------------------------------------------------
SF_ONLY_MIN_SHARE = 0.95      # single-family share at/above this = "single_family"
DOMINANT_SHARE = 0.50         # a multi-family type at/above this = dominates
SF_ONLY_SENSITIVITY = (1.00, 0.90)   # alternative cutoffs reported alongside
CATEGORIES = ("single_family", "small_mf_2_6", "large_mf_7plus", "mixed", "no_housing")
CATEGORY_LABELS = {
    "single_family": "Single-family only",
    "small_mf_2_6": "2-6 unit buildings dominate",
    "large_mf_7plus": "7+ unit buildings dominate",
    "mixed": "Mixed (houses + apartments)",
    "no_housing": "No housing",
}
# A block whose 2020 Census housing count exceeds the parcel-derived count by
# both of these margins is flagged as having unresolved (usually tax-exempt)
# housing; it keeps its classification but the flag is carried to outputs.
CENSUS_GAP_MIN_UNITS = 7
CENSUS_GAP_MIN_SHARE = 0.30

# A block whose 2020 population is mostly in group quarters (nursing homes,
# dormitories) is not describing its housing stock; results are reported with
# and without such blocks.
GQ_MAX_SHARE = 0.25

# Race / ethnicity categories reported (2020 P2 and ACS B03002 share the
# definitions). "nh_" = not Hispanic or Latino. Small categories are folded
# into "other" for the tables and charts; the full detail stays in the CSVs.
RACE_GROUPS = (("nh_white", "White (non-Hispanic)"),
               ("nh_black", "Black (non-Hispanic)"),
               ("hispanic", "Hispanic or Latino"),
               ("nh_asian", "Asian (non-Hispanic)"),
               ("nh_two_plus", "Two or more races (non-Hispanic)"),
               ("nh_other", "Other (non-Hispanic)"))
RACE_FOLD_INTO_OTHER = ("nh_aian", "nh_nhpi", "nh_other")

# Chart and map colours: validated categorical palette (dataviz skill
# reference instance), assigned in fixed slot order.
RACE_COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300")
CATEGORY_COLORS = {"single_family": "#2a78d6", "small_mf_2_6": "#1baf7a",
                   "large_mf_7plus": "#eb6834", "mixed": "#4a3aa7", "no_housing": "#d9d8d3"}

# Deterministic HTTP behaviour.
HTTP_TIMEOUT = 120
HTTP_RETRIES = 3
# Census Reporter returns 403 to the default python-requests agent.
HTTP_USER_AGENT = "op-block-typology-pipeline/1.0"
