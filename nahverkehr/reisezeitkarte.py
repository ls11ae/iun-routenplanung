"""Reisezeitkarte: Wie lange braucht man morgens aus ganz Dortmund zum Campus Nord?

Legt ein Raster (500 m) über das Stadtgebiet und fragt für jeden Rasterpunkt den lokalen
MOTIS-Server: Wie lange dauert der Weg zum Ziel mit dem öffentlichen Verkehr (ÖPNV), mit
dem Auto, mit dem Fahrrad und zu Fuß? Das Ergebnis steht in webdemo/daten/reisezeiten.json
und wird von der Webdemo und für die Abbildungen gelesen.

Vorher den Server starten (nahverkehr/starten.bat bzw. starten.sh), dann im
Wurzelverzeichnis des Repositorys:

    python nahverkehr/reisezeitkarte.py
    python nahverkehr/reisezeitkarte.py --uhrzeit 22:00 --ausgabe abends.json

Was gemessen wird:

- oepnv_min        Man verlässt zur angegebenen Uhrzeit das Haus. Gezählt wird bis zur
                   frühesten Ankunft am Ziel, die Wartezeit auf die erste Abfahrt zählt mit.
                   Tür zu Tür mit Fußwegen. Ist man zu Fuß früher da, gilt die Gehzeit.
- umstiege         Umstiege der Verbindung mit der frühesten Ankunft; -1 = zu Fuß schneller.
- zum_halt_min     Fußweg dieser Verbindung bis zur ersten Haltestelle.
- oepnv_dauer_min  Kürzeste Verbindung mit Abfahrt in der folgenden Stunde, ohne Wartezeit.
- auto_min         Reine Fahrzeit nach OpenStreetMap: ohne Stau, ohne Parkplatzsuche.
- rad_min, fuss_min  Fahrrad und zu Fuß nach OpenStreetMap.

Alle Zeiten in Minuten; `None` (in der Datei `null`) heißt: kein Weg in der Nähe des
Rasterpunkts oder keine Verbindung gefunden.

Die Funktionen lassen sich auch einzeln verwenden, etwa in einem Notebook:

    import reisezeitkarte as rk
    abfahrt = rk.zeitpunkt("2026-11-24", "07:30")
    rk.oepnv_zeiten((51.4862, 7.5050), rk.ZIEL, abfahrt)       # Hörde -> Campus
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
sitzung = requests.Session()      # hält die Verbindung zum Server offen


# ---------------------------------------------------------------- Zeit und Raster

def zeitpunkt(datum: str, uhrzeit: str, zone: str = "Europe/Berlin") -> datetime:
    """Datum (JJJJ-MM-TT) und Uhrzeit (HH:MM) in Ortszeit als datetime mit Zeitzone."""
    return datetime.fromisoformat(f"{datum}T{uhrzeit}").replace(tzinfo=ZoneInfo(zone))


def als_utc(zeit: datetime) -> str:
    """MOTIS erwartet Zeiten in Weltzeit (UTC), zum Beispiel 2026-11-24T06:30:00Z."""
    return zeit.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


KEINE_VERBINDUNG = {"min": None, "umstiege": None, "dauer_min": None, "zum_halt_min": None}


def oepnv_zeiten(start, ziel, abfahrt: datetime, server: str = SERVER, max_fussweg_s: int = 3600,
                 fenster_s: int = 3600) -> dict:
    """ÖPNV-Reisezeit für jemanden, der zur Zeit `abfahrt` das Haus verlässt.

    Zwei Anfragen:
    1. timetableView=false: MOTIS sucht die früheste Ankunft; Warten auf die erste Abfahrt
       ist Reisezeit. Geliefert werden die Verbindungen, die bei Ankunft oder Zahl der
       Umstiege unschlagbar sind – wir nehmen die mit der frühesten Ankunft.
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
    beste = min(fruehe, key=lambda v: (_zeit(v["endTime"]), v["transfers"]))
    erster = beste["legs"][0]
    # Findet MOTIS im Fenster nichts, sucht es von sich aus weiter – auch vor der Abfahrt
    # oder Stunden später. Deshalb hier auf das Fenster beschränken.
    fenster = [v for v in verbindungen(start, ziel, abfahrt, server, max_fussweg_s,
                                       searchWindow=fenster_s, numItineraries=1)
               if abfahrt <= _zeit(v["startTime"]) <= abfahrt + timedelta(seconds=fenster_s)]
    return {"min": round((_zeit(beste["endTime"]) - abfahrt).total_seconds() / 60, 1),
            "umstiege": beste["transfers"],
            "zum_halt_min": round(erster["duration"] / 60, 1) if erster["mode"] == "WALK" else 0.0,
            "dauer_min": round(min(v["duration"] for v in fruehe + fenster) / 60, 1)}


# ---------------------------------------------------------------- Raster berechnen

