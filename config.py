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

# ---------------------------------------------------------------------------
# Source 7: Village of Oak Park GIS, Historic Districts polygon layer
# (layer 13 of the VOP AGOL_VOP_Project MapServer; the same layer the
# oak-park-properties map uses). Attribute ESTABLISHED is empty in the data,
# so designation dates come from HISTORIC_DISTRICTS below, with sources.
# ---------------------------------------------------------------------------
VOP_HISTORIC_DISTRICTS_URL = ("https://utility.arcgis.com/usrsvcs/servers/"
                              "4cff1aaefa364b57b8c70d5c606f2088/rest/services/VOP/"
                              "AGOL_VOP_Project/MapServer/13/query")

# ---------------------------------------------------------------------------
# Source 8: Cook County Assessor, Condominium Unit Characteristics (Socrata
# 3r7i-mrz4): year built per condo unit, keyed by 10-digit building PIN.
# ---------------------------------------------------------------------------
SOCRATA_CONDO_URL = "https://datacatalog.cookcountyil.gov/resource/3r7i-mrz4.json"
SOCRATA_CONDO_YEAR = "2023"

# ---------------------------------------------------------------------------
# Source 9: Village of Oak Park GIS, Zoning Districts polygon layer (layer 8
# of the same MapServer; the layer the oak-park-properties map overlays).
# ---------------------------------------------------------------------------
VOP_ZONING_URL = ("https://utility.arcgis.com/usrsvcs/servers/"
                  "4cff1aaefa364b57b8c70d5c606f2088/rest/services/VOP/"
                  "AGOL_VOP_Project/MapServer/8/query")
VOP_ZONING_FIELDS = "ZONED,ZONINGDESCRIPTION,ZONINGCATEGORY"
MF_ZONES = ("R-5", "R-6", "R-7")          # two-family and multi-family residential zones
DOWNTOWN_COMMERCIAL_ZONES = ("DT-1", "DT-2", "DT-3", "NC", "GC", "HS", "MS", "NA", "RR")

# ---------------------------------------------------------------------------
# Historic districts: designation history. The GIS layer's ESTABLISHED field
# is blank, so dates are recorded here with their sources. "local" is the
# Village designation that brings demolition and exterior-alteration review
# (the treatment date for the before/after comparison); National Register
# listing carries no regulatory control over private owners.
# Sources:
#  [1] Oak Park Village Code 7-9-3 (Historic Districts), via
#      https://codelibrary.amlegal.com/codes/oakparkil/latest/oakpark_il/0-0-0-21232
#  [2] Village of Oak Park, "Ridgeland-Oak Park Historic District" brochure,
#      https://www.oak-park.us/files/assets/oakpark/v/1/historic-preservation/ridgeland-historic-district.pdf
#      ("listed in the National Register of Historic Places in 1983 and was
#      locally designated by the Village of Oak Park in 1994")
#  [3] Wednesday Journal, "Laying the foundation for historic preservation",
#      2014-11-25 (1972 first preservation ordinance; FLW renamed on 1973 NR
#      listing; FLW boundaries expanded 2009; Ridgeland local 1994;
#      Gunderson NR 2002, south portion local 2003)
#  [4] Patch, "Expansion Considered for Frank Lloyd Wright Historic District",
#      2011-03-22 (1,491 homes in the 1972 district; 444 to be added to match
#      the 2009 National Register boundary)
#  [5] National Register listing dates: NRHP reference 73000700 (FLW,
#      1973-12-04) and 83003559 (Ridgeland-Oak Park, 1983-12-08), as
#      reported on the districts' Wikipedia pages
#  [6] Village of Oak Park, Gunderson Historic District nomination report,
#      https://www.oak-park.us/files/assets/oakpark/v/1/historic-preservation/resources/gunderson-subdivision-1.pdf
#      (local designation 2002-06-17; expanded 2003-05-19, Ord. 2003-O-28)
# ---------------------------------------------------------------------------
HISTORIC_DISTRICTS = {
    "Frank Lloyd Wright": {
        "slug": "flw", "local_year": 1972, "local_date": "1972-02-07", "local_ordinance": "1972-O-8",
        "nr_year": 1973, "nr_date": "1973-12-04",
        "boundary_note": ("Current polygon is the boundary as expanded on the National Register in 2009 "
                          "and locally in 2012 (about 444 parcels added to the 1,491 of 1972); the 1972 "
                          "boundary is not available as GIS data, so a sensitivity run treats 2012 as the "
                          "designation year for the whole polygon."),
        "sensitivity_year": 2012, "sources": ["1", "3", "4", "5"]},
    "Ridgeland - Oak Park": {
        "slug": "ridgeland", "local_year": 1994, "local_date": "1994", "local_ordinance": "",
        "nr_year": 1983, "nr_date": "1983-12-08",
        "boundary_note": "Local district, designated 1994; National Register listing 1983.",
        "sensitivity_year": 1983, "sources": ["1", "2", "3", "5"]},
    "Gunderson": {
        "slug": "gunderson", "local_year": 2002, "local_date": "2002-06-17", "local_ordinance": "2003-O-28 (expansion)",
        "nr_year": 2002, "nr_date": "2002",
        "boundary_note": "Local district designated 2002 (north), expanded 2003 (south).",
        "sensitivity_year": 2003, "sources": ["1", "3", "6"]},
}

