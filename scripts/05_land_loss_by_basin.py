"""Step 5: persistent land loss and gain (1932 to 2016) by CWPPRA hydrologic basin.

Input: USGS SIM 3381 persistent land change raster (Couvillion et al. 2017), 15 m cells,
values 1-19 = land lost in a period (persistent water afterwards), 20-38 = land gained,
0 = no persistent change. Basins: CPRA BasinsCoastal polygons.
The raster is read in strips and the basin polygons are rasterized on the same grid, so
every 15 m cell is counted once. Per USGS metadata, the persistent-change layer is not
meant for rate calculation, so only areas are reported.
Outputs: outputs/tables/land_change_by_basin.csv, land_loss_by_basin_period.csv,
         outputs/figures/fig5_land_change_by_basin.png, fig6_land_loss_periods.png,
         RAW_DIR/work/landchange_overlay.png (+ bounds json) for the KMZ
Run: python -I scripts/05_land_loss_by_basin.py
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.features import rasterize  # noqa: E402
from rasterio.warp import calculate_default_transform, reproject  # noqa: E402
from rasterio.windows import Window  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import FIG_DIR, RAW_DIR, STUDY_BASINS, TAB_DIR, WORK_DIR  # noqa: E402

IMG = RAW_DIR / "landchange/sim_3381_persistent_change_spatial_data_092616.img"
PERIODS = ["1932-1956", "1956-1973", "1973-1975", "1975-1977", "1977-1985", "1985-1988",
           "1988-1990", "1990-1995", "1995-1998", "1998-1999", "1999-2002", "2002-2004",
           "2004-2006", "2006-2008", "2008-2009", "2009-2010", "2010-2013", "2013-2014",
           "2014-2015 new"]
# Interval labels follow the raster attribute table. Loss value 18 is labelled "2010-2014 Loss"
# in the file while the matching gain class reads "2013-2014 Gain"; it is shown here as
# 2013-2014. Values 19 and 38 are "2014-2015 New Water Area" and "New Land Area": the most
# recent changes, which the authors could not yet confirm as persistent. See README caveats.
INK, MUTED = "#0b0b0b", "#52514e"


def main():
    basins = gpd.read_file(RAW_DIR / "gis/Basins/shapefile/BasinsCoastal.shp")
    with rasterio.open(IMG) as src:
        basins = basins.to_crs(src.crs)
        shapes = [(geom, int(i) + 1) for i, geom in enumerate(basins.geometry)]
        names = ["outside basins"] + list(basins.UNIT)
        counts = np.zeros((len(names), 64), dtype=np.int64)
        step = 2048
        for row in range(0, src.height, step):
            h = min(step, src.height - row)
            win = Window(0, row, src.width, h)
            a = src.read(1, window=win)
            lab = rasterize(shapes, out_shape=a.shape, transform=src.window_transform(win),
                            fill=0, dtype="uint8")
            code = lab.astype(np.int32) * 64 + a
            counts += np.bincount(code.ravel(), minlength=len(names) * 64).reshape(len(names), 64)
        cell_km2 = abs(src.res[0] * src.res[1]) / 1e6
        cells_in_basin = np.zeros(len(names), dtype=np.int64)
        for i in range(len(names)):
            cells_in_basin[i] = counts[i].sum()

    area = counts * cell_km2
    rows, prow = [], []
    for i, n in enumerate(names):
        loss = area[i, 1:20].sum()
        gain = area[i, 20:39].sum()
        rows.append({"basin": n, "mapped_area_km2": cells_in_basin[i] * cell_km2,
                     "loss_km2": loss, "gain_km2": gain, "net_change_km2": gain - loss,
                     "loss_pct_of_mapped_area": 100 * loss / (cells_in_basin[i] * cell_km2) if cells_in_basin[i] else np.nan})
        for k, p in enumerate(PERIODS):
            prow.append({"basin": n, "period": p, "loss_km2": area[i, 1 + k], "gain_km2": area[i, 20 + k]})
    t = pd.DataFrame(rows)
    t = t[t.basin != "outside basins"].sort_values("loss_km2", ascending=False)
    tot = t[["mapped_area_km2", "loss_km2", "gain_km2", "net_change_km2"]].sum()
    t = pd.concat([t, pd.DataFrame([{"basin": "All coastal basins", **tot.to_dict(),
                                     "loss_pct_of_mapped_area": 100 * tot.loss_km2 / tot.mapped_area_km2}])])
    t.to_csv(TAB_DIR / "land_change_by_basin.csv", index=False, float_format="%.2f")
    pt = pd.DataFrame(prow)
    pt = pt[pt.basin != "outside basins"]
    pt.to_csv(TAB_DIR / "land_loss_by_basin_period.csv", index=False, float_format="%.3f")
    print(t.to_string(index=False))
    print("outside basin polygons, loss km2:", round(area[0, 1:20].sum(), 1))

    # Figure 5: loss and gain by basin
    tb = t[t.basin != "All coastal basins"].sort_values("loss_km2")
    fig, ax = plt.subplots(figsize=(8, 4))
    y = np.arange(len(tb))
    ax.barh(y + 0.19, tb.loss_km2, height=0.36, color="#e34948", label="Persistent land loss")
    ax.barh(y - 0.19, tb.gain_km2, height=0.36, color="#008300", label="Persistent land gain")
    for yi, (l, g) in enumerate(zip(tb.loss_km2, tb.gain_km2)):
        ax.text(l + 8, yi + 0.19, f"{l:,.0f}", va="center", fontsize=7, color=INK)
        ax.text(g + 8, yi - 0.19, f"{g:,.0f}", va="center", fontsize=7, color=MUTED)
    ax.set_yticks(y, tb.basin, fontsize=8)
    ax.set_xlabel("Area, km² (1932 to 2016)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("Persistent land change by CWPPRA basin, USGS SIM 3381 raster", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig5_land_change_by_basin.png", dpi=150)
    plt.close(fig)

    # Figure 6: loss by period for the three study basins (small multiples, shared axis)
    fig, axes = plt.subplots(len(STUDY_BASINS), 1, figsize=(9, 2.1 * len(STUDY_BASINS)), sharex=True, sharey=True)
    for ax, b in zip(axes, STUDY_BASINS):
        s = pt[pt.basin == b]
        ax.bar(range(len(PERIODS)), s.loss_km2, color="#e34948", width=0.75)
        ax.set_title(f"{b}: persistent land loss by mapping interval", loc="left", fontsize=9)
        ax.set_ylabel("km²", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    axes[-1].set_xticks(range(len(PERIODS)), PERIODS, rotation=60, fontsize=7)
    fig.text(0.01, 0.005, "Intervals have unequal lengths (1 to 24 years); the last bar is new water area not yet confirmed as persistent, so bar heights are areas, not rates.",
             fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(FIG_DIR / "fig6_land_loss_periods.png", dpi=150)
    plt.close(fig)

    # Overlay for Google Earth: study basins extent, about 90 m cells, EPSG:4326
    with rasterio.open(IMG) as src:
        sb = basins[basins.UNIT.isin(STUDY_BASINS)].total_bounds
        win = rasterio.windows.from_bounds(*sb, transform=src.transform).round_offsets().round_lengths()
        win = win.intersection(Window(0, 0, src.width, src.height))
        f = 6
        a = src.read(1, window=win, out_shape=(int(win.height // f), int(win.width // f)),
                     resampling=Resampling.nearest)
        tr = src.window_transform(win) * rasterio.Affine.scale(win.width / a.shape[1], win.height / a.shape[0])
        dst_tr, w, h = calculate_default_transform(src.crs, "EPSG:4326", a.shape[1], a.shape[0],
                                                   *rasterio.transform.array_bounds(a.shape[0], a.shape[1], tr))
        b = np.zeros((h, w), dtype="uint8")
        reproject(a, b, src_transform=tr, src_crs=src.crs, dst_transform=dst_tr, dst_crs="EPSG:4326",
                  resampling=Resampling.nearest)
    rgba = np.zeros((h, w, 4), dtype="uint8")
    eras = [((1, 2), (122, 4, 3)), ((3, 7), (214, 64, 40)), ((8, 19), (247, 152, 90)), ((20, 38), (0, 131, 0))]
    for (lo, hi), col in eras:
        m = (b >= lo) & (b <= hi)
        rgba[m, :3] = col
        rgba[m, 3] = 230
    plt.imsave(WORK_DIR / "landchange_overlay.png", rgba)
    west, north = dst_tr.c, dst_tr.f
    east, south = west + dst_tr.a * w, north + dst_tr.e * h
    (WORK_DIR / "landchange_overlay_bounds.json").write_text(json.dumps(
        {"west": west, "east": east, "south": south, "north": north}))

    # Figure 1 base layer: whole coast at about 150 m for the overview map
    with rasterio.open(IMG) as src:
        f = 10
        a = src.read(1, out_shape=(src.height // f, src.width // f), resampling=Resampling.nearest)
        ext = rasterio.transform.array_bounds(a.shape[0], a.shape[1],
                                              src.transform * rasterio.Affine.scale(src.width / a.shape[1], src.height / a.shape[0]))
    np.savez_compressed(WORK_DIR / "landchange_coast_150m.npz", a=a, bounds=np.array(ext), crs=str(src.crs))


if __name__ == "__main__":
    main()