def reisezeiten_berechnen(punkte, ziel=ZIEL, ziel_auto=ZIEL_AUTO, abfahrt: datetime = None,
                          server: str = SERVER, max_fussweg_s: int = 3600, fenster_s: int = 3600,
                          parallel: int = 4) -> dict:
    """Berechnet für alle Punkte die Reisezeiten zum Ziel. Liefert Listen gleicher Länge."""
    t0 = time.time()
    fuss = strassenzeiten(punkte, ziel, "WALK", server)
    rad = strassenzeiten(punkte, ziel, "BIKE", server)
    auto = strassenzeiten(punkte, ziel_auto, "CAR", server)
    print(f"Zu Fuß, Rad, Auto: {len(punkte)} Punkte in {time.time() - t0:.1f} s")

    fehler = 0

    def eine_zelle(punkt):
        try:
            return oepnv_zeiten(punkt, ziel, abfahrt, server, max_fussweg_s, fenster_s)
        except (requests.RequestException, ValueError, KeyError) as e:
            return e

    t1 = time.time()
    oepnv = []
    with ThreadPoolExecutor(max_workers=parallel) as helfer:   # mehrere Anfragen gleichzeitig
        for i, ergebnis in enumerate(helfer.map(eine_zelle, punkte), start=1):
            if isinstance(ergebnis, Exception):
                fehler += 1
                print(f"  Fehler bei Punkt {punkte[i - 1]}: {ergebnis}")
                ergebnis = dict(KEINE_VERBINDUNG)
            oepnv.append(ergebnis)
            if i % 100 == 0 or i == len(punkte):
                print(f"  ÖPNV: {i:5d} von {len(punkte)} Punkten, {time.time() - t1:5.0f} s", flush=True)
    dauer = time.time() - t1
    print(f"ÖPNV: {len(punkte)} Punkte in {dauer:.0f} s "
          f"({2 * len(punkte) / dauer:.0f} Anfragen je Sekunde), Fehler: {fehler}")

    # Zu Fuß früher da als mit jeder ÖPNV-Verbindung (oder gar keine gefunden): Gehzeit gilt.
    oepnv_min, oepnv_dauer, umstiege, zum_halt = [], [], [], []
    for o, f in zip(oepnv, fuss):
        zu_fuss = f is not None and (o["min"] is None or f <= o["min"])
        oepnv_min.append(f if zu_fuss else o["min"])
        umstiege.append(-1 if zu_fuss else o["umstiege"])
        zum_halt.append(None if zu_fuss else o["zum_halt_min"])
        zeiten = [t for t in (o["dauer_min"], f) if t is not None]
        oepnv_dauer.append(min(zeiten) if zeiten else None)

    return {"lat": [p[0] for p in punkte], "lon": [p[1] for p in punkte],
            "oepnv_min": oepnv_min, "oepnv_dauer_min": oepnv_dauer, "umstiege": umstiege,
            "zum_halt_min": zum_halt, "auto_min": auto, "rad_min": rad, "fuss_min": fuss}


def _gerundet(koordinaten, stellen: int = 5):
    if isinstance(koordinaten[0], (int, float)):
        return [round(k, stellen) for k in koordinaten]
    return [_gerundet(k, stellen) for k in koordinaten]


def zusammenfassung(zellen: dict):
    """Gibt für jede Spalte aus, wie viele Werte fehlen und wie die Zeiten verteilt sind."""
    n = len(zellen["lat"])
    for spalte in ("oepnv_min", "oepnv_dauer_min", "zum_halt_min", "auto_min", "rad_min", "fuss_min"):
        werte = sorted(w for w in zellen[spalte] if w is not None)
        if not werte:
            print(f"  {spalte:16s} keine Werte")
            continue
        q = statistics.quantiles(werte, n=4)
        print(f"  {spalte:16s} ohne Wert {n - len(werte):4d} ({(n - len(werte)) / n:4.0%})   "
              f"min {werte[0]:5.1f}  25 % {q[0]:5.1f}  Median {q[1]:5.1f}  75 % {q[2]:5.1f}  "
              f"max {werte[-1]:5.1f}")
    paare = [(o, a) for o, a in zip(zellen["oepnv_min"], zellen["auto_min"])
             if o is not None and a]
    if paare:
        print(f"  ÖPNV/Auto: Median des Verhältnisses {statistics.median(o / a for o, a in paare):.2f} "
              f"({len(paare)} Zellen mit beiden Werten)")
    print(f"  zu Fuß schneller als ÖPNV: {sum(u == -1 for u in zellen['umstiege'])} Zellen")
    weit = sum(w is not None and w > 20 for w in zellen["zum_halt_min"])
    print(f"  Fußweg zur ersten Haltestelle über 20 Minuten: {weit} Zellen")


