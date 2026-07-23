"""One-time build: MA town boundaries -> simplified GeoJSON for the
dashboard map. Source shapefile is already WGS84 degrees (verified via
.prj); simplify tolerance 0.0015 deg ~ 150 m.
"""
import json
import sys
from pathlib import Path

import shapefile
from shapely.geometry import shape as shp_shape, mapping

SRC = r"C:\Project ISO\data\shapefiles\massachusetts_towns.shp"
OUT = Path(__file__).resolve().parent.parent / "reference" / "ma_towns.geojson"


def main():
    r = shapefile.Reader(SRC)
    town_idx = [f[0] for f in r.fields[1:]].index("TOWN")
    feats = []
    for sr in r.iterShapeRecords():
        geom = shp_shape(sr.shape.__geo_interface__).simplify(0.0015)
        feats.append({
            "type": "Feature",
            "properties": {"TOWN": sr.record[town_idx].title()},
            "geometry": mapping(geom),
        })
    gj = {"type": "FeatureCollection", "features": feats}
    OUT.write_text(json.dumps(gj, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {len(feats)} towns)")


if __name__ == "__main__":
    main()
