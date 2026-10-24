"""Step 3: locate CRMS hydro stations, assign basins, choose the analysis stations,
and tidy the USGS NWIS site list.

Selection rules (set in config.py):
  * Maurepas group: CRMS hydro stations within MAUREPAS_RADIUS_KM of Lake Maurepas.
  * Key sites: for each study basin, CRMS hydro stations outside the Maurepas group with
    at least 10 years of daily salinity and data in 2025; KEY_SITES_PER_BASIN of them are
    picked evenly along latitude (north to south) to span the fresh to saline gradient.
Outputs: data/crms_stations_selected.csv, data/crms_selected_daily.csv.gz,
         data/nwis_sites_study_area.csv, data/basins_coastal_simplified.geojson
Run: python -I scripts/03_select_stations.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (DATA_DIR, KEY_SITES_PER_BASIN, MAUREPAS_CENTER, MAUREPAS_RADIUS_KM,  # noqa: E402
                    RAW_DIR, STUDY_BASINS, TAB_DIR, WORK_DIR)


def haversine_km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = (np.sin((lat2 - lat1) * p / 2) ** 2 +
         np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * np.arcsin(np.sqrt(a))


def load_basins():
    b = gpd.read_file(RAW_DIR / "gis/Basins/shapefile/BasinsCoastal.shp").to_crs(4326)
    b = b.rename(columns={"UNIT": "basin"})[["BASIN_ID", "basin", "geometry"]]
    return b


def main():
    basins = load_basins()
    st = gpd.read_file(RAW_DIR / "gis/Data_Collection_Stations/monitoring_stations.gdb")
    st = st[st.STATION_ID.str.match(r"^CRMS\d{4}-H\d\d$", na=False)].to_crs(4326)
    st = st.drop_duplicates("STATION_ID")[["STATION_ID", "STATUS", "geometry"]]
    st = gpd.sjoin(st, basins, how="left", predicate="within").drop(columns="index_right")
    st["lat"], st["lon"] = st.geometry.y, st.geometry.x
    st = st.rename(columns={"STATION_ID": "station"})
    st["site"] = st.station.str[:8]

    sites = gpd.read_file(RAW_DIR / "gis/CRMS_Sites/shapefile/crms6298.shp")
    st = st.merge(sites[["SITE_ID", "VEGTYPE", "PARISH_NAM"]].rename(
        columns={"SITE_ID": "site", "VEGTYPE": "veg_type", "PARISH_NAM": "parish"}), on="site", how="left")

    daily = pd.read_csv(WORK_DIR / "crms_daily_all.csv.gz", parse_dates=["date"])
    rec = daily.dropna(subset=["sal_mean"]).groupby("station").agg(
        first=("date", "min"), last=("date", "max"), sal_days=("date", "size")).reset_index()
    st = st.merge(rec, on="station", how="inner")
    st["years_span"] = (st["last"] - st["first"]).dt.days / 365.25
    st["dist_maurepas_km"] = haversine_km(MAUREPAS_CENTER[0], MAUREPAS_CENTER[1], st.lat, st.lon)

    all_tab = st.drop(columns="geometry").sort_values("station")
    all_tab.to_csv(TAB_DIR / "crms_hydro_station_inventory.csv", index=False, float_format="%.5f")

    maur = st[(st.dist_maurepas_km <= MAUREPAS_RADIUS_KM) & (st.years_span >= 8)].copy()
    maur["group"] = "Lake Maurepas"
    picks = [maur]
    for b in STUDY_BASINS:
        c = st[(st.basin == b) & (~st.station.isin(maur.station)) &
               (st.sal_days >= 3650) & (st["last"] >= "2025-01-01")].sort_values("lat", ascending=False)
        idx = np.unique(np.round(np.linspace(0, len(c) - 1, KEY_SITES_PER_BASIN)).astype(int))
        k = c.iloc[idx].copy()
        k["group"] = f"{b} key site"
        picks.append(k)
    sel = pd.concat(picks).drop(columns="geometry")
    sel["first"] = sel["first"].dt.date
    sel["last"] = sel["last"].dt.date
    sel = sel[["station", "site", "group", "basin", "parish", "veg_type", "lat", "lon",
               "dist_maurepas_km", "first", "last", "sal_days", "years_span", "STATUS"]]
    sel.to_csv(DATA_DIR / "crms_stations_selected.csv", index=False, float_format="%.5f")
    sub = daily[daily.station.isin(sel.station)]
    sub.to_csv(DATA_DIR / "crms_selected_daily.csv.gz", index=False, compression="gzip", float_format="%.4f")
    print(sel[["station", "group", "basin", "first", "last", "sal_days"]].to_string(index=False))
    print(f"CRMS hydro stations with salinity data: {len(st)}; selected: {len(sel)}")

    # NWIS series catalog -> one row per site with parameter flags
    rdb = pd.read_csv(RAW_DIR / "nwis/nwis_sites_catalog.rdb", sep="\t", comment="#", dtype=str)
    rdb = rdb.iloc[1:]  # drop the field-width row
    rdb = rdb[rdb.data_type_cd.isin(["iv", "uv"])]  # "uv" = instantaneous (unit) values
    params = {"00065": "gage_height", "00060": "discharge", "00095": "spec_cond",
              "00480": "salinity", "00010": "water_temp", "62620": "wl_navd88"}
    rows = []
    for site, g in rdb.groupby("site_no"):
        r = {"site_no": site, "station_nm": g.station_nm.iloc[0], "site_tp_cd": g.site_tp_cd.iloc[0],
             "lat": float(g.dec_lat_va.iloc[0]), "lon": float(g.dec_long_va.iloc[0]),
             "iv_begin": g.begin_date.min(), "iv_end": g.end_date.max()}
        for code, name in params.items():
            r[name] = int((g.parm_cd == code).any())
        rows.append(r)
    nw = pd.DataFrame(rows)
    nwg = gpd.GeoDataFrame(nw, geometry=gpd.points_from_xy(nw.lon, nw.lat), crs=4326)
    nwg = gpd.sjoin(nwg, basins, how="left", predicate="within").drop(columns=["index_right", "BASIN_ID"])
    nwg["basin"] = nwg["basin"].fillna("outside coastal basins")
    nwg.drop(columns="geometry").to_csv(DATA_DIR / "nwis_sites_study_area.csv", index=False)
    print(f"NWIS active IV sites in box: {len(nwg)}; with salinity or spec. cond.: "
          f"{int(((nwg.salinity + nwg.spec_cond) > 0).sum())}")

    # simplified basin polygons for the repo and the KMZ
    bs = basins.copy()
    bs["geometry"] = bs.to_crs(26915).simplify(150).to_crs(4326)
    bs.to_file(DATA_DIR / "basins_coastal_simplified.geojson", driver="GeoJSON")


if __name__ == "__main__":
    main()
