"""Grundkarte für die Webdemo aus OpenStreetMap-Daten (für Lehrende).

Die Webdemo lädt keine Kartenkacheln von fremden Servern. Stattdessen zeichnet sie diese
kleine Grundkarte selbst: Gewässer, größere Grünflächen, Bahnstrecken, Hauptstraßen und
die Namen der Ortsteile in und um Dortmund.

Aufruf im Wurzelverzeichnis (braucht das pip-Paket osmium, siehe daten/requirements-lehrende.txt):

    python werkzeuge/grundkarte.py ARNSBERG.osm.pbf MUENSTER.osm.pbf

Ergebnis: webdemo/daten/grundkarte.json (GeoJSON; Eigenschaft "k" = Klasse, "n" = Name).
Daten: © OpenStreetMap-Mitwirkende, ODbL. Die Datei ist eine abgeleitete Datenbank und steht
ebenfalls unter der ODbL.
"""

import argparse
import json
import math
import time
from pathlib import Path

import osmium
import shapely
from shapely.geometry import box, mapping, shape

ZIEL = Path(__file__).resolve().parent.parent / "webdemo" / "daten" / "grundkarte.json"
RECHTECK = (7.27, 51.40, 7.67, 51.615)          # Dortmund mit etwas Rand (west, süd, ost, nord)
VEREINFACHEN = 0.00006                          # Grad, etwa 4 bis 7 Meter
STRASSEN = {"motorway": "autobahn", "trunk": "bundesstrasse", "primary": "hauptstrasse",
            "secondary": "nebenstrasse"}
ORTE = {"city", "town", "borough", "suburb", "quarter"}
MIN_FLAECHE_M2 = {"wasser": 5_000, "gruen": 50_000}


def klasse_flaeche(t):
    if t.get("natural") == "water" or t.get("landuse") == "reservoir" or t.get("waterway") == "riverbank":
        return "wasser"
    if t.get("leisure") == "park" or t.get("landuse") == "forest" or t.get("natural") == "wood":
        return "gruen"
    return None


def klasse_linie(t):
    if t.get("tunnel") in ("yes", "building_passage"):
        return None
    if t.get("highway") in STRASSEN:
        return STRASSEN[t["highway"]]
    if t.get("railway") in ("rail", "light_rail") and "service" not in t:
        return "bahn"
    if t.get("waterway") in ("river", "canal"):
        return "fluss"
    return None


def flaeche_m2(geometrie):
    """Fläche in Quadratmetern, genähert (Grad in Meter bei 51,5° Nord)."""
    return geometrie.area * 111_320 * math.cos(math.radians(51.5)) * 110_540


def _gerundet(koordinaten):
    if isinstance(koordinaten[0], (int, float)):
        return [round(koordinaten[0], 5), round(koordinaten[1], 5)]
    return [_gerundet(k) for k in koordinaten]


def lesen(datei: Path, rahmen, gesehen: set, merkmale: list):
    """Liest passende Objekte aus einer OSM-Datei und hängt sie an `merkmale` an."""
    schluessel = ("natural", "landuse", "leisure", "waterway", "railway", "highway", "place")
    fp = (osmium.FileProcessor(str(datei))
          .with_areas(osmium.filter.KeyFilter("natural", "landuse", "leisure", "waterway"))
          .with_filter(osmium.filter.KeyFilter(*schluessel))
          .with_filter(osmium.filter.GeoInterfaceFilter()))
    for o in fp:
        t = dict(o.tags)
        if o.is_node():
            if t.get("place") in ORTE and "name" in t and rahmen.contains(shape(o.__geo_interface__["geometry"])):
                art = ("o", o.id)
                if art not in gesehen:
                    gesehen.add(art)
                    merkmale.append(({"k": "ort", "art": t["place"], "n": t["name"]},
                                     o.__geo_interface__["geometry"]))
            continue
        if o.is_area():
            k = klasse_flaeche(t)
            art = ("a", o.id)
        elif o.is_way():
            k = klasse_linie(t)
            art = ("w", o.id)
        else:
            continue
        if k is None or art in gesehen:
            continue
        g = shape(o.__geo_interface__["geometry"])
        if not g.intersects(rahmen):
            continue
        g = g.intersection(rahmen)
        if o.is_area() and flaeche_m2(g) < MIN_FLAECHE_M2[k]:
            continue
        g = shapely.simplify(g, VEREINFACHEN, preserve_topology=True)
        if g.is_empty:
            continue
        gesehen.add(art)
        merkmale.append(({"k": k}, mapping(g)))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("osm", type=Path, nargs="+", help="OSM-Auszüge (.osm.pbf)")
    p.add_argument("--ziel", type=Path, default=ZIEL)
    a = p.parse_args()
    t0 = time.time()
    rahmen = box(*RECHTECK)
    gesehen, merkmale = set(), []
    for datei in a.osm:
        lesen(datei, rahmen, gesehen, merkmale)
        print(f"{datei.name}: {len(merkmale)} Objekte, {time.time() - t0:.0f} s")
    reihenfolge = {"gruen": 0, "wasser": 1, "fluss": 2, "nebenstrasse": 3, "hauptstrasse": 4,
                   "bundesstrasse": 5, "autobahn": 6, "bahn": 7, "ort": 8}
    merkmale.sort(key=lambda m: reihenfolge[m[0]["k"]])
    sammlung = {
        "type": "FeatureCollection",
        "quelle": "© OpenStreetMap-Mitwirkende, ODbL; " + ", ".join(d.name for d in a.osm),
        "features": [{"type": "Feature", "properties": e,
                      "geometry": {"type": g["type"], "coordinates": _gerundet(g["coordinates"])}}
                     for e, g in merkmale],
    }
    a.ziel.write_text(json.dumps(sammlung, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    zaehler = {}
    for e, _ in merkmale:
        zaehler[e["k"]] = zaehler.get(e["k"], 0) + 1
    print(f"{a.ziel}: {a.ziel.stat().st_size / 1e6:.2f} MB, {zaehler}, {time.time() - t0:.0f} s")
