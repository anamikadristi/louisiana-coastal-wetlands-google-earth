"""Shared paths and settings for the pipeline.

Raw downloads go to RAW_DIR (default: <repo>/raw_data, ignored by git).
Set the environment variable LCW_RAW_DIR to keep large downloads elsewhere.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.environ.get("LCW_RAW_DIR", REPO / "raw_data"))
WORK_DIR = RAW_DIR / "work"          # intermediate files (large, not committed)
DATA_DIR = REPO / "data"             # small cleaned files (committed)
FIG_DIR = REPO / "outputs" / "figures"
TAB_DIR = REPO / "outputs" / "tables"
KMZ_DIR = REPO / "outputs" / "kmz"
CHART_DIR = WORK_DIR / "balloon_charts"  # small PNGs packed into the KMZ

for d in (RAW_DIR, WORK_DIR, DATA_DIR, FIG_DIR, TAB_DIR, KMZ_DIR, CHART_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Public, keyless sources
CIMS = "https://cims.coastal.la.gov/RequestedDownloads/ZippedFiles"
CIMS_GIS = "https://cims.coastal.louisiana.gov/viewer/metadata/zips"
SOURCES = {
    "crms_hydro": (f"{CIMS}/CRMS_Continuous_Hydrographic.zip", "crms/CRMS_Continuous_Hydrographic.zip"),
    "crms_sites": (f"{CIMS_GIS}/CRMS_Sites.zip", "gis/CRMS_Sites.zip"),
    "stations": (f"{CIMS_GIS}/Data_Collection_Stations.zip", "gis/Data_Collection_Stations.zip"),
    "basins": (f"{CIMS_GIS}/Basins.zip", "gis/Basins.zip"),
    # USGS SIM 3381 persistent land change raster (ScienceBase item 5a67a8cde4b06e28e9c57150)
    "sim3381_img": ("https://www.sciencebase.gov/catalog/file/get/5a67a8cde4b06e28e9c57150?f=__disk__85%2F4c%2F31%2F854c31e17525ee111c9e39c2272554053fa8ab57",
                    "landchange/sim_3381_persistent_change_spatial_data_092616.img"),
    "sim3381_rrd": ("https://www.sciencebase.gov/catalog/file/get/5a67a8cde4b06e28e9c57150?f=__disk__b3%2F62%2F92%2Fb3629207ca1a65be690f7d0fedeca005dac58a6e",
                    "landchange/sim_3381_persistent_change_spatial_data_092616.rrd"),
    "sim3381_xml": ("https://www.sciencebase.gov/catalog/file/get/5a67a8cde4b06e28e9c57150?f=__disk__2d%2F6a%2F80%2F2d6a80e6c365005cafb6f1d29038781a0e28b3bb",
                    "landchange/sim_3381_persistent_change_spatial_data_092616.img.xml"),
    # USGS NWIS active surface-water sites with instantaneous values, study bounding box
    "nwis_sites": ("https://waterservices.usgs.gov/nwis/site/?format=rdb&bBox=-91.30,28.90,-89.60,30.60"
                   "&siteType=ST,ES,LK,ST-TS&siteStatus=active&outputDataTypeCd=iv&seriesCatalogOutput=true",
                   "nwis/nwis_sites_catalog.rdb"),
}

# Study design
MAUREPAS_CENTER = (30.255, -90.515)   # lat, lon, approximate middle of Lake Maurepas
MAUREPAS_RADIUS_KM = 22.0             # CRMS hydro stations within this distance form the Maurepas group
STUDY_BASINS = ["Pontchartrain", "Barataria", "Terrebonne"]
KEY_SITES_PER_BASIN = 4               # extra stations per basin for the KMZ and comparison
MIN_DAYS_PER_MONTH = 15               # a month counts if it has at least this many valid daily means
MIN_YEARS = 8                         # minimum span of valid monthly data for a trend test
END_DATE = "2025-12-31"               # last complete calendar year used in trend tests
