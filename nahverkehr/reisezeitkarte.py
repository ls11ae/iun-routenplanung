"""Reisezeitkarte: Wie lange braucht man morgens aus ganz Dortmund zum Campus Nord?

Legt ein Raster (500 m) über das Stadtgebiet und fragt für jeden Rasterpunkt den lokalen
MOTIS-Server: Wie lange dauert der Weg zum Ziel mit dem öffentlichen Verkehr (ÖPNV), mit
dem Auto, mit dem Fahrrad und zu Fuß? Das Ergebnis steht in webdemo/daten/reisezeiten.json
und wird von der Webdemo und für die Abbildung gelesen.

Vorher den Server starten (nahverkehr/starten.bat bzw. starten.sh), dann im
Wurzelverzeichnis des Repositorys:

    python nahverkehr/reisezeitkarte.py
    python nahverkehr/reisezeitkarte.py --von 21:00 --bis 22:00 --ausgabe abends.json

Was gemessen wird:

- oepnv_min        Median der Reisezeit über die Abfahrten zwischen --von und --bis im Abstand
                   von --schritt Minuten (Voreinstellung 7:00, 7:05, …, 8:00 Uhr). Für jede
                   Abfahrt zählt die Zeit vom Verlassen des Hauses bis zur frühesten Ankunft,
                   die Wartezeit auf die erste Abfahrt also mit. Tür zu Tür mit Fußwegen. Ist
                   man zu Fuß früher da, gilt für diese Abfahrt die Gehzeit.
- oepnv_beste_min, oepnv_schlechteste_min  kürzeste und längste dieser Reisezeiten.
- umstiege         Umstiege der Verbindung, die den Median liefert; -1 = zu Fuß schneller.
- zum_halt_min     Fußweg dieser Verbindung bis zur ersten Haltestelle.
- oepnv_dauer_min  Kürzeste Verbindung mit Abfahrt im Zeitraum, ohne Wartezeit.
- halt_m           Luftlinie zur nächsten Haltestelle, an der am Tag zwischen 7 und 9 Uhr
                   ein Bus oder eine Bahn abfährt.
- auto_min         Reine Fahrzeit nach OpenStreetMap: ohne Stau, ohne Parkplatzsuche.
- rad_min, fuss_min  Fahrrad und zu Fuß nach OpenStreetMap.

Alle Zeiten in Minuten; `None` (in der Datei `null`) heißt: kein Weg in der Nähe des
Rasterpunkts oder keine Verbindung gefunden.

Die Funktionen lassen sich auch einzeln verwenden, etwa in einem Notebook:

    import reisezeitkarte as rk
    zeiten = rk.abfahrten(rk.zeitpunkt("2026-11-24", "07:00"), rk.zeitpunkt("2026-11-24", "08:00"))
    rk.oepnv_ueber_abfahrten((51.4862, 7.5050), rk.ZIEL, zeiten)       # Hörde -> Campus
    rk.strassenzeiten([(51.4862, 7.5050)], rk.ZIEL_AUTO, "CAR")
"""

import argparse
import json
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import requests
import shapely
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motis_einrichten import VERSION, fahrplan_zeitraum  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent
GRENZE = WURZEL / "daten" / "dortmund-grenze.geojson"
AUSGABE = WURZEL / "webdemo" / "daten" / "reisezeiten.json"

# 127.0.0.1 statt localhost: Unter Windows probiert Python bei „localhost“ zuerst IPv6,
# und jede neue Verbindung dauert dann zwei Sekunden länger.
SERVER = "http://127.0.0.1:8080"
OHNE_PROXY = {"http": None, "https": None}   # der eigene Rechner wird ohne Proxy angesprochen

ZIEL_NAME = "TU Dortmund, Campus Nord"
ZIEL = (51.4925, 7.4128)          # (Breite, Länge)
# Der Campus ist autofrei: Im Umkreis des Ziels findet MOTIS keine Straße, die mit dem
# Auto erreichbar ist. Die Autofahrt endet deshalb an der nächsten öffentlichen Straße.
ZIEL_AUTO_NAME = "Emil-Figge-Straße am Campus Nord (rund 180 m vom Ziel)"
ZIEL_AUTO = (51.4941, 7.4122)

