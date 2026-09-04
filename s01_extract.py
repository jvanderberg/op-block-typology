"""Stage 1: extract every Oak Park parcel for the assessment year from the
source database, verbatim, with the fields later stages need.

Source: ~/git/tax_appeal_app/data/properties.db, a local SQLite mirror of the
Cook County Assessor Socrata datasets (assessed values uzyt-m557, parcel
addresses 3723-97qp, address points 78yw-iddh, characteristics x54s-btds).
The database is 6.5 GB, so it is fingerprinted by size, mtime and the sha256
of its first 64 MB rather than hashed in full.

Outputs: data/interim/s01_parcels.csv, one row per PIN;
         data/interim/s01_address_points.csv, every Oak Park address point
         (address, lat, lon) for the address-match locating rule in stage 3.
"""
import os
import sqlite3

import pandas as pd

from config import DB_PATH, INTERIM_DIR, TOWNSHIP_CODE, YEAR
from provenance import Stage

SQL = """
SELECT a.pin, a.class, a.nbhd, a.mailed_bldg, a.mailed_land, a.mailed_tot,
       ap.lat AS ap_lat, ap.lon AS ap_lon, p.prop_address_full AS address,
       c.char_apts, c.char_bldg_sf, c.char_land_sf, c.char_yrblt, c.char_use,
       c.n_cards
FROM assessed_values a
LEFT JOIN address_points ap ON ap.pin = a.pin
LEFT JOIN parcel_addresses p ON p.pin = a.pin AND p.year = a.year
LEFT JOIN (
    SELECT pin, year, MAX(char_apts) AS char_apts, SUM(char_bldg_sf) AS char_bldg_sf,
           MAX(char_land_sf) AS char_land_sf, MAX(char_yrblt) AS char_yrblt,
           MAX(char_use) AS char_use, COUNT(*) AS n_cards
    FROM property_characteristics
    WHERE township_code = ? AND year = ?
    GROUP BY pin, year
) c ON c.pin = a.pin AND c.year = a.year
WHERE a.township_code = ? AND a.year = ?
ORDER BY a.pin
"""


def main():
    with Stage("s01_extract", __file__) as st:
        st.param(db_path=DB_PATH, year=YEAR, township_code=TOWNSHIP_CODE)
        stt = os.stat(DB_PATH)
        st.input(DB_PATH, role="source database (Cook County Assessor mirror)",
                 partial_hash=64 * 1024 * 1024,
                 extra={"mtime": int(stt.st_mtime)})
        db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        n_av = db.execute("SELECT COUNT(*) FROM assessed_values WHERE township_code=? AND year=?",
                          (TOWNSHIP_CODE, YEAR)).fetchone()[0]
        st.note(f"assessed_values rows for township {TOWNSHIP_CODE}, year {YEAR}: {n_av}")
        df = pd.read_sql_query(SQL, db, params=(TOWNSHIP_CODE, YEAR, TOWNSHIP_CODE, YEAR))
        ap = pd.read_sql_query(
            """SELECT pin, address, lat, lon FROM address_points
               WHERE city LIKE '%Oak Park%' AND lat IS NOT NULL AND lon IS NOT NULL
               ORDER BY pin""", db)
        db.close()
        assert len(df) == n_av, f"join changed row count: {len(df)} != {n_av}"
        assert df.pin.is_unique, "duplicate PINs in extract"
        st.note(f"extracted {len(df)} parcels; {df.ap_lat.notna().sum()} have an address point; "
                f"{df.char_bldg_sf.notna().sum()} have a characteristics record")
        st.note("class counts: " + ", ".join(f"{k}={v}" for k, v in
                                             df["class"].value_counts().head(25).items()))
        out = os.path.join(INTERIM_DIR, "s01_parcels.csv")
        df.to_csv(out, index=False)
        st.output(out, role="all Oak Park parcels, one row per PIN")
        out2 = os.path.join(INTERIM_DIR, "s01_address_points.csv")
        ap.to_csv(out2, index=False)
        st.note(f"address points with city like Oak Park and coordinates: {len(ap)}")
        st.output(out2, role="Oak Park address points (address, lat, lon)")


if __name__ == "__main__":
    main()
