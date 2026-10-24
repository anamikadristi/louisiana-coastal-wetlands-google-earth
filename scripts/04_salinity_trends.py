"""Step 4: salinity and water-level trends and seasonal patterns at the selected CRMS stations.

* Daily means -> monthly means (months need MIN_DAYS_PER_MONTH valid days).
* Seasonal Mann-Kendall test (Hirsch et al. 1982) on monthly salinity, with the seasonal
  Sen slope, through END_DATE. Benjamini-Hochberg false discovery rate across stations.
* Water level (NAVD88): same test, but only on the longest run of days that share one
  geoid model, so datum updates do not create false trends.
* Seasonal climatology: mean salinity by calendar month.
* A small chart per station for the Google Earth balloons.
Outputs: outputs/tables/crms_station_summary.csv, crms_monthly_climatology.csv,
         outputs/figures/*.png, RAW_DIR/work/balloon_charts/*.png
Run: python -I scripts/04_salinity_trends.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pymannkendall as mk  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (CHART_DIR, DATA_DIR, END_DATE, FIG_DIR, MIN_DAYS_PER_MONTH,  # noqa: E402
                    MIN_YEARS, TAB_DIR)

GROUP_COLORS = {"Lake Maurepas": "#2a78d6", "Pontchartrain key site": "#eb6834",
                "Barataria key site": "#1baf7a", "Terrebonne key site": "#eda100"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "figure.dpi": 150})


def monthly(df, col, ncol):
    d = df.dropna(subset=[col]).set_index("date")[col]
    m = d.resample("MS").agg(["mean", "count"])
    m.loc[m["count"] < MIN_DAYS_PER_MONTH, "mean"] = np.nan
    return m["mean"]


def seasonal_mk(series):
    s = series.dropna()
    if s.empty:
        return None
    s = series.loc[s.index.min():s.index.max()]
    span = (s.dropna().index.max() - s.dropna().index.min()).days / 365.25
    if span < MIN_YEARS or s.notna().sum() < 12 * MIN_YEARS * 0.6:
        return None
    r = mk.seasonal_test(s.values, period=12)
    return {"trend": r.trend, "p": r.p, "tau": r.Tau, "sen_per_yr": r.slope,
            "n_months": int(s.notna().sum()), "start": s.dropna().index.min().date(),
            "end": s.dropna().index.max().date()}


def longest_geoid_run(df):
    d = df.dropna(subset=["wl_navd88_ft_mean"]).copy()
    if d.empty:
        return d
    d["geoid"] = d["geoid"].fillna("unknown")
    d["run"] = (d["geoid"] != d["geoid"].shift()).cumsum()
    best = d.groupby("run").size().idxmax()
    return d[d.run == best]


def bh_fdr(p):
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    pv = p[ok]
    order = np.argsort(pv)
    ranked = pv[order] * len(pv) / (np.arange(len(pv)) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(pv)
    out[order] = np.minimum(ranked, 1)
    q[ok] = out
    return q


def balloon_chart(name, ms, ann, res, color, path):
    fig, ax = plt.subplots(figsize=(3.6, 1.9), dpi=110)
    ax.plot(ms.index, ms.values, color=color, lw=0.9, alpha=0.55, label="monthly mean")
    ax.plot(ann.index, ann.values, color=INK, lw=0, marker="o", ms=3, label="annual mean")
    if res is not None and res["trend"] != "no trend":
        t0 = pd.Timestamp(res["start"])
        yrs = (ms.index - t0).days / 365.25
        mid = np.nanmedian(ms.values) - res["sen_per_yr"] * np.nanmedian(yrs)
        ax.plot(ms.index, mid + res["sen_per_yr"] * yrs, color=INK, lw=1.2, ls="--", label="Sen slope")
    ax.set_title(f"{name} salinity (ppt)", fontsize=8, color=INK, loc="left")
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=6, frameon=False, loc="upper left", ncol=3)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    sel = pd.read_csv(DATA_DIR / "crms_stations_selected.csv")
    daily = pd.read_csv(DATA_DIR / "crms_selected_daily.csv.gz", parse_dates=["date"])
    daily = daily[daily.date <= END_DATE]
    rows, clim, months_all = [], [], {}
    for _, s in sel.iterrows():
        d = daily[daily.station == s.station]
        ms = monthly(d, "sal_mean", "sal_n")
        months_all[s.station] = ms
        ann = ms.groupby(ms.index.year).agg(["mean", "count"])
        ann = ann.loc[ann["count"] >= 9, "mean"]
        ann.index = pd.to_datetime(ann.index.astype(str) + "-07-01")
        res = seasonal_mk(ms)
        res13 = seasonal_mk(ms.loc["2013-01-01":])  # sensitivity: common window 2013-2025
        wl = longest_geoid_run(d)
        wres = seasonal_mk(monthly(wl, "wl_navd88_ft_mean", "wl_n")) if len(wl) else None
        sal = d.sal_mean.dropna()
        cm = ms.groupby(ms.index.month).mean()
        r = {"station": s.station, "group": s.group, "basin": s.basin, "lat": s.lat, "lon": s.lon,
             "veg_type": s.veg_type, "days_with_salinity": int(sal.size),
             "sal_mean": sal.mean(), "sal_median": sal.median(), "sal_p10": sal.quantile(0.1),
             "sal_p90": sal.quantile(0.9), "sal_max_daily": sal.max(),
             "pct_days_gt_2ppt": 100 * (sal > 2).mean(), "pct_days_gt_5ppt": 100 * (sal > 5).mean(),
             "peak_month": int(cm.idxmax()), "low_month": int(cm.idxmin()),
             "seasonal_range_ppt": cm.max() - cm.min()}
        if res:
            r.update({"mk_trend": res["trend"], "mk_p": res["p"], "mk_tau": res["tau"],
                      "sen_ppt_per_decade": 10 * res["sen_per_yr"], "trend_start": res["start"],
                      "trend_end": res["end"], "trend_n_months": res["n_months"]})
        if res13:
            r.update({"mk13_trend": res13["trend"], "mk13_p": res13["p"],
                      "sen13_ppt_per_decade": 10 * res13["sen_per_yr"]})
        if wres:
            r.update({"wl_trend": wres["trend"], "wl_p": wres["p"],
                      "wl_sen_mm_per_yr": wres["sen_per_yr"] * 304.8,
                      "wl_start": wres["start"], "wl_end": wres["end"],
                      "wl_geoid": wl.geoid.iloc[0]})
        rows.append(r)
        for m, v in cm.items():
            clim.append({"station": s.station, "group": s.group, "month": m, "sal_mean": v})
        balloon_chart(s.station, ms, ann, res, GROUP_COLORS[s.group], CHART_DIR / f"{s.station}.png")

    out = pd.DataFrame(rows)
    out["mk_q_fdr"] = bh_fdr(out.get("mk_p", pd.Series(np.nan, index=out.index)))
    out["mk13_q_fdr"] = bh_fdr(out.get("mk13_p", pd.Series(np.nan, index=out.index)))
    out["wl_q_fdr"] = bh_fdr(out.get("wl_p", pd.Series(np.nan, index=out.index)))
    out.to_csv(TAB_DIR / "crms_station_summary.csv", index=False, float_format="%.4g")
    climdf = pd.DataFrame(clim)
    climdf.pivot(index="station", columns="month", values="sal_mean").to_csv(
        TAB_DIR / "crms_monthly_climatology.csv", float_format="%.3f")

    # group-level summary
    gs = out.groupby("group").agg(stations=("station", "size"), median_sal=("sal_median", "median"),
                                  sig_increase=("mk_q_fdr", lambda q: int(((q < 0.05) & (out.loc[q.index, "sen_ppt_per_decade"] > 0)).sum())),
                                  sig_decrease=("mk_q_fdr", lambda q: int(((q < 0.05) & (out.loc[q.index, "sen_ppt_per_decade"] < 0)).sum())),
                                  median_sen_ppt_dec=("sen_ppt_per_decade", "median"),
                                  sig_increase_2013=("mk13_q_fdr", lambda q: int(((q < 0.05) & (out.loc[q.index, "sen13_ppt_per_decade"] > 0)).sum())),
                                  sig_decrease_2013=("mk13_q_fdr", lambda q: int(((q < 0.05) & (out.loc[q.index, "sen13_ppt_per_decade"] < 0)).sum())),
                                  median_sen13_ppt_dec=("sen13_ppt_per_decade", "median"),
                                  median_wl_mm_yr=("wl_sen_mm_per_yr", "median"))
    gs.to_csv(TAB_DIR / "crms_group_trend_summary.csv", float_format="%.3f")
    print(out[["station", "group", "sal_median", "mk_trend", "mk_p", "mk_q_fdr", "sen_ppt_per_decade",
               "sen13_ppt_per_decade", "mk13_q_fdr", "peak_month", "wl_sen_mm_per_yr", "wl_q_fdr"]].to_string(index=False))
    print(gs.to_string())

    # Figure: Maurepas monthly salinity small multiples
    mau = out[out.group == "Lake Maurepas"].sort_values("lat", ascending=False)
    n = len(mau)
    ncol = 3
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(10, 1.9 * nrow), sharex=True, squeeze=False)
    for ax, (_, r) in zip(axes.flat, mau.iterrows()):
        ms = months_all[r.station]
        ax.plot(ms.index, ms.values, color=GROUP_COLORS["Lake Maurepas"], lw=1)
        qs = "q<0.001" if r.mk_q_fdr < 0.001 else f"q={r.mk_q_fdr:.3f}"
        lab = f"Sen {r.sen_ppt_per_decade:+.2f} ppt/decade, {qs}" if pd.notna(r.get("mk_p")) else "too short for test"
        ax.set_title(f"{r.station}  ({lab})", fontsize=8, loc="left", color=INK)
        ax.set_ylim(bottom=0)
        ax.xaxis.set_major_locator(mdates.YearLocator(4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    fig.supylabel("Monthly mean salinity (ppt)", fontsize=9)
    fig.suptitle("CRMS hydro stations around Lake Maurepas: monthly mean salinity", fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig2_maurepas_monthly_salinity.png")
    plt.close(fig)

    # Figure: seasonal climatology heat map (single-hue sequential), all selected stations
    order = out.sort_values(["group", "sal_median"]).station
    piv = climdf.pivot(index="station", columns="month", values="sal_mean").loc[order]
    fig, ax = plt.subplots(figsize=(8, 0.28 * len(piv) + 1.4))
    im = ax.imshow(np.log10(piv.values + 0.1), aspect="auto", cmap="Blues")
    ax.set_yticks(range(len(piv)), [f"{s}  ({out.set_index('station').loc[s, 'group'].replace(' key site', '')})" for s in piv.index], fontsize=7)
    ax.set_xticks(range(12), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.grid(False)
    for i in range(piv.shape[0]):
        for j in range(12):
            v = piv.values[i, j]
            ax.text(j, i, f"{v:.1f}" if v < 10 else f"{v:.0f}", ha="center", va="center", fontsize=6,
                    color="white" if np.log10(v + 0.1) > np.log10(piv.values + 0.1).max() * 0.6 else INK)
    cb = fig.colorbar(im, ax=ax, shrink=0.6)
    ticks = [0.2, 1, 5, 20]
    cb.set_ticks(np.log10(np.array(ticks) + 0.1), labels=[str(t) for t in ticks])
    cb.set_label("Mean salinity (ppt, log scale)")
    ax.set_title("Mean salinity by calendar month (all years through 2025)", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig3_salinity_seasonal_climatology.png")
    plt.close(fig)

    # Figure: Sen slopes, full record vs 2013-2025, filled = FDR q < 0.05
    o = out.dropna(subset=["sen_ppt_per_decade"]).sort_values(["group", "sen_ppt_per_decade"])
    fig, ax = plt.subplots(figsize=(10, 0.26 * len(o) + 1.4))
    y = np.arange(len(o))
    for yi, (_, r) in zip(y, o.iterrows()):
        c = GROUP_COLORS[r.group]
        ax.plot([r.sen_ppt_per_decade, r.sen13_ppt_per_decade], [yi, yi], color=GRID, lw=1.5, zorder=1)
        ax.scatter(r.sen_ppt_per_decade, yi, s=42, marker="o", zorder=3, edgecolor=c, linewidth=1.5,
                   facecolor=c if r.mk_q_fdr < 0.05 else "white")
        ax.scatter(r.sen13_ppt_per_decade, yi, s=42, marker="D", zorder=3, edgecolor=INK, linewidth=1,
                   facecolor=INK if r.mk13_q_fdr < 0.05 else "white")
    ax.set_yticks(y, [f"{s} ({g.replace(' key site', '')})" for s, g in zip(o.station, o.group)], fontsize=7)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Seasonal Sen slope of monthly salinity (ppt per decade)")
    from matplotlib.lines import Line2D
    hs = [Line2D([], [], marker="o", lw=0, color=c, ms=6, label=f"full record: {g.replace(' key site', '')}")
          for g, c in GROUP_COLORS.items()]
    hs += [Line2D([], [], marker="D", lw=0, color=INK, ms=5, label="2013 to 2025 only"),
           Line2D([], [], marker="o", lw=0, markerfacecolor="white", markeredgecolor=MUTED, ms=6,
                  label="open marker = not significant")]
    ax.legend(handles=hs, fontsize=7, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.set_title("Salinity trends (seasonal Mann-Kendall, filled = FDR q < 0.05)", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig4_salinity_trend_slopes.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