UTM = 25832                       # ETRS89 / UTM Zone 32N: Koordinaten in Metern
MAX_WEGABSTAND_M = 250            # so weit darf der nächste Weg vom Punkt entfernt sein

# Darstellung (Webdemo und Abbildung lesen diese Werte aus der Ergebnisdatei)
HALT_MAX_M = 1000                 # weiter weg: „keine Haltestelle in Gehweite“
CAMPUS_FUSS_MAX_MIN = 15          # höchstens so lange zu Fuß: „Campus in Gehweite“
ZUSCHLAG_MIN = 5                  # Minuten für Parkplatzsuche und Fußweg zum Auto (Standard)
VERHAELTNIS_GRENZEN = [2.5, 3, 3.5, 4]   # Klassen des Verhältnisses ÖPNV zu Auto; ab 4 zusammengefasst
MAX_REISEZEIT_MIN = 180           # länger gilt als „keine Verbindung“ (etwa erst am Mittag)

sitzung = requests.Session()      # hält die Verbindung zum Server offen


# ---------------------------------------------------------------- Zeit und Raster

def zeitpunkt(datum: str, uhrzeit: str, zone: str = "Europe/Berlin") -> datetime:
    """Datum (JJJJ-MM-TT) und Uhrzeit (HH:MM) in Ortszeit als datetime mit Zeitzone."""
    return datetime.fromisoformat(f"{datum}T{uhrzeit}").replace(tzinfo=ZoneInfo(zone))


def als_utc(zeit: datetime) -> str:
    """MOTIS erwartet Zeiten in Weltzeit (UTC), zum Beispiel 2026-11-24T06:30:00Z."""
    return zeit.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def abfahrten(von: datetime, bis: datetime, schritt_min: int = 5) -> list:
    """Abfahrtszeiten von `von` bis einschließlich `bis` im Abstand von `schritt_min` Minuten."""
    zeiten, t = [], von
    while t <= bis:
        zeiten.append(t)
        t += timedelta(minutes=schritt_min)
    return zeiten


def grenze_laden(datei: Path = GRENZE):
    """Stadtgrenze als shapely-Geometrie (Länge/Breite, EPSG:4326)."""
    geojson = json.loads(Path(datei).read_text(encoding="utf-8"))
    return shapely.geometry.shape(geojson.get("geometry", geojson))


def umrechnen(geometrie, von: int, nach: int):
    """Rechnet die Koordinaten einer Geometrie zwischen zwei Bezugssystemen (EPSG) um."""
    t = Transformer.from_crs(von, nach, always_xy=True)
    return shapely.transform(geometrie, lambda p: np.column_stack(t.transform(p[:, 0], p[:, 1])))


def raster_erzeugen(grenze, raster_m: int = 500):
    """Mittelpunkte eines Gitters mit Maschenweite `raster_m`, die im Gebiet liegen.

    Gerechnet wird in UTM (Meter). Die Gitterlinien liegen auf Vielfachen von `raster_m`,
    das Raster ist also bei jedem Lauf dasselbe. Liefert eine Liste von (Breite, Länge),
    zeilenweise von Norden nach Süden.
    """
    flaeche = umrechnen(grenze, 4326, UTM)
    x0, y0, x1, y1 = flaeche.bounds
    xs = np.arange(np.floor(x0 / raster_m) * raster_m + raster_m / 2, x1, raster_m)
    ys = np.arange(np.floor(y0 / raster_m) * raster_m + raster_m / 2, y1, raster_m)[::-1]
    x, y = (a.ravel() for a in np.meshgrid(xs, ys))
    innen = shapely.contains_xy(flaeche, x, y)
    lon, lat = Transformer.from_crs(UTM, 4326, always_xy=True).transform(x[innen], y[innen])
    return [(round(float(b), 5), round(float(l), 5)) for b, l in zip(lat, lon)]


