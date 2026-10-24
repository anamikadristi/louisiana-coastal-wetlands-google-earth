"""Step 7: build the Google Earth KMZ with simplekml.

Contents of outputs/kmz/louisiana_coastal_wetlands.kmz:
  * CRMS stations: styled placemarks (one colour per group) with HTML balloons that show the
    station's summary statistics and a small salinity chart packed inside the KMZ.
  * USGS NWIS active sites in the study box, with the parameters they report.
  * CWPPRA hydrologic basin boundaries (semi-transparent polygons).
  * Persistent land change 1932 to 2015/16 (USGS SIM 3381) as a ground overlay.
  * A guided tour (gx:Tour) that flies through the key sites and opens their balloons.
Run: python -I scripts/07_build_kmz.py
"""
import json
import math
import re
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import simplekml
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CHART_DIR, DATA_DIR, KMZ_DIR, STUDY_BASINS, TAB_DIR, WORK_DIR  # noqa: E402

KMZ = KMZ_DIR / "louisiana_coastal_wetlands.kmz"
GROUP_RGB = {"Lake Maurepas": (42, 120, 214), "Pontchartrain key site": (235, 104, 52),
             "Barataria key site": (27, 175, 122), "Terrebonne key site": (237, 161, 0)}
BASIN_RGB = {"Pontchartrain": (235, 104, 52), "Barataria": (27, 175, 122), "Terrebonne": (237, 161, 0)}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
ICON = "http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"
NWIS_ICON = "http://maps.google.com/mapfiles/kml/shapes/triangle.png"


def fmt(v, nd=2, suffix=""):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:.{nd}f}{suffix}"


def station_balloon(r, img_href):
    trend = "not tested (record too short)"
    if isinstance(r.get("mk_trend"), str):
        sig = "significant" if r.mk_q_fdr < 0.05 else "not significant"
        trend = (f"{r.mk_trend}, Sen slope {r.sen_ppt_per_decade:+.2f} ppt/decade, "
                 f"p = {r.mk_p:.3g}, FDR q = {r.mk_q_fdr:.3g} ({sig}); "
                 f"{r.trend_start} to {r.trend_end}")
    t13 = "n/a"
    if isinstance(r.get("mk13_trend"), str):
        t13 = (f"{r.mk13_trend}, Sen slope {r.sen13_ppt_per_decade:+.2f} ppt/decade, "
               f"FDR q = {r.mk13_q_fdr:.3g}")
    wl = "n/a"
    if isinstance(r.get("wl_trend"), str):
        wl = (f"{r.wl_sen_mm_per_yr:+.1f} mm/yr ({r.wl_trend}, FDR q = {r.wl_q_fdr:.3g}), "
              f"{r.wl_start} to {r.wl_end}, {r.wl_geoid}")
    rows = [("Group", r.group), ("Basin", r.basin), ("Vegetation type", str(r.veg_type).title()),
            ("Days with salinity", f"{int(r.days_with_salinity):,}"),
            ("Median daily salinity", fmt(r.sal_median, 2, " ppt")),
            ("10th to 90th percentile", f"{fmt(r.sal_p10)} to {fmt(r.sal_p90)} ppt"),
            ("Days above 2 ppt", fmt(r.pct_days_gt_2ppt, 1, " %")),
            ("Saltiest / freshest month", f"{MONTHS[int(r.peak_month) - 1]} / {MONTHS[int(r.low_month) - 1]}"),
            ("Seasonal range of monthly means", fmt(r.seasonal_range_ppt, 2, " ppt")),
            ("Salinity trend (seasonal Mann-Kendall)", trend),
            ("Salinity trend, 2013 to 2025 only", t13),
            ("Water level trend (NAVD88)", wl)]
    trs = "".join(f"<tr><td style='color:#52514e;padding:2px 8px 2px 0;vertical-align:top'>{k}</td>"
                  f"<td style='padding:2px 0'>{v}</td></tr>" for k, v in rows)
    site = r.station[:8]
    return (f"<div style='font-family:Arial,sans-serif;font-size:12px;width:400px'>"
            f"<h3 style='margin:0 0 4px 0'>{r.station}</h3>"
            f"<img src='{img_href}' width='396' alt='Monthly salinity chart for {r.station}'/>"
            f"<table style='font-size:11px;border-collapse:collapse'>{trs}</table>"
            f"<p style='font-size:10px;color:#52514e'>Data: CPRA CRMS continuous hydrographic record (CIMS). "
            f"Daily means from hourly adjusted values; statistics through 2025. "
            f"Look up site {site} in the <a href='https://www.lacoast.gov/crms_viewer/Map/CRMSViewer'>CRMS Viewer</a>.</p></div>")


FEATURE_ORDER = ["name", "visibility", "open", "author", "link", "address", "phoneNumber", "Snippet",
                 "description", "LookAt", "Camera", "TimeStamp", "TimeSpan", "styleUrl", "Style", "StyleMap",
                 "Region", "ExtendedData"]
