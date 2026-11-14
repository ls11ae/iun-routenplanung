"""Szenarien für Projekt 1 „Was wäre, wenn …? Eine bessere Verbindung zum Campus“.

Ein Szenario ist eine geänderte Kopie des Fahrplans (GTFS). Dieses Modul hilft beim
Entwerfen, Durchrechnen und Vergleichen; das Original in daten/ bleibt immer unberührt.

    import szenarien as sz
    g = sz.gtfs_laden()                                          # Fahrplan als Tabellen
    neu = sz.takt_verdoppeln(g, "X13", "06:00", "09:00", tag)    # Beispiel: Takt verdoppeln
    datei = sz.gtfs_schreiben(neu, sz.ORDNER / "x13" / "gtfs.zip")
    sz.kennzahlen(g, neu, tag, linien=["X13"])                   # zusätzliche Fahrzeugkilometer, -stunden
    vorher = sz.motis_rechnen(sz.GTFS, "basis")                  # Reisezeiten zum Campus mit MOTIS
    nachher = sz.motis_rechnen(datei, "x13", strassen=vorher)
    tabelle, werte = sz.vergleichen(vorher, nachher)             # Wirkung, gewichtet mit Einwohnern
    sz.abbildung(tabelle)                                        # Karten vorher, nachher, Differenz

Die Reisezeiten rechnet reisezeitkarte.py genauso wie für die Karte der Webdemo: Median über
die Abfahrten 7:00 bis 8:00 Uhr, Tür zu Tür, Wartezeit zählt mit. Ein Beispiel mit allen
Schritten steht in szenario_beispiel.ipynb.
"""

import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gtfs_hilfen as h  # noqa: E402
import motis_einrichten as me  # noqa: E402
import reisezeitkarte as rk  # noqa: E402

GTFS = me.GTFS                                     # der Fahrplan aus dem Datenpaket (nur lesen)
ORDNER = me.ORDNER / "szenarien"                   # je Szenario ein Unterordner (nicht im Git)
PORT = 8090                                        # Port der Szenario-Server (der Hauptserver hat 8080)


# ---------------------------------------------------------------- Fahrplan laden und schreiben

def gtfs_laden(pfad=GTFS) -> dict:
    """Alle Tabellen eines GTFS-Zips als Wörterbuch Name -> DataFrame (alle Werte als Text,
    damit beim Schreiben nichts verändert wird)."""
    g = {}
    with zipfile.ZipFile(pfad) as z:
        for name in z.namelist():
            if name.endswith(".txt"):
                with z.open(name) as f:
                    g[name[:-4]] = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8")
    return g