def zelle_in_grad(punkt, raster_m: int = 500):
    """Breite und Höhe einer Rasterzelle in Grad [dlon, dlat] an der Stelle `punkt`."""
    hin = Transformer.from_crs(4326, UTM, always_xy=True)
    her = Transformer.from_crs(UTM, 4326, always_xy=True)
    x, y = hin.transform(punkt[1], punkt[0])
    lon_w, _ = her.transform(x - raster_m / 2, y)
    lon_o, _ = her.transform(x + raster_m / 2, y)
    _, lat_s = her.transform(x, y - raster_m / 2)
    _, lat_n = her.transform(x, y + raster_m / 2)
    return [round(lon_o - lon_w, 6), round(lat_n - lat_s, 6)]


def haltestellen_abstand(punkte, tag: date, von: str = "07:00", bis: str = "09:00"):
    """Luftlinie in Metern von jedem Punkt zur nächsten Haltestelle, an der am `tag` zwischen
    `von` und `bis` Uhr ein Fahrzeug abfährt (aus dem Fahrplan in daten/dortmund-gtfs.zip)."""
    import gtfs_hilfen as h
    g = h.lade_gtfs()
    c = h.verbindungen(g, tag, von, bis)
    halte = set(c.ab_halt[c.einstieg_ok])
    s = g["stops"][g["stops"].stop_id.isin(halte)]
    lat, lon = s.stop_lat.to_numpy(), s.stop_lon.to_numpy()
    return [int(round(float(h.entfernung_m(b, l, lat, lon).min()))) for b, l in punkte]


# ---------------------------------------------------------------- Anfragen an MOTIS

def motis(pfad: str, parameter: dict, server: str = SERVER):
    """Schickt eine Anfrage an den MOTIS-Server und liefert die Antwort (JSON) als Python-Objekt."""
    antwort = sitzung.get(server + pfad, params=parameter, proxies=OHNE_PROXY, timeout=120)
    antwort.raise_for_status()
    return antwort.json()


def server_pruefen(server: str = SERVER) -> str:
    """Prüft, ob der Server läuft, und liefert seine Bezeichnung, etwa „MOTIS 2.11.4“."""
    try:
        antwort = sitzung.get(server + "/api/v1/health", proxies=OHNE_PROXY, timeout=10)
        antwort.raise_for_status()
    except requests.RequestException:
        raise SystemExit(f"Der MOTIS-Server antwortet nicht ({server}). Bitte zuerst "
                         "nahverkehr/starten.bat bzw. starten.sh ausführen.") from None
    kennung = antwort.headers.get("Server", "")          # zum Beispiel „MOTIS v2.11.4-dirty“
    if kennung.startswith("MOTIS v"):
        return "MOTIS " + kennung[len("MOTIS v"):].split("-")[0]
    return f"MOTIS {VERSION}"


def strassenzeiten(punkte, ziel, modus: str, server: str = SERVER, hoechstens_s: int = 21600,
                   stueck: int = 100):
    """Reisezeit in Minuten von jedem Punkt zum Ziel auf Straßen und Wegen.

    modus: "WALK", "BIKE" oder "CAR". Nutzt /api/v1/one-to-many (viele Starts, ein Ziel)
    in Stücken von `stueck` Punkten; der Server nimmt höchstens 128 je Anfrage an.
    `hoechstens_s` ist die längste zugelassene Reisezeit (Obergrenze des Servers: 6 Stunden).
    Punkte ohne Verbindung erhalten None. Das passiert auch, wenn der nächstgelegene Weg
    (höchstens 250 m entfernt) nicht mit dem übrigen Netz verbunden ist, etwa auf einem
    Werksgelände oder – für das Auto – in einer Fußgängerzone.
    """
    minuten = []
    for i in range(0, len(punkte), stueck):
        antwort = motis("/api/v1/one-to-many", {
            "one": f"{ziel[0]};{ziel[1]}",
            "many": ",".join(f"{lat};{lon}" for lat, lon in punkte[i:i + stueck]),
            "mode": modus,
            "max": hoechstens_s,
            "maxMatchingDistance": MAX_WEGABSTAND_M,
            "arriveBy": "true",        # true = von den vielen Punkten zu dem einen
        }, server)
        minuten += [round(e["duration"] / 60, 1) if "duration" in e else None for e in antwort]
    return minuten