def main():
    parser = argparse.ArgumentParser(description="Reisezeiten von einem Raster zum Ziel mit MOTIS berechnen")
    parser.add_argument("--datum", default="2026-11-24", help="Tag im Fahrplan (JJJJ-MM-TT)")
    parser.add_argument("--uhrzeit", default="07:30", help="Ortszeit, zu der man das Haus verlässt")
    parser.add_argument("--raster", type=int, default=500, help="Maschenweite in Metern")
    parser.add_argument("--max-fussweg", type=int, default=60,
                        help="Grenze für den Fußweg zur ersten und von der letzten Haltestelle in "
                             "Minuten (Wegkosten von MOTIS, höchstens 60)")
    parser.add_argument("--fenster", type=int, default=60,
                        help="Zeitfenster in Minuten für die kürzeste Verbindung (oepnv_dauer_min)")
    parser.add_argument("--parallel", type=int, default=4, help="gleichzeitige Anfragen")
    parser.add_argument("--stichprobe", type=int, help="nur so viele zufällige Rasterpunkte (zum Ausprobieren)")
    parser.add_argument("--server", default=SERVER, help="Adresse des MOTIS-Servers")
    parser.add_argument("--grenze", type=Path, default=GRENZE, help="GeoJSON mit der Gebietsgrenze")
    parser.add_argument("--ausgabe", type=Path, default=AUSGABE, help="Zieldatei (JSON)")
    args = parser.parse_args()

    t0 = time.time()
    werkzeug = server_pruefen(args.server)
    abfahrt = zeitpunkt(args.datum, args.uhrzeit)
    von, bis = fahrplan_zeitraum()
    if not von <= abfahrt.date() <= bis:
        print(f"Achtung: Der {abfahrt:%d.%m.%Y} liegt außerhalb des Fahrplans "
              f"({von:%d.%m.%Y} bis {bis:%d.%m.%Y}); es wird keine ÖPNV-Verbindung geben.")

    grenze = grenze_laden(args.grenze)
    punkte = raster_erzeugen(grenze, args.raster)
    if args.stichprobe:
        punkte = sorted(random.Random(1).sample(punkte, args.stichprobe), key=lambda p: (-p[0], p[1]))
    print(f"{werkzeug}, Abfahrt {abfahrt:%d.%m.%Y %H:%M} ({als_utc(abfahrt)}), {len(punkte)} Rasterpunkte")

    zellen = reisezeiten_berechnen(punkte, abfahrt=abfahrt, server=args.server,
                                   max_fussweg_s=args.max_fussweg * 60,
                                   fenster_s=args.fenster * 60, parallel=args.parallel)
    ende = abfahrt + timedelta(minutes=args.fenster)
    daten = {
        "erzeugt": date.today().isoformat(),
        "ziel": {"name": ZIEL_NAME, "lat": ZIEL[0], "lon": ZIEL[1]},
        "ziel_auto": {"name": ZIEL_AUTO_NAME, "lat": ZIEL_AUTO[0], "lon": ZIEL_AUTO[1]},
        "zeitpunkt": abfahrt.isoformat(),
        "raster_m": args.raster,
        "zelle_grad": zelle_in_grad(ZIEL, args.raster),
        "fahrplan": {"gueltig_von": von.isoformat(), "gueltig_bis": bis.isoformat()},
        "werkzeug": werkzeug,
        "annahmen": [
            f"ÖPNV: Man verlässt um {abfahrt:%H:%M} Uhr das Haus. Gezählt wird bis zur frühesten "
            "Ankunft am Ziel; die Wartezeit auf die erste Abfahrt zählt mit.",
            "Tür zu Tür mit Fußwegen. Welche Haltestelle man nimmt, entscheidet allein die "
            "früheste Ankunft; der Fußweg dorthin kann lang sein (zum_halt_min, technische "
            f"Grenze {args.max_fussweg} Minuten).",
            "Ist man zu Fuß früher da als mit jeder ÖPNV-Verbindung, gilt die Gehzeit (umstiege = -1).",
            f"oepnv_dauer_min: kürzeste Verbindung mit Abfahrt zwischen {abfahrt:%H:%M} und "
            f"{ende:%H:%M} Uhr, ohne Wartezeit.",
            "Fahrplan nach Plan: ohne Verspätungen und Ausfälle. Umsteigen mit der Voreinstellung "
            "von MOTIS, in der Regel 2 Minuten.",
            "Auto: reine Fahrzeit nach OpenStreetMap, ohne Stau, ohne Parkplatzsuche und ohne "
            f"Fußweg vom Parkplatz. Die Fahrt endet an der Stelle „{ZIEL_AUTO_NAME}“, "
            "weil der Campus autofrei ist.",
            "Fahrrad und zu Fuß: Zeiten nach OpenStreetMap mit den Standardgeschwindigkeiten "
            "von MOTIS, ohne Steigungen.",
            f"Start ist der Mittelpunkt der Rasterzelle. Liegt im Umkreis von {MAX_WEGABSTAND_M} m "
            "kein passender Weg, der zum Ziel führt, oder gibt es keine Verbindung, bleibt der "
            "Wert leer (null).",
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
