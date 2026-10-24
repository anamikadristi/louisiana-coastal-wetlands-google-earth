"""Step 6: static maps.
Fig 1: study area with CWPPRA basins, persistent land change (about 150 m display
resolution), selected CRMS stations and active USGS NWIS sites.
Also writes data/crms_stations_selected.geojson and data/nwis_sites_study_area.geojson
for QGIS or ArcGIS Pro.
Run: python -I scripts/06_maps.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA_DIR, FIG_DIR, STUDY_BASINS, WORK_DIR  # noqa: E402

GROUP_COLORS = {"Lake Maurepas": "#2a78d6", "Pontchartrain key site": "#eb6834",
                "Barataria key site": "#1baf7a", "Terrebonne key site": "#eda100"}


def main():
    basins = gpd.read_file(DATA_DIR / "basins_coastal_simplified.geojson").to_crs(26915)
    sel = pd.read_csv(DATA_DIR / "crms_stations_selected.csv")
    sg = gpd.GeoDataFrame(sel, geometry=gpd.points_from_xy(sel.lon, sel.lat), crs=4326)
    sg.to_file(DATA_DIR / "crms_stations_selected.geojson", driver="GeoJSON")
    nw = pd.read_csv(DATA_DIR / "nwis_sites_study_area.csv", dtype={"site_no": str})
    ng = gpd.GeoDataFrame(nw, geometry=gpd.points_from_xy(nw.lon, nw.lat), crs=4326)
    ng.to_file(DATA_DIR / "nwis_sites_study_area.geojson", driver="GeoJSON")
    sg, ng = sg.to_crs(26915), ng.to_crs(26915)

    z = np.load(WORK_DIR / "landchange_coast_150m.npz")
    a = z["a"]
    # raster is in WGS 84 / UTM 15N (EPSG:32615), same easting/northing as NAD83 UTM 15N at map scale
    w, s, e, n = z["bounds"]
    cls = np.zeros_like(a)
    cls[(a >= 1) & (a <= 2)] = 1
    cls[(a >= 3) & (a <= 7)] = 2
    cls[(a >= 8) & (a <= 19)] = 3
    cls[(a >= 20) & (a <= 38)] = 4
    cmap = ListedColormap([(0, 0, 0, 0), "#7a0403", "#d64028", "#f7985a", "#008300"])

    study = basins[basins.basin.isin(STUDY_BASINS)]
    xmin, ymin, xmax, ymax = study.total_bounds
    fig, ax = plt.subplots(figsize=(10, 7.2))
    ax.set_facecolor("#f4f3ef")
    basins.plot(ax=ax, facecolor="white", edgecolor="#9a9893", lw=0.6)
    study.plot(ax=ax, facecolor="none", edgecolor="#52514e", lw=1.2)
    ax.imshow(np.ma.masked_equal(cls, 0), extent=(w, e, s, n), cmap=cmap, vmin=0, vmax=4,
              interpolation="nearest", zorder=2)
    ng.plot(ax=ax, marker="^", color="#4a3aa7", markersize=14, zorder=4, alpha=0.8)
    for g, c in GROUP_COLORS.items():
        sub = sg[sg.group == g]
        sub.plot(ax=ax, color=c, edgecolor="white", linewidth=0.8, markersize=46, zorder=5)
    for _, r in sg[sg.group != "Lake Maurepas"].iterrows():  # Maurepas cluster too dense to label
        ax.annotate(r.station.replace("CRMS", "").replace("-H01", ""), (r.geometry.x, r.geometry.y),
                    xytext=(4, 3), textcoords="offset points", fontsize=6, color="#0b0b0b", zorder=6)
    for _, r in study.iterrows():
        c = r.geometry.representative_point()
        ax.text(c.x, c.y, r.basin, fontsize=9, color="#52514e", ha="center", style="italic", zorder=6)
    ax.set_xlim(xmin - 5000, xmax + 5000)
    ax.set_ylim(ymin - 5000, ymax + 5000)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    handles = [Patch(color="#7a0403", label="Land loss 1932-1973"),
               Patch(color="#d64028", label="Land loss 1973-1990"),
               Patch(color="#f7985a", label="Land loss 1990-2015"),
               Patch(color="#008300", label="Land gain 1932-2015")]
    handles += [Line2D([], [], marker="o", lw=0, color=c, markeredgecolor="white", ms=7,
                       label=f"CRMS: {g.replace(' key site', ' key sites')} (n={int((sg.group == g).sum())})") for g, c in GROUP_COLORS.items()]
    handles += [Line2D([], [], marker="^", lw=0, color="#4a3aa7", ms=6, label=f"USGS NWIS active site (n={len(ng)})")]
    ax.legend(handles=handles, loc="lower left", fontsize=7, frameon=True, framealpha=0.9)
    ax.set_title("Study area: Pontchartrain, Barataria and Terrebonne basins (UTM 15N)", loc="left", fontsize=11)
    sx = xmin + 5000
    ax.plot([sx, sx + 20000], [ymax - 4000] * 2, color="black", lw=2)
    ax.text(sx + 10000, ymax - 2500, "20 km", ha="center", fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig1_study_area_map.png", dpi=150)
    plt.close(fig)
    print("map written")


if __name__ == "__main__":
    main()
