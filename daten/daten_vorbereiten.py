"""Datenpaket für die IuN-Projekte erzeugen (für Lehrende, nicht für Studierende).

Erzeugt aus den großen Rohdaten die kleinen Dateien, die Studierende mit
`daten/herunterladen.py` bekommen:

- dortmund-gtfs.zip           Fahrplan (gtfs.de), auf Dortmund und Umgebung zugeschnitten
- dortmund-wege.osm.pbf       OSM-Auszug mit Wegen und Haltestellen für MOTIS
- dortmund-sued-wege.osm.bz2  Wegenetz Dortmund-Süd für OSMnx
- dortmund-sued-hoehen.tif    Geländehöhen für denselben Ausschnitt (5-m-Raster)
- dortmund-grenze.geojson     Stadtgrenze Dortmund (für das Raster der Reisezeitkarte)
- stand.json                  Quellen, Stand und Gültigkeit des Fahrplans

Braucht nur Python-Pakete (pip install pandas osmium rasterio pyproj shapely), läuft
unter Windows, macOS und Linux. Aufruf im Wurzelverzeichnis des Repositorys:

    python daten/daten_vorbereiten.py --rohdaten PFAD --gtfs gtfs-de-free-JJMMTT.zip \
        --osm arnsberg-regbez-JJMMTT.osm.pbf muenster-regbez-JJMMTT.osm.pbf --dgm1

Rohdaten (in den Ordner --rohdaten legen):
- GTFS Deutschland gesamt: https://download.gtfs.de/germany/free/latest.zip (CC BY 4.0)
- OSM: https://download.geofabrik.de/europe/germany/nordrhein-westfalen.html (ODbL),
  Regierungsbezirke Arnsberg und Münster mit demselben Stand
- Höhen: DGM1 von Geobasis NRW, wird mit --dgm1 kachelweise geladen (etwa 240 MB,
  Datenlizenz Deutschland Zero 2.0). Alternative: --dgm DATEI für ein fertiges Raster
  in geografischen Koordinaten, etwa Copernicus DEM GLO-30.

Wichtig: Der Feed von gtfs.de deckt nur rund einen Monat ab. Das Paket also etwa
monatlich und nach jedem Fahrplanwechsel neu erzeugen.
"""

import argparse
import bz2
import csv
import io
import json
import shutil
import time
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

DGM1_VERZEICHNIS = "https://www.opengeodata.nrw.de/produkte/geobasis/hm/dgm1_tiff/dgm1_tiff/"

# Wege, die für Fuß, Rad und Rollstuhl nicht in Frage kommen (wie im Paket vom Oktober)
OHNE_HIGHWAY = {"motorway", "motorway_link", "trunk", "trunk_link", "proposed",
                "construction", "platform", "raceway", "bus_guideway", "abandoned", "razed"}
OHNE_SERVICE = {"parking_aisle", "driveway", "drive-through"}


# ---------------------------------------------------------------- Fahrplan (GTFS)

