"""Step 2: stream the 15 GB CRMS hourly CSV out of its zip and reduce it to daily means.

Uses `unzip -p` piped into `awk` (scripts/02_daily.awk) because this is far faster than
reading 15 GB in Python. Requires unzip and awk (macOS, Linux, or WSL on Windows).
Output: RAW_DIR/work/crms_daily_all.csv.gz (all CRMS hydro stations, coastwide).
Run: python -I scripts/02_build_crms_daily.py
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import RAW_DIR, WORK_DIR  # noqa: E402

ZIP = RAW_DIR / "crms" / "CRMS_Continuous_Hydrographic.zip"
AWK = Path(__file__).resolve().parent / "02_daily.awk"
RAW_OUT = WORK_DIR / "crms_daily_sums.csv"
OUT = WORK_DIR / "crms_daily_all.csv.gz"


def main():
    if not RAW_OUT.exists():
        cmd = (f'unzip -p "{ZIP}" CRMS_Continuous_Hydrographic.csv | '
               f'LC_ALL=C awk -f "{AWK}" > "{RAW_OUT}.part" && mv "{RAW_OUT}.part" "{RAW_OUT}"')
        print("streaming hourly CSV (takes several minutes)...")
        subprocess.run(cmd, shell=True, check=True)
    d = pd.read_csv(RAW_OUT, dtype={"geoid": str})
    d["date"] = pd.to_datetime(d["date"], format="%m/%d/%Y")
    g = d.groupby(["station", "date"], as_index=False).agg(
        sal_sum=("sal_sum", "sum"), sal_n=("sal_n", "sum"), wl_sum=("wl_sum", "sum"),
        wl_n=("wl_n", "sum"), temp_sum=("temp_sum", "sum"), temp_n=("temp_n", "sum"),
        hours=("hours", "sum"), geoid=("geoid", "last"))
    for v in ("sal", "wl", "temp"):
        g[f"{v}_mean"] = (g[f"{v}_sum"] / g[f"{v}_n"]).where(g[f"{v}_n"] > 0)
    # require at least 12 valid hourly values for a daily mean
    for v in ("sal", "wl", "temp"):
        g.loc[g[f"{v}_n"] < 12, f"{v}_mean"] = float("nan")
    out = g[["station", "date", "sal_mean", "sal_n", "wl_mean", "wl_n", "temp_mean", "temp_n", "hours", "geoid"]]
    out = out.rename(columns={"wl_mean": "wl_navd88_ft_mean", "temp_mean": "temp_c_mean"})
    out.to_csv(OUT, index=False, compression="gzip")
    print(f"stations: {out.station.nunique()}, station-days: {len(out)}, "
          f"dates {out.date.min().date()} to {out.date.max().date()}")


if __name__ == "__main__":
    main()