def gtfs_schreiben(g: dict, ziel) -> Path:
    """Schreibt die Tabellen als GTFS-Zip nach `ziel`. Das Original des Datenpakets wird nie
    überschrieben."""
    ziel = Path(ziel)
    if ziel.resolve() == Path(GTFS).resolve():
        raise ValueError("Das Original des Fahrplans wird nicht überschrieben; bitte einen anderen Namen wählen.")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ziel, "w") as z:
        for name, df in g.items():
            puffer = io.StringIO()
            df.to_csv(puffer, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
            # feste Zeitangabe: gleicher Fahrplan, gleiche Datei (so erkennt motis_rechnen ihn wieder)
            info = zipfile.ZipInfo(f"{name}.txt", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, puffer.getvalue().encode("utf-8"), compresslevel=1)
    return ziel


def _uhrzeit(sekunden) -> list:
    """Sekunden seit Mitternacht als 'HH:MM:SS' (auch über 24 Uhr hinaus, wie in GTFS)."""
    return [f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}" for s in np.asarray(sekunden, dtype=int)]


def fahrten_der_linie(g: dict, linie: str) -> pd.DataFrame:
    """Alle Fahrten einer Linie (route_short_name) mit erster Abfahrt (Sekunden), Anfangs- und
    Endhalt. Anfangs- und Endhalt zusammen stehen für Richtung und Laufweg."""
    routen = set(g["routes"].route_id[g["routes"].route_short_name == linie])
    if not routen:
        raise ValueError(f"Keine Linie {linie!r} im Fahrplan.")
    trips = g["trips"][g["trips"].route_id.isin(routen)]
    st = g["stop_times"][g["stop_times"].trip_id.isin(set(trips.trip_id))].copy()
    st["seq"] = st.stop_sequence.astype(int)
    st = st.sort_values(["trip_id", "seq"])
    f = st.groupby("trip_id").agg(ab=("departure_time", "first"), von=("stop_id", "first"),
                                  nach=("stop_id", "last"))
    f["ab_s"] = h.zeit_in_sekunden(f.ab)
    return f.join(trips.set_index("trip_id")[["service_id"]])


# ---------------------------------------------------------------- Ein Beispiel-Szenario

def takt_verdoppeln(g: dict, linie: str, von: str = "06:00", bis: str = "09:00", tag=None) -> dict:
    """Verdoppelt den Takt einer Linie zwischen `von` und `bis` (erste Abfahrt der Fahrt).

    Jede Fahrt in diesem Zeitfenster wird um den halben Takt versetzt kopiert. Den Takt
    bestimmen wir je Laufweg (Anfangs- und Endhalt) und Verkehrstag (service_id) als Median
    der Abstände zwischen den Abfahrten. Liegt dort schon eine Fahrt (höchstens 2 Minuten
    daneben), entfällt die Kopie. Die Kopien fahren an denselben Tagen wie ihre Vorbilder.
    Mit `tag` (date) nur die Fahrten, die an diesem Tag fahren, z. B. Dienstag, dann gilt
    die Änderung für alle Tage mit demselben Fahrplan; ohne `tag` für alle Verkehrstage.
    Gibt einen neuen Fahrplan zurück; `g` bleibt unverändert.
    """
    f = fahrten_der_linie(g, linie)
    if tag is not None:
        f = f[f.service_id.isin(h.aktive_dienste(g, tag))]
    lo, hi = h.zeit_in_sekunden(pd.Series([von + ":00", bis + ":00"]))
    namen = g["stops"].set_index("stop_id").stop_name
    neue, protokoll = {}, []
    for (dienst, a, b), gruppe in f.groupby(["service_id", "von", "nach"]):
        abfahrten = np.sort(gruppe.ab_s.to_numpy())
        if len(abfahrten) < 2:
            continue
        takt = int(np.median(np.diff(abfahrten)))
        if takt <= 0:
            continue
        versatz = takt // 2
        im_fenster = gruppe[(gruppe.ab_s >= lo) & (gruppe.ab_s < hi)]
        for trip_id, ab in zip(im_fenster.index, im_fenster.ab_s):
            if np.min(np.abs(abfahrten - (ab + versatz))) > 120:
                neue[trip_id] = versatz
        n = sum(t in neue for t in im_fenster.index)
        if n:
            protokoll.append({"Laufweg": f"{namen[a]} → {namen[b]}", "Verkehrstag (service_id)": dienst,
                              "Takt bisher (min)": round(takt / 60, 1), "zusätzliche Fahrten": n})
    trips, st = g["trips"], g["stop_times"]
    kopie_trips = trips[trips.trip_id.isin(neue)].copy()
    kopie_st = st[st.trip_id.isin(neue)].copy()
    versatz = kopie_st.trip_id.map(neue).to_numpy()
    kopie_st["arrival_time"] = _uhrzeit(h.zeit_in_sekunden(kopie_st.arrival_time) + versatz)
    kopie_st["departure_time"] = _uhrzeit(h.zeit_in_sekunden(kopie_st.departure_time) + versatz)
    kopie_trips["trip_id"] += "_takt"
    kopie_st["trip_id"] += "_takt"
    neu = dict(g)
    neu["trips"] = pd.concat([trips, kopie_trips], ignore_index=True)
    neu["stop_times"] = pd.concat([st, kopie_st], ignore_index=True)
    print(f"Linie {linie}: {len(neue)} zusätzliche Fahrten mit erster Abfahrt zwischen {von} und {bis} Uhr")
    if protokoll:
        print(pd.DataFrame(protokoll).to_string(index=False))
    return neu


def linien_entfernen(g: dict, linien) -> dict:
    """Ein Fahrplan ohne die Linien `linien` (route_short_name), z. B. ["HB1", "HB2"]:
    Ihre Fahrten und Haltezeiten fallen weg. `g` bleibt unverändert."""
    routen = set(g["routes"].route_id[g["routes"].route_short_name.isin(linien)])
    fahrten = set(g["trips"].trip_id[g["trips"].route_id.isin(routen)])
    print(f"{len(fahrten)} Fahrten der Linien {', '.join(linien)} entfernt")
    return dict(g, trips=g["trips"][~g["trips"].trip_id.isin(fahrten)],
                stop_times=g["stop_times"][~g["stop_times"].trip_id.isin(fahrten)])


# ---------------------------------------------------------------- Kosten: Fahrleistung

def fahrleistung(g: dict, tag, linien=None) -> pd.Series:
    """Fahrten, Fahrzeugkilometer und Fahrzeugstunden an einem Tag (date).

    Kilometer: Luftlinie zwischen aufeinanderfolgenden Halten, also etwas weniger als der
    tatsächliche Weg (der Fahrplan enthält keine Linienverläufe). Stunden: erste Abfahrt bis
    letzte Ankunft je Fahrt, ohne Wende- und Pausenzeiten. Mit `linien` nur diese Linien.
    """
    trips = g["trips"][g["trips"].service_id.isin(h.aktive_dienste(g, tag))]
    if linien is not None:
        routen = set(g["routes"].route_id[g["routes"].route_short_name.isin(linien)])
        trips = trips[trips.route_id.isin(routen)]
    st = g["stop_times"][g["stop_times"].trip_id.isin(set(trips.trip_id))].copy()
    st["seq"] = st.stop_sequence.astype(int)
    st = st.sort_values(["trip_id", "seq"])
    halte = g["stops"].set_index("stop_id")
    lat = halte.stop_lat.astype(float).reindex(st.stop_id).to_numpy()
    lon = halte.stop_lon.astype(float).reindex(st.stop_id).to_numpy()
    gleich = st.trip_id.to_numpy()[1:] == st.trip_id.to_numpy()[:-1]
    meter = h.entfernung_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    st["ab_s"] = h.zeit_in_sekunden(st.departure_time)
    st["an_s"] = h.zeit_in_sekunden(st.arrival_time)
    dauer = st.groupby("trip_id").agg(a=("ab_s", "min"), b=("an_s", "max"))
    return pd.Series({"Fahrten": len(trips),
                      "Fahrzeugkilometer": round(float(np.nansum(meter[gleich])) / 1000, 1),
                      "Fahrzeugstunden": round(float((dauer.b - dauer.a).sum()) / 3600, 1)}, dtype=object)


def kennzahlen(vorher: dict, nachher: dict, tag, linien=None) -> pd.DataFrame:
    """Fahrleistung vorher und nachher an einem Tag und ihre Differenz (das kostet das Szenario)."""
    a, b = fahrleistung(vorher, tag, linien), fahrleistung(nachher, tag, linien)
    differenz = pd.Series([round(y - x, 1) for x, y in zip(a, b)], index=a.index, dtype=object)
    return pd.DataFrame({"vorher": a, "nachher": b, "Differenz": differenz})


# ---------------------------------------------------------------- Einwohner

def einwohner(punkte, raster_m: int = 500) -> list:
    """Einwohner (Zensus 2022) je Rasterzelle. Aus daten/dortmund-einwohner.csv (100-m-Gitter,
    im Datenpaket ab daten-2026-12); fehlt die Datei, aus den Werten je 500-m-Zelle, die in
    webdemo/daten/reisezeiten.json stehen (`raster_m` muss dann ein Vielfaches von 500 sein)."""
    if rk.EINWOHNER.exists():
        return rk.einwohner_je_zelle(punkte, raster_m)
    if raster_m % 500:
        raise ValueError("Ohne daten/dortmund-einwohner.csv geht nur ein Raster von 500 m, 1000 m, …")
    from pyproj import Transformer
    D = json.loads(rk.AUSGABE.read_text(encoding="utf-8"))
    Z = D["zellen"]
    nach_utm = Transformer.from_crs(4326, rk.UTM, always_xy=True)
    x, y = nach_utm.transform(Z["lon"], Z["lat"])
    summe = {}
    for i, j, e in zip(np.floor(np.array(x) / raster_m), np.floor(np.array(y) / raster_m), Z["einwohner"]):
        summe[(int(i), int(j))] = summe.get((int(i), int(j)), 0) + e
    px, py = nach_utm.transform([p[1] for p in punkte], [p[0] for p in punkte])
    return [summe.get((int(i), int(j)), 0) for i, j in zip(np.floor(np.array(px) / raster_m), np.floor(np.array(py) / raster_m))]


# ---------------------------------------------------------------- Vergleich vorher – nachher

def vergleichen(vorher: dict, nachher: dict, grenze_min: float = 30):
    """Vergleicht zwei Ergebnisse von `motis_rechnen` (gleiche Rasterpunkte).

    Gibt (tabelle, werte) zurück: je Zelle die Reisezeit mit Bus und Bahn vorher, nachher und
    die Differenz (negativ = schneller), dazu Kennzahlen, gewichtet mit den Einwohnern:
    wie viele Menschen den Campus in höchstens `grenze_min` Minuten erreichen und wie lange
    sie im Mittel brauchen (nur Zellen mit Wert vorher und nachher). Die Reisezeit ist die
    mit Bus und Bahn; wer zu Fuß schneller ist, zählt mit der Gehzeit (wie in reisezeitkarte.py).
    """
    if vorher["lat"] != nachher["lat"] or vorher["lon"] != nachher["lon"]:
        raise ValueError("vorher und nachher müssen auf denselben Rasterpunkten gerechnet sein")
    t = pd.DataFrame({"lat": vorher["lat"], "lon": vorher["lon"], "einwohner": vorher["einwohner"],
                      "vorher": pd.to_numeric(pd.Series(vorher["oepnv_min"]), errors="coerce"),
                      "nachher": pd.to_numeric(pd.Series(nachher["oepnv_min"]), errors="coerce")})
    t["differenz"] = t.nachher - t.vorher
    beide = t.dropna(subset=["vorher", "nachher"])
    ew = beide.einwohner
    erreicht = lambda spalte: int(t.einwohner[t[spalte] <= grenze_min].sum())
    besser = beide[beide.differenz <= -1]
    werte = pd.Series({
        f"Menschen, die den Campus in höchstens {grenze_min:g} min erreichen: vorher": erreicht("vorher"),
        f"Menschen, die den Campus in höchstens {grenze_min:g} min erreichen: nachher": erreicht("nachher"),
        "mittlere Reisezeit (gewichtet mit Einwohnern, min): vorher": round(float((beide.vorher * ew).sum() / ew.sum()), 2),
        "mittlere Reisezeit (gewichtet mit Einwohnern, min): nachher": round(float((beide.nachher * ew).sum() / ew.sum()), 2),
        "Zellen mindestens 1 min schneller": len(besser),
        "Menschen in diesen Zellen": int(besser.einwohner.sum()),
        "Zellen mindestens 1 min langsamer": int((beide.differenz >= 1).sum()),
        "größte Verbesserung (min)": float(-beide.differenz.min()) if len(beide) else 0.0,
    }, dtype=object)
    return t, werte


# ---------------------------------------------------------------- Karten

# Klassen der Differenz nachher − vorher in Minuten: (Obergrenze einschließlich, Farbe, Schraffur, Text).
# Blau-Töne nach Okabe-Ito; „langsamer“ ist zusätzlich schraffiert.
DIFFERENZ_KLASSEN = [(-10, "#003f63", "", "10 min oder mehr schneller"),
                     (-5, "#0072B2", "", "5 bis unter 10 min schneller"),
                     (-2, "#56B4E9", "", "2 bis unter 5 min schneller"),
                     (-0.5, "#c4e3f5", "", "weniger als 2 min schneller"),
                     (0.5, "#e6e6e3", "", "unverändert"),
                     (np.inf, "#D55E00", "///", "langsamer")]
# Klassen der Reisezeit mit Bus und Bahn (Minuten, Obergrenze einschließlich, Text)
REISEZEIT_KLASSEN = [(20, "bis 20 min"), (30, "20 bis 30 min"), (45, "30 bis 45 min"),
                     (60, "45 bis 60 min"), (90, "60 bis 90 min"), (np.inf, "über 90 min")]


def differenz_klasse(d: float) -> int:
    """Nummer der Klasse in DIFFERENZ_KLASSEN für eine Differenz `d` in Minuten."""
    return next(i for i, k in enumerate(DIFFERENZ_KLASSEN) if d <= k[0])


def linienverlauf(g: dict, linie: str) -> list:
    """Halte (Breite, Länge) der Fahrt einer Linie mit den meisten Halten, zum Einzeichnen."""
    f = fahrten_der_linie(g, linie)
    st = g["stop_times"][g["stop_times"].trip_id.isin(set(f.index))]
    laengste = st.trip_id.value_counts().idxmax()
    st = st[st.trip_id == laengste]
    st = st.iloc[np.argsort(st.stop_sequence.astype(int).to_numpy())]
    halte = g["stops"].set_index("stop_id")
    return [(float(halte.stop_lat[s]), float(halte.stop_lon[s])) for s in st.stop_id]


def abbildung(tabelle: pd.DataFrame, raster_m: int = 500, verlauf=None, linie: str = ""):
    """Drei Karten nebeneinander (matplotlib): Reisezeit mit Bus und Bahn vorher, nachher und
    die Differenz. `verlauf` (Liste von (Breite, Länge), etwa aus `linienverlauf`) wird als
    gestrichelte Linie eingezeichnet. Gibt die Abbildung zurück (speichern mit .savefig)."""
    import matplotlib.pyplot as plt
    from matplotlib.collections import PatchCollection
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Rectangle

    dlon, dlat = rk.zelle_in_grad(rk.ZIEL, raster_m)
    farben = plt.get_cmap("viridis")(np.linspace(0.97, 0.05, len(REISEZEIT_KLASSEN)))
    grenze = rk.grenze_laden()
    fig, achsen = plt.subplots(1, 3, figsize=(16, 6.4))

    def zellen(ax, maske, farbe, schraffur=""):
        z = tabelle[maske]
        ecken = [Rectangle((lon - dlon / 2, lat - dlat / 2), dlon, dlat) for lat, lon in zip(z.lat, z.lon)]
        ax.add_collection(PatchCollection(ecken, facecolor=farbe, edgecolor="#888888" if schraffur else "white",
                                          linewidth=0.2, hatch=schraffur or None))

    for ax, spalte, titel in [(achsen[0], "vorher", "vorher"), (achsen[1], "nachher", "nachher"),
                              (achsen[2], "differenz", "nachher − vorher")]:
        werte = tabelle[spalte]
        if spalte == "differenz":
            klasse = werte.map(lambda d: differenz_klasse(d) if pd.notna(d) else -1)
            for i, k in enumerate(DIFFERENZ_KLASSEN):
                zellen(ax, klasse == i, k[1], k[2])
        else:
            grenzen = [k[0] for k in REISEZEIT_KLASSEN]
            klasse = werte.map(lambda m: int(np.searchsorted(grenzen, m)) if pd.notna(m) else -1)
            for i, farbe in enumerate(farben):
                zellen(ax, klasse == i, farbe)
        zellen(ax, werte.isna(), "white", "xx")
        for teil in getattr(grenze, "geoms", [grenze]):
            x, y = teil.exterior.xy
            ax.plot(x, y, color="#555555", linewidth=0.8)
        if verlauf:
            ax.plot([p[1] for p in verlauf], [p[0] for p in verlauf], color="black", linewidth=1.6,
                    linestyle=(0, (4, 2)))
        ax.plot(rk.ZIEL[1], rk.ZIEL[0], marker="*", markersize=14, color="black", markeredgecolor="white")
        ax.annotate("Campus Nord", (rk.ZIEL[1], rk.ZIEL[0]), xytext=(6, -12), textcoords="offset points", fontsize=9)
        ax.set_title(f"Reisezeit mit Bus und Bahn: {titel}", fontsize=11)
        ax.set_aspect(1 / np.cos(np.radians(rk.ZIEL[0])))
        ax.autoscale_view()
        ax.set_xticks([])
        ax.set_yticks([])
    keine = Patch(facecolor="white", edgecolor="#888888", hatch="xx", label="keine Verbindung")
    zeit = [Patch(facecolor=f, label=t) for f, (_, t) in zip(farben, REISEZEIT_KLASSEN)] + [keine]
    if verlauf:
        zeit.append(Line2D([], [], color="black", linestyle=(0, (4, 2)), label=f"Linie {linie}".strip()))
    diff = [Patch(facecolor=k[1], hatch=k[2] or None, edgecolor="#888888", label=k[3]) for k in DIFFERENZ_KLASSEN]
    fig.legend(handles=zeit, loc="lower center", bbox_to_anchor=(0.34, 0.0), ncol=4, fontsize=9, frameon=False)
    achsen[2].legend(handles=diff + [keine], loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2,
                     fontsize=9, frameon=False)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.17, wspace=0.03)
    return fig