VIEW_ORDER = ["longitude", "latitude", "altitude", "heading", "tilt", "range", "altitudeMode"]


def schema_order(doc):
    """simplekml writes some children out of the order the KML 2.2 XSD requires
    (shared Style before a Folder's name, LookAt range after altitudeMode). Reorder them."""
    root = etree.fromstring(doc.encode("utf-8"))
    ns = "{http://www.opengis.net/kml/2.2}"

    def rank(el, order, default):
        name = etree.QName(el).localname if isinstance(el.tag, str) else ""
        return order.index(name) if name in order else default

    for tag in ("Document", "Folder", "Placemark", "GroundOverlay"):
        for el in root.iter(ns + tag):
            kids = list(el)
            kids.sort(key=lambda k: rank(k, FEATURE_ORDER, len(FEATURE_ORDER)))  # stable sort
            el[:] = kids
    for tag in ("LookAt", "Camera"):
        for el in root.iter(ns + tag):
            kids = list(el)
            kids.sort(key=lambda k: rank(k, VIEW_ORDER, len(VIEW_ORDER)))
            el[:] = kids
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode("utf-8")


def add_polygon(folder, name, geom, style, desc):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    mg = folder.newmultigeometry(name=name, description=desc)
    for p in polys:
        pol = mg.newpolygon(outerboundaryis=list(p.exterior.coords))
        if p.interiors:
            pol.innerboundaryis = [list(i.coords) for i in p.interiors]
        pol.tessellate = 1
    mg.style = style
    return mg