# Multi-family for the district analysis = any building with 2 or more
# dwelling units in one structure: 2-6 unit buildings, 7+ unit buildings,
# and condominium buildings with 2+ units. Townhomes (one unit per PIN,
# ground entry) are single-family and are excluded.
MF_UNIT_TYPES = ("small_mf", "large_mf", "condo")
MF_MIN_UNITS = 2
# Year built rules for the district analysis, in priority order (per building):
#   char_yrblt          assessor residential characteristics, 2026 record
#   condo_chars         assessor condominium characteristics, min over units
#   commval             assessor commercial valuation `yearbuilt`
#   char_yrblt_anyyear  residential characteristics for the PIN in any
#                       year 2020-2026 (PINs reclassified out of class 2)
#   class_history       first assessment year the PIN carries a residential
#                       class after being vacant/absent, minus one
#   unknown
#   manual              year from a cited published source, for the few large
#                       buildings none of the assessor sources date (below)
DECADE_START, DECADE_END = 1870, 2029

# Year built from published sources for buildings the assessor data cannot
# date (co-operatives and special rental structures carry no characteristics
# record and are absent from the Commercial Valuation dataset). Keyed by
# building_id (10-digit condo parent or the 14-digit PIN / commval keypin).
MANUAL_YEAR_BUILT = {
    # Oak Park Arms, 408 S Oak Park Ave: hotel completed 1921, opened 1922
    # (https://en.wikipedia.org/wiki/Oak_Park_Arms;
    #  https://www.oakparkarms.com/oak-park-arms-hotel-history/)
    "16074180010000": (1921, "https://en.wikipedia.org/wiki/Oak_Park_Arms"),
    "16074180050000": (1921, "https://en.wikipedia.org/wiki/Oak_Park_Arms"),
    # Holley Court Terrace (now Brookdale Oak Park), 1111 Ontario St, 13
    # storeys, built 1992 (Wednesday Journal, "The high-rise wars", 2017-03-28,
    # https://www.oakpark.com/2017/03/28/the-high-rise-wars/)
    "16071180450000": (1992, "https://www.oakpark.com/2017/03/28/the-high-rise-wars/"),
    "16071180430000": (1992, "https://www.oakpark.com/2017/03/28/the-high-rise-wars/"),
}


# Deterministic HTTP behaviour.
HTTP_TIMEOUT = 120
HTTP_RETRIES = 3
# Census Reporter returns 403 to the default python-requests agent.
HTTP_USER_AGENT = "op-block-typology-pipeline/1.0"