def differenzkarte(tabelle: pd.DataFrame, raster_m: int = 500):
    """Interaktive Karte der Differenz nachher − vorher (folium, mit OpenStreetMap im
    Hintergrund), nur Zellen, die sich ändern. Blau: schneller, Orange mit gestricheltem Rand:
    langsamer; ein Tooltip nennt die Minuten und Einwohner jeder Zelle."""
    import folium
    dlon, dlat = rk.zelle_in_grad(rk.ZIEL, raster_m)
    karte = folium.Map(location=(51.515, 7.465), zoom_start=11, tiles="OpenStreetMap")
    for z in tabelle.itertuples():
        if pd.isna(z.differenz) or abs(z.differenz) <= 0.5:
            continue
        _, farbe, schraffur, text = DIFFERENZ_KLASSEN[differenz_klasse(z.differenz)]
        folium.Rectangle([(z.lat - dlat / 2, z.lon - dlon / 2), (z.lat + dlat / 2, z.lon + dlon / 2)],
                         color="black" if schraffur else "white", weight=1 if schraffur else 0.5,
                         dash_array="4" if schraffur else None, fill=True, fill_color=farbe, fill_opacity=0.75,
                         tooltip=f"{z.vorher:.0f} → {z.nachher:.0f} min ({text}), {z.einwohner} Einwohner").add_to(karte)
    folium.Marker(rk.ZIEL, tooltip="Campus Nord", icon=folium.Icon(color="black", icon="flag")).add_to(karte)
    zeilen = "".join(f'<div><span style="display:inline-block;width:14px;height:10px;background:{k[1]};'
                     f'border:1px {"dashed black" if k[2] else "solid #777"};margin-right:6px"></span>{k[3]}</div>'
                     for k in DIFFERENZ_KLASSEN if k[3] != "unverändert")
    legende = ('<div style="position:fixed;bottom:24px;left:12px;z-index:9999;background:white;padding:6px 9px;'
               f'border:1px solid #999;border-radius:4px;font:12px sans-serif"><b>Reisezeit nachher − vorher</b>{zeilen}</div>')
    karte.get_root().html.add_child(folium.Element(legende))
    return karte


