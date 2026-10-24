"""Step 1: download all public inputs (keyless) into RAW_DIR and unzip the GIS layers.

The CRMS continuous hydrographic export is about 1.3 GB zipped (15 GB CSV). It is never
extracted to disk; step 2 streams it.
Run: python -I scripts/01_download_data.py
"""
import datetime as dt
import json
import sys
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import RAW_DIR, SOURCES  # noqa: E402


def fetch(url, dest, force=False):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"  exists: {dest.name}")
        return
    print(f"  downloading {dest.name}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.rename(dest)


def main():
    log = {}
    for key, (url, rel) in SOURCES.items():
        dest = RAW_DIR / rel
        fetch(url, dest)
        log[key] = {"url": url, "file": rel, "bytes": dest.stat().st_size,
                    "accessed": dt.date.today().isoformat()}
    for z in ["gis/CRMS_Sites.zip", "gis/Data_Collection_Stations.zip", "gis/Basins.zip"]:
        out = RAW_DIR / z.replace(".zip", "")
        if not out.exists():
            with zipfile.ZipFile(RAW_DIR / z) as zf:
                zf.extractall(out)
    (RAW_DIR / "download_log.json").write_text(json.dumps(log, indent=2))
    for k, v in log.items():
        print(f"{k:12s} {v['bytes'] / 1e6:10.1f} MB  {v['accessed']}")


if __name__ == "__main__":
    main()