def main():
    summ = pd.read_csv(TAB_DIR / "crms_station_summary.csv")
    nwis = pd.read_csv(DATA_DIR / "nwis_sites_study_area.csv", dtype={"site_no": str})
    basins = gpd.read_file(DATA_DIR / "basins_coastal_simplified.geojson")
    lc = pd.read_csv(TAB_DIR / "land_change_by_basin.csv").set_index("basin")

    kml = simplekml.Kml(name="Louisiana coastal wetlands: CRMS stations, land change and basins")
    kml.document.description = ("Independent analysis of public CPRA CRMS and USGS data by Anamika Dristi, Ph.D. "
                                "Open the Tours folder and play the tour for a guided fly-through.")

    # styles
    styles = {}
    for g, (r, gg, b) in GROUP_RGB.items():
        st = simplekml.Style()
        st.iconstyle.icon.href = ICON
        st.iconstyle.color = simplekml.Color.rgb(r, gg, b)
        st.iconstyle.scale = 1.2
        st.labelstyle.scale = 0.7
        st.balloonstyle.text = "$[description]"
        styles[g] = st
    nst = simplekml.Style()
    nst.iconstyle.icon.href = NWIS_ICON
    nst.iconstyle.color = simplekml.Color.rgb(74, 58, 167)
    nst.iconstyle.scale = 0.7
    nst.labelstyle.scale = 0

    # basins
    fb = kml.newfolder(name="CWPPRA hydrologic basins (CPRA)")
    for _, r in basins.iterrows():
        rgb = BASIN_RGB.get(r.basin, (120, 120, 120))
        ps = simplekml.Style()
        ps.polystyle.color = simplekml.Color.changealphaint(40 if r.basin in BASIN_RGB else 18, simplekml.Color.rgb(*rgb))
        ps.linestyle.color = simplekml.Color.rgb(*rgb)
        ps.linestyle.width = 2.5 if r.basin in BASIN_RGB else 1
        d = ""
        if r.basin in lc.index:
            x = lc.loc[r.basin]
            d = (f"<b>{r.basin} basin</b><br/>Persistent land loss 1932 to 2016: {x.loss_km2:,.0f} km&#178;<br/>"
                 f"Persistent land gain: {x.gain_km2:,.0f} km&#178;<br/>Net change: {x.net_change_km2:,.0f} km&#178;<br/>"
                 f"Source: USGS SIM 3381 raster, this repository's zonal summary.")
        add_polygon(fb, r.basin, r.geometry, ps, d)

    # land change overlay
    bnd = json.loads((WORK_DIR / "landchange_overlay_bounds.json").read_text())
    ov_href = kml.addfile(str(WORK_DIR / "landchange_overlay.png"))
    go = kml.newgroundoverlay(name="Persistent land change 1932 to 2015 (USGS SIM 3381, about 90 m display)")
    go.icon.href = ov_href
    go.latlonbox.west, go.latlonbox.east = bnd["west"], bnd["east"]
    go.latlonbox.south, go.latlonbox.north = bnd["south"], bnd["north"]
    go.color = simplekml.Color.changealphaint(210, simplekml.Color.white)
    go.description = ("Dark red: land lost 1932-1973; red: 1973-1990; orange: 1990-2015; green: land gained. "
                      "Couvillion et al. 2017, https://doi.org/10.3133/sim3381")
    go.visibility = 0

    # CRMS stations
    fs = kml.newfolder(name="CRMS hydro stations (analysed)")
    sub = {g: fs.newfolder(name=g) for g in GROUP_RGB}
    pts = {}
    for _, r in summ.iterrows():
        href = kml.addfile(str(CHART_DIR / f"{r.station}.png"))
        p = sub[r.group].newpoint(name=r.station, coords=[(r.lon, r.lat)])
        p.description = station_balloon(r, href)
        p.style = styles[r.group]
        p.snippet.content = f"{r.group}; median salinity {r.sal_median:.2f} ppt"
        p.snippet.maxlines = 1
        pts[r.station] = p

    # NWIS
    fn = kml.newfolder(name=f"USGS NWIS active sites ({len(nwis)})")
    fn.visibility = 1
    labels = {"gage_height": "gage height", "discharge": "discharge", "spec_cond": "specific conductance",
              "salinity": "salinity", "water_temp": "water temperature", "wl_navd88": "water level NAVD88"}
    for _, r in nwis.iterrows():
        par = ", ".join(v for k, v in labels.items() if r[k] == 1) or "other parameters"
        p = fn.newpoint(name=r.site_no, coords=[(r.lon, r.lat)])
        p.style = nst
        p.description = (f"<b>USGS {r.site_no}</b><br/>{r.station_nm}<br/>Instantaneous values: {par}<br/>"
                         f"Record {r.iv_begin} to {r.iv_end}<br/>Basin: {r.basin}<br/>"
                         f"<a href='https://waterdata.usgs.gov/monitoring-location/{r.site_no}/'>USGS page</a>")

    # Tour
    tour = kml.newgxtour(name="Tour: Lake Maurepas to the Barataria and Terrebonne basins")
    pl = tour.newgxplaylist()

    def fly(lon, lat, rng, tilt=45, heading=0, dur=5.0, wait=2.0):
        f = pl.newgxflyto(gxduration=dur)
        f.flytomode = "smooth"
        f.lookat = simplekml.LookAt(longitude=lon, latitude=lat, altitude=0, range=rng, tilt=tilt,
                                    heading=heading, altitudemode=simplekml.AltitudeMode.relativetoground)
        pl.newgxwait(gxduration=wait)

    def balloon(station, show):
        au = pl.newgxanimatedupdate(gxduration=0.5)
        au.update.change = (f'<Placemark targetId="{pts[station].placemark.id}">'
                            f'<gx:balloonVisibility>{1 if show else 0}</gx:balloonVisibility></Placemark>')

    fly(-90.6, 29.6, 260000, tilt=0, dur=4, wait=2)
    fly(-90.515, 30.255, 45000, tilt=40, dur=6, wait=2)
    order = summ.assign(o=summ.group.map({g: i for i, g in enumerate(GROUP_RGB)})).sort_values(["o", "lat"], ascending=[True, False])
    # Maurepas: 7 stations spread around the lake (sorted by bearing from the lake centre)
    m = order[order.group == "Lake Maurepas"].copy()
    m["bearing"] = (np.degrees(np.arctan2(m.lon + 90.515, m.lat - 30.255)) + 360) % 360
    m = m.sort_values("bearing")
    tour_stations = list(m.station.iloc[np.unique(np.linspace(0, len(m) - 1, 7).round().astype(int))])
    for b in STUDY_BASINS:
        tour_stations += list(order[order.group == f"{b} key site"].station)
    for i, s in enumerate(tour_stations):
        r = summ.set_index("station").loc[s]
        fly(r.lon, r.lat, 9000, tilt=50, heading=(i * 30) % 360, dur=5, wait=0.5)
        balloon(s, True)
        pl.newgxwait(gxduration=5)
        balloon(s, False)
    fly(-90.6, 29.6, 260000, tilt=0, dur=6, wait=1)

    # simplekml numbers its ids ("12"); XML ids must start with a letter, so prefix them
    doc = kml.kml(format=True)
    doc = re.sub(r'\b(id|targetId)="(\d+)"', r'\1="k\2"', doc)
    doc = re.sub(r"<styleUrl>#(\d+)</styleUrl>", r"<styleUrl>#k\1</styleUrl>", doc)
    doc = schema_order(doc)
    (WORK_DIR / "doc_preview.kml").write_text(doc, encoding="utf-8")
    with zipfile.ZipFile(KMZ, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", doc)  # first entry, as Google Earth expects
        for src in sorted(CHART_DIR.glob("*.png")) + [WORK_DIR / "landchange_overlay.png"]:
            z.write(src, f"files/{src.name}")
    print(f"KMZ written: {KMZ.name}, {KMZ.stat().st_size / 1e6:.2f} MB, stations {len(summ)}, "
          f"NWIS {len(nwis)}, tour stops {len(tour_stations)}")


if __name__ == "__main__":
    main()
