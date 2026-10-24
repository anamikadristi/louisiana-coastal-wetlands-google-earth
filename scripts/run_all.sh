#!/usr/bin/env bash
# Run the whole pipeline in order. Usage: bash scripts/run_all.sh
# Optional: export LCW_RAW_DIR=/path/with/space  (about 1.5 GB of downloads)
set -euo pipefail
cd "$(dirname "$0")/.."
for s in 01_download_data 02_build_crms_daily 03_select_stations 04_salinity_trends \
         05_land_loss_by_basin 06_maps 07_build_kmz 08_validate_kml; do
  echo "== $s"
  python -I "scripts/$s.py"
done