def verbindungen(start, ziel, abfahrt: datetime, server: str = SERVER, max_fussweg_s: int = 3600,
                 **weitere):
    """ÖPNV-Verbindungen von `start` nach `ziel` (jeweils (Breite, Länge)) ab `abfahrt`.

    Liefert die Liste `itineraries` aus /api/v6/plan. Direkte Fußwege werden hier nicht
    mitberechnet (directModes leer), denn sonst lässt MOTIS langsamere ÖPNV-Verbindungen
    weg.

    `max_fussweg_s` begrenzt den Fußweg zur ersten und von der letzten Haltestelle
    (Voreinstellung von MOTIS: 900 s; Obergrenze des Servers: 3600 s). Vorsicht: MOTIS
    vergleicht die Grenze nicht mit der Gehzeit, die es in der Antwort nennt, sondern mit
    internen Wegkosten, in denen Zuschläge stecken. Ein Fußweg von 11 Minuten kann so schon
    an einer Grenze von 20 Minuten scheitern, und die Haltestelle fehlt dann ohne Hinweis.
    Deshalb steht hier die Obergrenze; welche Verbindung gewinnt, entscheidet die Ankunft.
    """
    parameter = {
        "fromPlace": f"{start[0]},{start[1]}",
        "toPlace": f"{ziel[0]},{ziel[1]}",
        "time": als_utc(abfahrt),
        "directModes": "",
        "maxPreTransitTime": max_fussweg_s,
        "maxPostTransitTime": max_fussweg_s,
        "maxMatchingDistance": MAX_WEGABSTAND_M,
        "detailedLegs": "false",       # ohne Linienverläufe: kleinere Antworten
    }
    parameter.update(weitere)
    return motis("/api/v6/plan", parameter, server)["itineraries"]