def gtfs_zuschneiden(gtfs_zip: Path, bbox, ziel: Path, chunk=2_000_000):
    """Behält nur Halte im Rechteck und die Fahrten, die dort mindestens zweimal halten."""
    lon_min, lat_min, lon_max, lat_max = bbox
    t0 = time.time()
    z = zipfile.ZipFile(gtfs_zip)

    def lies(name):
        return pd.read_csv(z.open(name), dtype=str, keep_default_na=False, encoding="utf-8")

    stops = lies("stops.txt")
    lat = stops.stop_lat.astype(float)
    lon = stops.stop_lon.astype(float)
    innen = (lon >= lon_min) & (lon <= lon_max) & (lat >= lat_min) & (lat <= lat_max)
    halte = set(stops.stop_id[innen & (stops.location_type.isin(["", "0"]))])
    print(f"Haltepunkte im Rechteck: {len(halte)}")

    # stop_times ist sehr groß (über 2 GB entpackt): stückweise lesen
    teile = []
    for i, st in enumerate(pd.read_csv(z.open("stop_times.txt"), dtype=str,
                                       keep_default_na=False, chunksize=chunk,
                                       encoding="utf-8")):
        teile.append(st[st.stop_id.isin(halte)])
        if i % 10 == 0:
            print(f"  stop_times: {(i + 1) * chunk / 1e6:.0f} Mio. Zeilen gelesen")
    st = pd.concat(teile, ignore_index=True)
    # Fahrten, die nach dem Zuschnitt nur noch einen Halt haben, sind nutzlos
    anzahl = st.groupby("trip_id").stop_id.transform("size")
    st = st[anzahl >= 2].copy()
    st["_seq"] = st.stop_sequence.astype(int)
    st = st.sort_values(["trip_id", "_seq"]).drop(columns="_seq")
    fahrten = set(st.trip_id)

    trips = lies("trips.txt")
    trips = trips[trips.trip_id.isin(fahrten)]
    routes = lies("routes.txt")
    routes = routes[routes.route_id.isin(set(trips.route_id))]
    agency = lies("agency.txt")
    agency = agency[agency.agency_id.isin(set(routes.agency_id))]
    dienste = set(trips.service_id)
    cal = lies("calendar.txt")
    cal = cal[cal.service_id.isin(dienste)]
    cald = lies("calendar_dates.txt")
    cald = cald[cald.service_id.isin(dienste)]
    benutzt = set(st.stop_id)
    eltern = set(stops.parent_station[stops.stop_id.isin(benutzt)]) - {""}
    stops = stops[stops.stop_id.isin(benutzt | eltern)]

    ziel.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as out:
        for name, df in [("agency.txt", agency), ("routes.txt", routes),
                         ("trips.txt", trips), ("stops.txt", stops),
                         ("stop_times.txt", st), ("calendar.txt", cal),
                         ("calendar_dates.txt", cald)]:
            puffer = io.StringIO()
            df.to_csv(puffer, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
            out.writestr(name, puffer.getvalue().encode("utf-8"))
        for name in ["feed_info.txt", "attributions.txt"]:
            if name in z.namelist():
                out.writestr(name, z.read(name))
    tage = sorted(set(cald.date[cald.exception_type == "1"]) | set(cal.start_date) | set(cal.end_date))
    gueltig = {"von": min(cal.start_date.min(), tage[0]), "bis": max(cal.end_date.max(), tage[-1])}
    print(f"GTFS fertig: {ziel} ({ziel.stat().st_size / 1e6:.1f} MB), "
          f"{len(stops)} Halte, {len(trips)} Fahrten, {len(st)} Halteereignisse, "
          f"Gültigkeit {gueltig['von']}-{gueltig['bis']}, {time.time() - t0:.0f} s")
    return {"halte": len(stops), "fahrten": len(trips), "halteereignisse": len(st),
            "gueltig_von": gueltig["von"], "gueltig_bis": gueltig["bis"]}


# ---------------------------------------------------------------- Wege (OpenStreetMap)

def _fuer_routenplaner(tags):
    return ("highway" in tags or "public_transport" in tags or "railway" in tags
            or tags.get("amenity") in ("parking", "bicycle_parking", "bicycle_rental"))


def _fuer_osmnx(tags):
    return ("highway" in tags and tags["highway"] not in OHNE_HIGHWAY
            and tags.get("service") not in OHNE_SERVICE and tags.get("area") != "yes")


def _ausschnitt(quelle: Path, bbox, ziel: Path, schluessel, weg_ok, knoten_ok=None,
                relation_ok=None):
    """Schreibt passende Wege, die das Rechteck berühren, vollständig (mit allen ihren
    Knoten) nach `ziel`; außerdem passende Knoten im Rechteck und Relationen, die einen
    der geschriebenen Wege oder Knoten enthalten. `schluessel` filtert vorab (schnell)
    auf Objekte, die mindestens eines dieser Merkmale tragen."""
    import osmium
    lon_min, lat_min, lon_max, lat_max = bbox
    wege, knoten = set(), set()
    with osmium.BackReferenceWriter(str(ziel), ref_src=str(quelle), overwrite=True,
                                    remove_tags=False) as aus:
        for o in (osmium.FileProcessor(str(quelle)).with_locations()
                  .with_filter(osmium.filter.KeyFilter(*schluessel))):
            if o.is_node():
                if (knoten_ok and len(o.tags) and knoten_ok(o.tags)
                        and lon_min <= o.lon <= lon_max and lat_min <= o.lat <= lat_max):
                    knoten.add(o.id)
                    aus.add_node(o)
            elif o.is_way():
                if weg_ok(o.tags) and any(
                        n.location.valid() and lon_min <= n.lon <= lon_max
                        and lat_min <= n.lat <= lat_max for n in o.nodes):
                    wege.add(o.id)
                    aus.add_way(o)
            elif o.is_relation() and relation_ok and relation_ok(o.tags):
                if any((m.type == "w" and m.ref in wege) or (m.type == "n" and m.ref in knoten)
                       for m in o.members):
                    aus.add_relation(o)
    return len(wege)


def _zusammenfuehren(dateien, ziel: Path):
    """Führt mehrere OSM-Dateien sortiert zusammen; doppelte Objekte nur einmal."""
    import osmium
    if len(dateien) == 1:
        shutil.copyfile(dateien[0], ziel)
        return
    leser = osmium.MergeInputReader()
    for f in dateien:
        leser.add_file(str(f))
    schreiber = osmium.WriteHandler(str(ziel))
    try:
        leser.apply(schreiber, simplify=True)
    finally:
        schreiber.close()


def osm_zuschneiden(osm_dateien, bbox, ziel: Path, sued_bbox, osmnx_ziel: Path):
    t0 = time.time()
    teile = []
    for i, quelle in enumerate(osm_dateien):
        teil = ziel.with_name(f"_teil{i}.osm.pbf")
        n = _ausschnitt(Path(quelle), bbox, teil,
                        ("highway", "public_transport", "railway", "amenity", "type"),
                        _fuer_routenplaner, _fuer_routenplaner,
                        lambda t: t.get("type") in ("restriction", "route")
                        or _fuer_routenplaner(t))
        print(f"  {Path(quelle).name}: {n} Wege im Rechteck, {time.time() - t0:.0f} s")
        teile.append(teil)
    ziel.unlink(missing_ok=True)
    _zusammenfuehren(teile, ziel)
    for t in teile:
        t.unlink(missing_ok=True)
    print(f"OSM für MOTIS: {ziel} ({ziel.stat().st_size / 1e6:.1f} MB)")

    # Für OSMnx: nur begeh- und befahrbare Wege, kleiner Ausschnitt, als .osm.bz2 (XML)
    roh = osmnx_ziel.with_name("_wege.osm")
    n = _ausschnitt(ziel, sued_bbox, roh, ("highway",), _fuer_osmnx)
    with open(roh, "rb") as ein, bz2.open(osmnx_ziel, "wb") as aus:
        shutil.copyfileobj(ein, aus, 1 << 20)
    roh.unlink()
    print(f"OSM für OSMnx: {osmnx_ziel} ({osmnx_ziel.stat().st_size / 1e6:.1f} MB), "
          f"{n} Wege, {time.time() - t0:.0f} s")


def grenze_ausschneiden(quelle: Path, ziel: Path, name="Dortmund", admin_level="6"):
    """Stadtgrenze als GeoJSON (für das Raster der Reisezeitkarte)."""
    import osmium
    from shapely.geometry import mapping, shape
    t0 = time.time()
    fp = (osmium.FileProcessor(str(quelle))
          .with_areas(osmium.filter.TagFilter(("admin_level", admin_level)))
          .with_filter(osmium.filter.TagFilter(("admin_level", admin_level)))
          .with_filter(osmium.filter.GeoInterfaceFilter()))
    for o in fp:
        if o.is_area() and o.tags.get("name") == name and o.tags.get("boundary") == "administrative":
            geo = shape(o.__geo_interface__["geometry"]).simplify(0.0002)
            ziel.write_text(json.dumps({
                "type": "Feature",
                "properties": {"name": name, "quelle": "© OpenStreetMap-Mitwirkende (ODbL)"},
                "geometry": json.loads(json.dumps(mapping(geo)))}, ensure_ascii=False),
                encoding="utf-8")
            print(f"Stadtgrenze: {ziel} ({ziel.stat().st_size / 1e3:.0f} kB), "
                  f"{time.time() - t0:.0f} s")
            return
    raise SystemExit(f"Grenze von {name} nicht gefunden")


# ---------------------------------------------------------------- Höhen

def dgm1_laden(bbox, ordner: Path):
    """Lädt die DGM1-Kacheln (1 km x 1 km, EPSG:25832) für das Rechteck, falls sie fehlen."""
    from pyproj import Transformer
    nach_utm = Transformer.from_crs(4326, 25832, always_xy=True)
    ecken = [nach_utm.transform(x, y) for x in (bbox[0], bbox[2]) for y in (bbox[1], bbox[3])]
    e0, e1 = int(min(e[0] for e in ecken) // 1000), int(max(e[0] for e in ecken) // 1000)
    n0, n1 = int(min(e[1] for e in ecken) // 1000), int(max(e[1] for e in ecken) // 1000)
    ordner.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(DGM1_VERZEICHNIS + "index.json", timeout=120) as r:
        index = json.load(r)
    namen = {}
    for f in index["datasets"][0]["files"]:
        teile = f["name"].split("_")              # dgm1_32_386_5702_1_nw_2022.tif
        namen[(int(teile[2]), int(teile[3]))] = f["name"]
    kacheln = []
    for e in range(e0, e1 + 1):
        for n in range(n0, n1 + 1):
            name = namen.get((e, n))
            if name is None:
                continue
            datei = ordner / name
            if not datei.exists():
                teil = datei.with_suffix(".teil")
                urllib.request.urlretrieve(DGM1_VERZEICHNIS + name, teil)
                teil.rename(datei)
            kacheln.append(datei)
    print(f"DGM1: {len(kacheln)} Kacheln, "
          f"{sum(k.stat().st_size for k in kacheln) / 1e6:.0f} MB in {ordner}")
    return kacheln


def hoehen_aus_dgm1(kacheln, bbox, ziel: Path, meter=5):
    """Mittelt die 1-m-Kacheln auf `meter` Meter, setzt sie zusammen und rechnet sie in
    geografische Koordinaten (EPSG:4326) um, damit OSMnx das Raster direkt lesen kann."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import reproject

    t0 = time.time()
    grenzen = []
    for k in kacheln:
        with rasterio.open(k) as src:
            grenzen.append(src.bounds)
    w, s = min(b.left for b in grenzen), min(b.bottom for b in grenzen)
    e, n = max(b.right for b in grenzen), max(b.top for b in grenzen)
    breite, hoehe = round((e - w) / meter), round((n - s) / meter)
    mosaik = np.full((hoehe, breite), np.nan, dtype="float32")
    for k in kacheln:
        with rasterio.open(k) as src:
            b = src.bounds
            form = (round((b.top - b.bottom) / meter), round((b.right - b.left) / meter))
            a = src.read(1, out_shape=form, resampling=Resampling.average, masked=True)
            a = a.astype("float32").filled(np.nan)
        zeile, spalte = round((n - b.top) / meter), round((b.left - w) / meter)
        mosaik[zeile:zeile + form[0], spalte:spalte + form[1]] = a
    quelle_transform = from_origin(w, n, meter, meter)

    dx, dy = meter / 69_300, meter / 111_200       # Grad je `meter` Meter bei 51,5° Nord
    zb, zh = round((bbox[2] - bbox[0]) / dx), round((bbox[3] - bbox[1]) / dy)
    ziel_transform = from_origin(bbox[0], bbox[3], dx, dy)
    aus = np.full((zh, zb), np.nan, dtype="float32")
    reproject(mosaik, aus, src_transform=quelle_transform, src_crs="EPSG:25832",
              src_nodata=np.nan, dst_transform=ziel_transform, dst_crs="EPSG:4326",
              dst_nodata=np.nan, resampling=Resampling.bilinear)
    aus = np.round(aus, 1)                          # Dezimeter genügen und packen besser
    with rasterio.open(ziel, "w", driver="GTiff", width=zb, height=zh, count=1,
                       dtype="float32", crs="EPSG:4326", transform=ziel_transform,
                       nodata=np.nan, compress="deflate", predictor=3, zlevel=9,
                       tiled=True, blockxsize=256, blockysize=256) as dst:
        dst.write(aus, 1)
    print(f"Höhen (DGM1, {meter} m): {ziel} ({ziel.stat().st_size / 1e6:.1f} MB), "
          f"{zb}x{zh} Punkte, {np.nanmin(aus):.0f}-{np.nanmax(aus):.0f} m, "
          f"{np.isnan(aus).mean():.1%} ohne Wert, {time.time() - t0:.0f} s")


def hoehen_zuschneiden(dgm: Path, bbox, ziel: Path):
    """Alternative: Ausschnitt aus einem fertigen Raster (z. B. Copernicus DEM GLO-30)."""
    import rasterio
    from rasterio.windows import from_bounds
    with rasterio.open(dgm) as src:
        fenster = from_bounds(*bbox, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=fenster)
        profil = src.profile.copy()
        for k in ["blockxsize", "blockysize", "interleave", "tiled"]:
            profil.pop(k, None)
        profil.update(width=a.shape[1], height=a.shape[0], driver="GTiff",
                      compress="deflate", transform=src.window_transform(fenster))
    with rasterio.open(ziel, "w", **profil) as dst:
        dst.write(a, 1)
    print(f"Höhen: {ziel} ({ziel.stat().st_size / 1e3:.0f} kB)")


# ---------------------------------------------------------------- Aufruf

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--rohdaten", type=Path, default=Path("."),
                   help="Ordner mit den Rohdaten (relative Dateinamen beziehen sich darauf)")
    p.add_argument("--gtfs", type=Path, help="GTFS Deutschland von gtfs.de")
    p.add_argument("--osm", type=Path, nargs="*", help="OSM-Auszüge (.osm.pbf) von Geofabrik")
    p.add_argument("--dgm1", action="store_true",
                   help="Höhen aus dem DGM1 von Geobasis NRW (lädt fehlende Kacheln)")
    p.add_argument("--dgm", type=Path, help="stattdessen: fertiges Höhenraster (EPSG:4326)")
    p.add_argument("--bbox", default="7.15,51.38,7.70,51.62",
                   help="lon_min,lat_min,lon_max,lat_max (Dortmund und Umgebung)")
    p.add_argument("--sued-bbox", default="7.37,51.465,7.53,51.525",
                   help="kleinerer Ausschnitt für OSMnx (Hbf, Campus, Phoenix-See)")
    p.add_argument("--name", default="dortmund")
    p.add_argument("--ziel", type=Path, default=Path(__file__).resolve().parent)
    a = p.parse_args()
    bbox = [float(x) for x in a.bbox.split(",")]
    sued = [float(x) for x in a.sued_bbox.split(",")]
    rand = [sued[0] - 0.01, sued[1] - 0.005, sued[2] + 0.01, sued[3] + 0.005]
    a.ziel.mkdir(parents=True, exist_ok=True)
    roh = lambda f: f if f.is_absolute() else a.rohdaten / f

    stand = dict(erzeugt=date.today().isoformat(), bbox=bbox, sued_bbox=sued)
    if a.gtfs:
        stand["gtfs"] = {"quelle": a.gtfs.name, "lizenz": "gtfs.de / DELFI e.V., CC BY 4.0",
                         **gtfs_zuschneiden(roh(a.gtfs), bbox, a.ziel / f"{a.name}-gtfs.zip")}
    if a.osm:
        dateien = [roh(f) for f in a.osm]
        osm_zuschneiden(dateien, bbox, a.ziel / f"{a.name}-wege.osm.pbf", sued,
                        a.ziel / f"{a.name}-sued-wege.osm.bz2")
        grenze_ausschneiden(dateien[0], a.ziel / f"{a.name}-grenze.geojson")
        stand["osm"] = {"quelle": [f.name for f in a.osm],
                        "lizenz": "© OpenStreetMap-Mitwirkende, ODbL"}
    if a.dgm1:
        kacheln = dgm1_laden(rand, a.rohdaten / "dgm1")
        hoehen_aus_dgm1(kacheln, rand, a.ziel / f"{a.name}-sued-hoehen.tif")
        stand["hoehen"] = {"quelle": "DGM1, Geobasis NRW", "raster_m": 5,
                           "lizenz": "Datenlizenz Deutschland Zero 2.0"}
    elif a.dgm:
        hoehen_zuschneiden(roh(a.dgm), rand, a.ziel / f"{a.name}-sued-hoehen.tif")
        stand["hoehen"] = {"quelle": a.dgm.name}
    # Vorhandene Angaben behalten (das Skript kann in Teilen aufgerufen werden)
    stand_datei = a.ziel / "stand.json"
    if stand_datei.exists():
        stand = {**json.loads(stand_datei.read_text(encoding="utf-8")), **stand}
    stand_datei.write_text(json.dumps(stand, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