# ---------------------------------------------------------------- Ein Szenario mit MOTIS rechnen

def _konfiguration(ordner: Path, gtfs: Path, port: int, erster: date, letzter: date):
    """config.yml für ein Szenario: wie beim Hauptserver, aber mit dem Fahrplan des Szenarios
    und seinem Zeitraum, eigenem Port und ohne Kartenkacheln (die braucht nur die Oberfläche
    im Browser)."""
    def pfad(p):
        try:
            return Path(os.path.relpath(p, ordner)).as_posix()
        except ValueError:                       # anderes Laufwerk unter Windows
            return Path(p).resolve().as_posix()
    zeilen, in_kacheln = [], False
    for z in (me.ORDNER / "config.yml").read_text(encoding="utf-8").splitlines():
        if z.startswith("tiles:"):
            in_kacheln = True
            continue
        if in_kacheln and z.startswith(" "):
            continue
        in_kacheln = False
        if z.startswith("osm:"):
            z = f"osm: {pfad(me.OSM)}"
        elif z.strip().startswith("path:"):
            z = z[: len(z) - len(z.lstrip())] + f"path: {pfad(gtfs)}"
        zeilen.append(z)
    text = "\n".join(zeilen) + "\n"
    text = me.yaml_setzen(text, "timetable", "first_day", erster.isoformat())
    text = me.yaml_setzen(text, "timetable", "num_days", (letzter - erster).days + 1)
    text = me.yaml_setzen(text, "server", "port", port)
    (ordner / "config.yml").write_text(text, encoding="utf-8", newline="\n")


