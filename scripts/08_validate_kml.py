"""Step 8: validate the KMZ.

1. Opens the KMZ as a zip and parses doc.kml with lxml (well-formed XML check).
2. Validates doc.kml against the OGC KML 2.2 schema plus the Google gx extension schema
   (XSD files fetched from schemas.opengis.net and developers.google.com, cached in RAW_DIR).
3. Structural checks: every referenced image is inside the KMZ, every placemark has
   coordinates inside the study box, the tour has FlyTo steps and every AnimatedUpdate
   targets an existing placemark id.
Writes outputs/tables/kml_validation_report.txt and exits non-zero on failure.
Run: python -I scripts/08_validate_kml.py
"""
import re
import sys
import zipfile
from pathlib import Path

import requests
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import KMZ_DIR, RAW_DIR, TAB_DIR  # noqa: E402

KMZ = KMZ_DIR / "louisiana_coastal_wetlands.kmz"
SCHEMAS = {
    "ogckml22.xsd": "http://schemas.opengis.net/kml/2.2.0/ogckml22.xsd",
    "atom-author-link.xsd": "http://schemas.opengis.net/kml/2.2.0/atom-author-link.xsd",
    "xAL.xsd": "http://docs.oasis-open.org/election/external/xAL.xsd",
    "kml22gx.xsd": "https://developers.google.com/kml/schema/kml22gx.xsd",
}
NS = {"k": "http://www.opengis.net/kml/2.2", "gx": "http://www.google.com/kml/ext/2.2"}
BOX = (-92.0, 28.5, -89.0, 31.0)  # lon/lat sanity box


def get_schemas():
    d = RAW_DIR / "schemas"
    d.mkdir(exist_ok=True)
    for name, url in SCHEMAS.items():
        p = d / name
        if not p.exists():
            p.write_bytes(requests.get(url, timeout=60).content)
    # point imports at the local copies
    for name in SCHEMAS:
        p = d / name
        t = p.read_text(encoding="utf-8")
        t = re.sub(r'schemaLocation="[^"]*/(ogckml22|atom-author-link|xAL)\.xsd"',
                   lambda m: f'schemaLocation="{m.group(1)}.xsd"', t)
        p.write_text(t, encoding="utf-8")
    wrapper = d / "kml_with_gx.xsd"
    wrapper.write_text(
        '<?xml version="1.0"?>\n<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'targetNamespace="urn:local:wrapper">\n'
        '  <xs:import namespace="http://www.opengis.net/kml/2.2" schemaLocation="ogckml22.xsd"/>\n'
        '  <xs:import namespace="http://www.google.com/kml/ext/2.2" schemaLocation="kml22gx.xsd"/>\n'
        '</xs:schema>\n', encoding="utf-8")
    return etree.XMLSchema(etree.parse(str(wrapper)))


def main():
    report, ok = [], True
    with zipfile.ZipFile(KMZ) as z:
        names = set(z.namelist())
        kml_name = "doc.kml"
        root = etree.fromstring(z.read(kml_name))
    report.append(f"KMZ: {KMZ.name}, {KMZ.stat().st_size / 1e6:.2f} MB, {len(names)} entries")
    report.append(f"[pass] doc.kml parsed by lxml, root element {etree.QName(root).localname}")

    schema = get_schemas()
    if schema.validate(root):
        report.append("[pass] doc.kml is valid against OGC KML 2.2 + Google gx 2.2 XSD")
    else:
        ok = False
        report.append(f"[FAIL] XSD validation: {len(schema.error_log)} errors")
        for e in list(schema.error_log)[:20]:
            report.append(f"   line {e.line}: {e.message}")

    pms = root.findall(".//k:Placemark", NS)
    ids = {p.get("id") for p in pms}
    pts = root.findall(".//k:Point/k:coordinates", NS)
    bad = 0
    for c in pts:
        lon, lat = map(float, c.text.strip().split(",")[:2])
        if not (BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]):
            bad += 1
    report.append(f"[{'pass' if bad == 0 else 'FAIL'}] {len(pts)} point placemarks, {bad} outside the study box")
    ok &= bad == 0
    polys = root.findall(".//k:Polygon", NS)
    report.append(f"[{'pass' if polys else 'FAIL'}] {len(polys)} basin polygon parts")
    ok &= bool(polys)

    hrefs = [h.text.strip() for h in root.findall(".//k:Icon/k:href", NS)]
    imgs = re.findall(r"<img src='([^']+)'", etree.tostring(root, encoding="unicode").replace("&lt;", "<").replace("&gt;", ">"))
    local = [h for h in hrefs + imgs if not h.startswith("http")]
    missing = [h for h in local if h not in names]
    report.append(f"[{'pass' if not missing else 'FAIL'}] {len(local)} local image references "
                  f"({len(imgs)} balloon charts, ground overlay), missing: {missing}")
    ok &= not missing

    tours = root.findall(".//gx:Tour", NS)
    flys = root.findall(".//gx:Tour//gx:FlyTo", NS)
    upd = root.findall(".//gx:Tour//gx:AnimatedUpdate//k:Placemark", NS)
    targets_ok = all(u.get("targetId") in ids for u in upd)
    report.append(f"[{'pass' if tours and flys and targets_ok else 'FAIL'}] {len(tours)} gx:Tour, "
                  f"{len(flys)} gx:FlyTo, {len(upd)} balloon updates, all targets exist: {targets_ok}")
    ok &= bool(tours and flys and targets_ok)

    report.append("RESULT: " + ("PASS" if ok else "FAIL"))
    txt = "\n".join(report)
    print(txt)
    (TAB_DIR / "kml_validation_report.txt").write_text(txt + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