def _zeit(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _zum_halt(verbindung) -> float:
    erster = verbindung["legs"][0]
    return round(erster["duration"] / 60, 1) if erster["mode"] == "WALK" else 0.0


def _frueheste(liste):
    """Die Verbindung mit der frühesten Ankunft (bei Gleichstand die mit weniger Umstiegen)."""
    return min(liste, key=lambda v: (_zeit(v["endTime"]), v["transfers"]))


KEINE_VERBINDUNG = {"min": None, "umstiege": None, "dauer_min": None, "zum_halt_min": None}


def oepnv_zeiten(start, ziel, abfahrt: datetime, server: str = SERVER, max_fussweg_s: int = 3600,
                 fenster_s: int = 3600) -> dict:
    """ÖPNV-Reisezeit für jemanden, der zu genau einer Zeit `abfahrt` das Haus verlässt.

    Zwei Anfragen:
    1. timetableView=false: MOTIS sucht die früheste Ankunft; Warten auf die erste Abfahrt
       ist Reisezeit.
    2. Fahrplanansicht mit searchWindow: alle sinnvollen Verbindungen, die im Zeitfenster
       abfahren. Daraus die kürzeste reine Dauer (wer passend losgeht, wartet nicht).

    Ergebnis (Minuten; alles None, wenn es keine Verbindung gibt):
    min           von `abfahrt` bis zur frühesten Ankunft
    umstiege      Umstiege dieser Verbindung
    zum_halt_min  ihr Fußweg bis zur ersten Haltestelle
    dauer_min     kürzeste reine Dauer unter allen gefundenen Verbindungen
    """
    fruehe = verbindungen(start, ziel, abfahrt, server, max_fussweg_s, timetableView="false")
    if not fruehe:
        return dict(KEINE_VERBINDUNG)
    beste = _frueheste(fruehe)
    # Findet MOTIS im Fenster nichts, sucht es von sich aus weiter – auch vor der Abfahrt
    # oder Stunden später. Deshalb hier auf das Fenster beschränken.
    fenster = [v for v in verbindungen(start, ziel, abfahrt, server, max_fussweg_s,
                                       searchWindow=fenster_s, numItineraries=1)
               if abfahrt <= _zeit(v["startTime"]) <= abfahrt + timedelta(seconds=fenster_s)]
    return {"min": round((_zeit(beste["endTime"]) - abfahrt).total_seconds() / 60, 1),
            "umstiege": beste["transfers"],
            "zum_halt_min": _zum_halt(beste),
            "dauer_min": round(min(v["duration"] for v in fruehe + fenster) / 60, 1)}


def oepnv_ueber_abfahrten(start, ziel, zeiten, fuss_min=None, server: str = SERVER,
                          max_fussweg_s: int = 3600, puffer_s: int = 5400,
                          max_reisezeit_min: float = MAX_REISEZEIT_MIN) -> dict:
    """ÖPNV-Reisezeit für mehrere Abfahrtszeiten `zeiten` und ihr Median.

    Eine einzige Anfrage in der Fahrplanansicht liefert alle sinnvollen Verbindungen, die
    zwischen der ersten Abfahrtszeit und der letzten plus `puffer_s` abfahren. Für jede
    Abfahrtszeit t gilt dann: Reisezeit = früheste Ankunft unter den Verbindungen, die
    frühestens um t starten, minus t (die Wartezeit zählt mit). Fehlt eine solche
    Verbindung, wird für t eigens nachgefragt. Reisezeiten über `max_reisezeit_min` gelten
    als keine Verbindung (MOTIS findet sonst etwa einen Bus am Mittag oder am nächsten Tag).
    Ist man zu Fuß (`fuss_min`) früher da, gilt für diese Abfahrt die Gehzeit.

    Ergebnis (Minuten; None, wenn es für weniger als die Hälfte der Abfahrten einen Wert gibt):
    min                 Median über die Abfahrten
    beste_min, schlechteste_min   kürzeste und längste Reisezeit
    je_abfahrt          Liste der Reisezeiten in der Reihenfolge von `zeiten`
    umstiege, zum_halt_min        der Verbindung, die den Median liefert (-1 / None: zu Fuß)
    dauer_min           kürzeste reine Dauer einer Verbindung mit Abfahrt im Zeitraum
    """
    von, bis = zeiten[0], zeiten[-1]
    fenster_s = int((bis - von).total_seconds()) + puffer_s
    alle = verbindungen(start, ziel, von, server, max_fussweg_s, searchWindow=fenster_s,
                        numItineraries=1)
    alle = [(_zeit(v["startTime"]), v) for v in alle]
    je_abfahrt = []                       # (Minuten, Verbindung oder None für zu Fuß)
    for t in zeiten:
        moeglich = [v for s, v in alle if s >= t]
        if not moeglich:                  # nichts im Fenster: früheste Ankunft eigens erfragen
            moeglich = verbindungen(start, ziel, t, server, max_fussweg_s, timetableView="false")
        oepnv = None
        if moeglich:
            v = _frueheste(moeglich)
            oepnv = round((_zeit(v["endTime"]) - t).total_seconds() / 60, 1)
            if oepnv > max_reisezeit_min:
                oepnv = None
        if fuss_min is not None and (oepnv is None or fuss_min <= oepnv):
            je_abfahrt.append((fuss_min, None))
        elif oepnv is not None:
            je_abfahrt.append((oepnv, v))
        else:
            je_abfahrt.append((None, None))
    werte = [m for m, _ in je_abfahrt if m is not None]
    if 2 * len(werte) < len(zeiten):
        return {"min": None, "beste_min": None, "schlechteste_min": None, "je_abfahrt": [m for m, _ in je_abfahrt],
                "umstiege": None, "zum_halt_min": None, "dauer_min": None}
    mitte = sorted((m, i) for i, (m, _) in enumerate(je_abfahrt) if m is not None)[(len(werte) - 1) // 2]
    vertreter = je_abfahrt[mitte[1]][1]
    dauern = [v["duration"] / 60 for s, v in alle if von <= s <= bis]
    if fuss_min is not None:
        dauern.append(fuss_min)
    return {"min": round(statistics.median(werte), 1),
            "beste_min": min(werte), "schlechteste_min": max(werte),
            "je_abfahrt": [m for m, _ in je_abfahrt],
            "umstiege": -1 if vertreter is None else vertreter["transfers"],
            "zum_halt_min": None if vertreter is None else _zum_halt(vertreter),
            "dauer_min": round(min(dauern), 1) if dauern else None}


# ---------------------------------------------------------------- Raster berechnen

def reisezeiten_berechnen(punkte, zeiten, ziel=ZIEL, ziel_auto=ZIEL_AUTO, server: str = SERVER,
                          max_fussweg_s: int = 3600, parallel: int = 4) -> dict:
    """Berechnet für alle Punkte die Reisezeiten zum Ziel. Liefert Listen gleicher Länge."""
    t0 = time.time()
    fuss = strassenzeiten(punkte, ziel, "WALK", server)
    rad = strassenzeiten(punkte, ziel, "BIKE", server)
    auto = strassenzeiten(punkte, ziel_auto, "CAR", server)
    print(f"Zu Fuß, Rad, Auto: {len(punkte)} Punkte in {time.time() - t0:.1f} s")

    fehler = 0

    def eine_zelle(i):
        try:
            return oepnv_ueber_abfahrten(punkte[i], ziel, zeiten, fuss[i], server, max_fussweg_s)
        except (requests.RequestException, ValueError, KeyError) as e:
            return e

    t1 = time.time()
    oepnv = []
    with ThreadPoolExecutor(max_workers=parallel) as helfer:   # mehrere Anfragen gleichzeitig
        for i, ergebnis in enumerate(helfer.map(eine_zelle, range(len(punkte))), start=1):
            if isinstance(ergebnis, Exception):
                fehler += 1
                print(f"  Fehler bei Punkt {punkte[i - 1]}: {ergebnis}")
                ergebnis = {"min": None, "beste_min": None, "schlechteste_min": None,
                            "umstiege": None, "zum_halt_min": None, "dauer_min": None}
            oepnv.append(ergebnis)
            if i % 100 == 0 or i == len(punkte):
                print(f"  ÖPNV: {i:5d} von {len(punkte)} Punkten, {time.time() - t1:5.0f} s", flush=True)
    print(f"ÖPNV: {len(punkte)} Punkte in {time.time() - t1:.0f} s, Fehler: {fehler}")

    spalte = lambda name: [o[name] for o in oepnv]
    return {"lat": [p[0] for p in punkte], "lon": [p[1] for p in punkte],
            "oepnv_min": spalte("min"), "oepnv_beste_min": spalte("beste_min"),
            "oepnv_schlechteste_min": spalte("schlechteste_min"),
            "oepnv_dauer_min": spalte("dauer_min"), "umstiege": spalte("umstiege"),
            "zum_halt_min": spalte("zum_halt_min"),
            "auto_min": auto, "rad_min": rad, "fuss_min": fuss}


def _gerundet(koordinaten, stellen: int = 5):
    if isinstance(koordinaten[0], (int, float)):
        return [round(k, stellen) for k in koordinaten]
    return [_gerundet(k, stellen) for k in koordinaten]


def kategorie(zellen: dict, i: int, zuschlag_min: float = ZUSCHLAG_MIN, halt_max_m: int = HALT_MAX_M,
              campus_fuss_max_min: float = CAMPUS_FUSS_MAX_MIN, grenzen=VERHAELTNIS_GRENZEN):
    """Kategorie einer Zelle für die Karte „ÖPNV gegen Auto“: "campus" (zu Fuß in Gehweite),
    "kein_halt" (keine Haltestelle in Gehweite), "kein_wert" oder die Nummer der Klasse des
    Verhältnisses ÖPNV / (Auto + Zuschlag), 0 = günstigste Klasse."""
    fuss = zellen["fuss_min"][i]
    if fuss is not None and fuss <= campus_fuss_max_min:
        return "campus"
    if zellen.get("halt_m") and zellen["halt_m"][i] is not None and zellen["halt_m"][i] > halt_max_m:
        return "kein_halt"
    o, a = zellen["oepnv_min"][i], zellen["auto_min"][i]
    if o is None or a is None:
        return "kein_wert"
    return sum(o / (a + zuschlag_min) > g for g in grenzen)


def zusammenfassung(zellen: dict, zuschlag_min: float = ZUSCHLAG_MIN):
    """Gibt für jede Spalte aus, wie viele Werte fehlen und wie die Zeiten verteilt sind,
    und zählt die Zellen je Kategorie der Karte."""
    n = len(zellen["lat"])
    for spalte in ("oepnv_min", "oepnv_beste_min", "oepnv_schlechteste_min", "oepnv_dauer_min",
                   "zum_halt_min", "halt_m", "auto_min", "rad_min", "fuss_min"):
        werte = sorted(w for w in zellen.get(spalte, []) if w is not None)
        if not werte:
            continue
        q = statistics.quantiles(werte, n=4)
        print(f"  {spalte:22s} ohne Wert {n - len(werte):4d}   min {werte[0]:6.1f}  25 % {q[0]:6.1f}  "
              f"Median {q[1]:6.1f}  75 % {q[2]:6.1f}  max {werte[-1]:6.1f}")
    kat = [kategorie(zellen, i, zuschlag_min) for i in range(n)]
    print("  Kategorien:", {k: kat.count(k) for k in sorted(set(kat), key=str)})
    for z in (0, zuschlag_min):
        v = [zellen["oepnv_min"][i] / (zellen["auto_min"][i] + z) for i in range(n)
             if isinstance(kategorie(zellen, i, z), int)]
        if v:
            print(f"  ÖPNV / (Auto + {z} min): Median {statistics.median(v):.2f} über {len(v)} Zellen")


def main():
    parser = argparse.ArgumentParser(description="Reisezeiten von einem Raster zum Ziel mit MOTIS berechnen")
    parser.add_argument("--datum", default="2026-11-24", help="Tag im Fahrplan (JJJJ-MM-TT)")
    parser.add_argument("--von", default="07:00", help="erste Abfahrt (Ortszeit)")
    parser.add_argument("--bis", default="08:00", help="letzte Abfahrt (Ortszeit)")
    parser.add_argument("--schritt", type=int, default=5, help="Abstand der Abfahrten in Minuten")
    parser.add_argument("--raster", type=int, default=500, help="Maschenweite in Metern")
    parser.add_argument("--max-fussweg", type=int, default=60,
                        help="Grenze für den Fußweg zur ersten und von der letzten Haltestelle in "
                             "Minuten (Wegkosten von MOTIS, höchstens 60)")
    parser.add_argument("--parallel", type=int, default=4, help="gleichzeitige Anfragen")
    parser.add_argument("--stichprobe", type=int, help="nur so viele zufällige Rasterpunkte (zum Ausprobieren)")
    parser.add_argument("--server", default=SERVER, help="Adresse des MOTIS-Servers")
    parser.add_argument("--grenze", type=Path, default=GRENZE, help="GeoJSON mit der Gebietsgrenze")
    parser.add_argument("--ausgabe", type=Path, default=AUSGABE, help="Zieldatei (JSON)")
    args = parser.parse_args()

    t0 = time.time()
    werkzeug = server_pruefen(args.server)
    zeiten = abfahrten(zeitpunkt(args.datum, args.von), zeitpunkt(args.datum, args.bis), args.schritt)
    von, bis = fahrplan_zeitraum()
    if not von <= zeiten[0].date() <= bis:
        print(f"Achtung: Der {zeiten[0]:%d.%m.%Y} liegt außerhalb des Fahrplans "
              f"({von:%d.%m.%Y} bis {bis:%d.%m.%Y}); es wird keine ÖPNV-Verbindung geben.")

    grenze = grenze_laden(args.grenze)
    punkte = raster_erzeugen(grenze, args.raster)
    if args.stichprobe:
        punkte = sorted(random.Random(1).sample(punkte, args.stichprobe), key=lambda p: (-p[0], p[1]))
    print(f"{werkzeug}, {len(zeiten)} Abfahrten {zeiten[0]:%d.%m.%Y %H:%M} bis {zeiten[-1]:%H:%M}, "
          f"{len(punkte)} Rasterpunkte")

    zellen = reisezeiten_berechnen(punkte, zeiten, server=args.server,
                                   max_fussweg_s=args.max_fussweg * 60, parallel=args.parallel)
    t1 = time.time()
    zellen["halt_m"] = haltestellen_abstand(punkte, zeiten[0].date())
    print(f"Abstand zur nächsten Haltestelle: {time.time() - t1:.0f} s")
    daten = {
        "erzeugt": date.today().isoformat(),
        "ziel": {"name": ZIEL_NAME, "lat": ZIEL[0], "lon": ZIEL[1]},
        "ziel_auto": {"name": ZIEL_AUTO_NAME, "lat": ZIEL_AUTO[0], "lon": ZIEL_AUTO[1]},
        "abfahrten": {"von": zeiten[0].isoformat(), "bis": zeiten[-1].isoformat(),
                      "schritt_min": args.schritt, "anzahl": len(zeiten)},
        "raster_m": args.raster,
        "zelle_grad": zelle_in_grad(ZIEL, args.raster),
        "fahrplan": {"gueltig_von": von.isoformat(), "gueltig_bis": bis.isoformat()},
        "werkzeug": werkzeug,
        "darstellung": {"zuschlag_min": ZUSCHLAG_MIN, "halt_max_m": HALT_MAX_M,
                        "campus_fuss_max_min": CAMPUS_FUSS_MAX_MIN,
                        "verhaeltnis_grenzen": VERHAELTNIS_GRENZEN},
        "annahmen": [
            f"Bus und Bahn: Median der Reisezeit über {len(zeiten)} Abfahrten von {zeiten[0]:%H:%M} "
            f"bis {zeiten[-1]:%H:%M} Uhr im Abstand von {args.schritt} Minuten. Je Abfahrt zählt die "
            "Zeit vom Verlassen des Hauses bis zur frühesten Ankunft, die Wartezeit also mit.",
            "Tür zu Tür mit Fußwegen; welche Haltestelle man nimmt, entscheidet die früheste "
            f"Ankunft (technische Grenze für den Fußweg {args.max_fussweg} Minuten). Ist man zu "
            f"Fuß früher da, gilt die Gehzeit. Reisezeiten über {MAX_REISEZEIT_MIN // 60} Stunden "
            "gelten als keine Verbindung.",
            f"Keine Haltestelle in Gehweite: Im Umkreis von {HALT_MAX_M} m (Luftlinie) fährt "
            "zwischen 7 und 9 Uhr kein Bus und keine Bahn ab.",
            f"Campus in Gehweite: zu Fuß in höchstens {CAMPUS_FUSS_MAX_MIN} Minuten am Ziel.",
            "Auto: Fahrzeit nach OpenStreetMap ohne Stau; die Karte rechnet standardmäßig "
            f"{ZUSCHLAG_MIN} Minuten für Parkplatzsuche und Fußweg dazu. Die Fahrt endet an der "
            f"Stelle „{ZIEL_AUTO_NAME}“, weil der Campus autofrei ist.",
            "Fahrplan nach Plan: ohne Verspätungen und Ausfälle. Umsteigen mit der Voreinstellung "
            "von MOTIS, in der Regel 2 Minuten.",
            "Fahrrad und zu Fuß: Zeiten nach OpenStreetMap mit den Standardgeschwindigkeiten "
            "von MOTIS, ohne Steigungen.",
            f"Start ist der Mittelpunkt der Rasterzelle ({args.raster} m). Liegt im Umkreis von "
            f"{MAX_WEGABSTAND_M} m kein passender Weg oder gibt es keine Verbindung, bleibt der "
            "Wert leer.",
        ],
        "grenze": {"type": grenze.geom_type,
                   "coordinates": _gerundet(shapely.geometry.mapping(grenze)["coordinates"])},
        "zellen": zellen,
    }
    args.ausgabe.parent.mkdir(parents=True, exist_ok=True)
    with open(args.ausgabe, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(daten, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"{args.ausgabe} geschrieben ({args.ausgabe.stat().st_size / 1000:.0f} kB), "
          f"Gesamtdauer {time.time() - t0:.0f} s")
    zusammenfassung(zellen)


if __name__ == "__main__":
    main()