def _pruefsumme(datei: Path) -> str:
    return hashlib.sha256(Path(datei).read_bytes()).hexdigest()[:16]


def motis_rechnen(gtfs, name: str, raster_m: int = 500, datum: str = "2026-11-24", von: str = "07:00",
                  bis: str = "08:00", schritt: int = 5, strassen: dict = None, punkte=None,
                  port: int = PORT, neu: bool = False, daten_behalten: bool = False) -> dict:
    """Rechnet die Reisezeiten zum Campus für den Fahrplan `gtfs` mit MOTIS.

    Je Szenario gibt es einen eigenen Ordner nahverkehr/motis/szenarien/<name>/ mit
    Konfiguration, Daten und dem Ergebnis (reisezeiten-500m.json). Das Straßennetz übernimmt das
    Szenario aus dem Hauptimport; MOTIS rechnet nur Fahrplan und Zuordnung neu (wenige
    Sekunden). Dann startet ein eigener Server (Port `port`), beantwortet die Anfragen wie in
    reisezeitkarte.py (Median über die Abfahrten von `von` bis `bis` am `datum`) und wird
    wieder beendet. Die Daten (etwa 150 MB) werden danach gelöscht, außer mit `daten_behalten`.

    `strassen`: ein früheres Ergebnis auf denselben Punkten (z. B. das „vorher“); dessen Zeiten
    zu Fuß, mit Rad und Auto werden übernommen, weil der Fahrplan sie nicht ändert.
    `punkte`: eigene Rasterpunkte statt des ganzen Rasters (etwa für einen schnellen Test).
    Ein vorhandenes Ergebnis mit gleichem Fahrplan und gleichen Einstellungen wird wiederverwendet.
    """
    gtfs, ordner = Path(gtfs), ORDNER / name
    if punkte is None:
        punkte = rk.raster_erzeugen(rk.grenze_laden(), raster_m)
    stempel = {"gtfs": _pruefsumme(gtfs), "raster_m": raster_m, "datum": datum, "von": von, "bis": bis,
               "schritt": schritt, "punkte": hashlib.sha256(json.dumps(punkte).encode()).hexdigest()[:16]}
    ergebnis = ordner / f"reisezeiten-{raster_m}m.json"
    if ergebnis.exists() and not neu:
        alt = json.loads(ergebnis.read_text(encoding="utf-8"))
        if alt["stempel"] == stempel:
            print(f"{name}: vorhandenes Ergebnis wiederverwendet (gerechnet in "
                  f"{alt['dauer_s']['import'] + alt['dauer_s']['anfragen']} s)")
            return alt["zellen"]
    erster, letzter = me.fahrplan_zeitraum(None, gtfs)
    if not erster <= date.fromisoformat(datum) <= letzter:
        raise ValueError(f"Der {datum} liegt nicht im Fahrplan {gtfs.name} ({erster:%d.%m.%Y} bis {letzter:%d.%m.%Y}).")
    if strassen is not None and list(zip(strassen["lat"], strassen["lon"])) != [tuple(p) for p in punkte]:
        raise ValueError("`strassen` muss auf denselben Rasterpunkten gerechnet sein")
    if me.port_belegt(me.RECHNER, port):
        raise SystemExit(f"Port {port} ist belegt: Läuft noch ein anderer Szenario-Server? Bitte beenden.")

    # MOTIS und der Hauptimport (beim ersten Mal etwa zwei Minuten), dann eine Kopie für das Szenario
    programm = me.motis_laden()
    me.importieren(programm)
    t0 = time.time()
    ordner.mkdir(parents=True, exist_ok=True)
    if not (ordner / "data").is_dir():
        shutil.copytree(me.ORDNER / "data", ordner / "data", ignore=shutil.ignore_patterns("tiles", "logs"))
    _konfiguration(ordner, gtfs, port, erster, letzter)
    with open(ordner / "import.log", "w", encoding="utf-8") as log:
        subprocess.run([str(programm), "import"], cwd=ordner, check=True, stdout=log, stderr=subprocess.STDOUT)
    t_import = time.time() - t0

    with open(ordner / "server.log", "w", encoding="utf-8") as log:
        server = subprocess.Popen([str(programm), "server"], cwd=ordner, stdout=log, stderr=subprocess.STDOUT)
    adresse = f"http://{me.RECHNER}:{port}"
    try:
        for _ in range(240):                   # auf den Server warten (meist 1 bis 2 Sekunden)
            if server.poll() is not None:
                raise SystemExit(f"Der MOTIS-Server ist abgebrochen; siehe {ordner / 'server.log'}")
            try:
                rk.server_pruefen(adresse)
                break
            except SystemExit:
                time.sleep(0.5)
        else:
            raise SystemExit(f"Der MOTIS-Server antwortet nicht; siehe {ordner / 'server.log'}")
        t1 = time.time()
        zeiten = rk.abfahrten(rk.zeitpunkt(datum, von), rk.zeitpunkt(datum, bis), schritt)
        zellen = rk.reisezeiten_berechnen(punkte, zeiten, server=adresse, strassen=strassen,
                                          parallel=min(8, os.cpu_count() or 4))
        t_anfragen = time.time() - t1
    finally:
        server.terminate()
        server.wait(timeout=30)
        if not daten_behalten:
            shutil.rmtree(ordner / "data", ignore_errors=True)
    zellen["einwohner"] = einwohner(punkte, raster_m)
    dauer = {"import": round(t_import), "anfragen": round(t_anfragen)}
    ergebnis.write_text(json.dumps({"stempel": stempel, "dauer_s": dauer, "zellen": zellen}, ensure_ascii=False),
                        encoding="utf-8")
    print(f"{name}: {len(punkte)} Zellen, Import {t_import:.0f} s, Anfragen {t_anfragen:.0f} s")
    return zellen
