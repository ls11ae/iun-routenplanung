"""Hilfsfunktionen, um den Fahrplan (GTFS) selbst zu lesen und zu verändern.

Für Gruppen in Projekt 1, die nicht nur einen fertigen Routenplaner befragen, sondern
am Fahrplan drehen wollen (etwa: Was bringt ein dichterer Takt auf einer Linie?).
Nur pandas, numpy und für Karten folium werden gebraucht. Die Funktionen sind bewusst
einfach gehalten; lesen und verändern ist ausdrücklich erwünscht.
"""

import warnings
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DATEN = Path(__file__).resolve().parent.parent / "daten"
GTFS_DATEI = DATEN / "dortmund-gtfs.zip"

VERKEHRSMITTEL = {0: "Straßenbahn", 1: "U-Bahn", 2: "Zug", 3: "Bus", 4: "Fähre", 7: "Seilbahn"}

GEHGESCHWINDIGKEIT = 1.2      # m/s, etwa 4,3 km/h
UMWEGFAKTOR = 1.3             # ein Fußweg ist länger als die Luftlinie
UMSTIEGSZEIT = 60             # s, Mindestzeit zum Umsteigen am selben Halt


def lade_gtfs(pfad=GTFS_DATEI):
    """Liest alle Tabellen eines GTFS-Zips in ein Wörterbuch von DataFrames."""
    g = {}
    with zipfile.ZipFile(pfad) as z:
        for name in z.namelist():
            if name.endswith(".txt"):
                with z.open(name) as f:
                    g[name[:-4]] = pd.read_csv(f, dtype=str, keep_default_na=False,
                                               encoding="utf-8")
    s = g["stops"]
    s["stop_lat"] = s.stop_lat.astype(float)
    s["stop_lon"] = s.stop_lon.astype(float)
    g["routes"]["route_type"] = g["routes"].route_type.astype(int)
    return g


def gueltigkeit(g):
    """Erster und letzter Tag, für den der Fahrplan Fahrten enthält (als date)."""
    c, cd = g["calendar"], g["calendar_dates"]
    tage = list(c.start_date) + list(c.end_date) + list(cd.date[cd.exception_type == "1"])
    als_tag = lambda t: datetime.strptime(t, "%Y%m%d").date()
    return als_tag(min(tage)), als_tag(max(tage))


def pruefe_gueltigkeit(g, tag=None):
    """Zeigt den Gültigkeitszeitraum und warnt, wenn der Fahrplan abgelaufen ist oder
    der gewählte Tag außerhalb liegt. Der Feed von gtfs.de gilt nur etwa einen Monat."""
    von, bis = gueltigkeit(g)
    print(f"Fahrplan gültig vom {von:%d.%m.%Y} bis {bis:%d.%m.%Y}.")
    if date.today() > bis:
        warnings.warn("Der Fahrplan ist abgelaufen. Holen Sie das aktuelle Datenpaket: "
                      "git pull, dann python daten/herunterladen.py", stacklevel=2)
    if tag is not None and not von <= tag <= bis:
        warnings.warn(f"Der {tag:%d.%m.%Y} liegt außerhalb des Fahrplans; "
                      "es gibt dann keine oder falsche Verbindungen.", stacklevel=2)
    return von, bis


def tag_waehlen(g, wochentag=1, ab=None):
    """Nächster Tag mit diesem Wochentag (0 = Montag, 1 = Dienstag), der im Fahrplan
    liegt und nicht vor `ab` (Voreinstellung: heute)."""
    von, bis = gueltigkeit(g)
    beginn = max(von, ab or date.today())
    tag = beginn + timedelta(days=(wochentag - beginn.weekday()) % 7)
    if tag > bis:        # Fahrplan abgelaufen: ersatzweise der letzte passende Tag darin
        tag = bis - timedelta(days=(bis.weekday() - wochentag) % 7)
    return tag


def aktive_dienste(g, tag: date):
    """Menge der service_id, die am gegebenen Tag fahren."""
    d = tag.strftime("%Y%m%d")
    wochentag = ["monday", "tuesday", "wednesday", "thursday", "friday",
                 "saturday", "sunday"][tag.weekday()]
    c = g["calendar"]
    aktiv = set(c.service_id[(c.start_date <= d) & (c.end_date >= d) & (c[wochentag] == "1")])
    cd = g["calendar_dates"]
    cd = cd[cd.date == d]
    aktiv |= set(cd.service_id[cd.exception_type == "1"])
    aktiv -= set(cd.service_id[cd.exception_type == "2"])
    return aktiv


def zeit_in_sekunden(spalte: pd.Series) -> np.ndarray:
    """'HH:MM:SS' (auch über 24:00 hinaus) in Sekunden seit Mitternacht."""
    # von hinten schneiden: die Stunden können ein-, zwei- oder dreistellig sein
    stunden = spalte.str.slice(0, -6).astype(int).to_numpy()
    minuten = spalte.str.slice(-5, -3).astype(int).to_numpy()
    sekunden = spalte.str.slice(-2).astype(int).to_numpy()
    return stunden * 3600 + minuten * 60 + sekunden


def uhrzeit(sek):
    sek = int(round(sek))
    return f"{sek // 3600:02d}:{sek % 3600 // 60:02d}"


def entfernung_m(lat1, lon1, lat2, lon2):
    """Luftlinie in Metern (Haversine); funktioniert auch mit numpy-Arrays."""
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def verbindungen(g, tag: date, von="06:00", bis="12:00"):
    """Elementarverbindungen (Fahrt von einem Halt zum nächsten) eines Tages.

    Ergebnis: DataFrame sortiert nach Abfahrtszeit mit den Spalten
    ab_halt, an_halt, ab, an (Sekunden), fahrt, einstieg_ok, ausstieg_ok, linie, typ.
    Fahrten, die am Vortag beginnen (Zeiten über 24:00), fehlen hier.
    """
    dienste = aktive_dienste(g, tag)
    trips = g["trips"][g["trips"].service_id.isin(dienste)]
    st = g["stop_times"][g["stop_times"].trip_id.isin(set(trips.trip_id))]
    # nach Fahrt und Reihenfolge der Halte sortieren (über Zahlen, das geht schnell)
    nummer = pd.factorize(st.trip_id)[0]
    st = st.iloc[np.lexsort((st.stop_sequence.astype(int).to_numpy(), nummer))]
    an_s = zeit_in_sekunden(st.arrival_time)
    ab_s = zeit_in_sekunden(st.departure_time)
    fahrt = st.trip_id.to_numpy()
    halt = st.stop_id.to_numpy()
    einstieg = st.pickup_type.to_numpy() != "1" if "pickup_type" in st else np.ones(len(st), bool)
    ausstieg = st.drop_off_type.to_numpy() != "1" if "drop_off_type" in st else np.ones(len(st), bool)
    gleiche_fahrt = fahrt[:-1] == fahrt[1:]          # Zeile i und i+1 gehören zur selben Fahrt
    c = pd.DataFrame({
        "ab_halt": halt[:-1], "an_halt": halt[1:],
        "ab": ab_s[:-1], "an": an_s[1:], "fahrt": fahrt[:-1],
        "einstieg_ok": einstieg[:-1], "ausstieg_ok": ausstieg[1:],
    })[gleiche_fahrt]
    lo, hi = zeit_in_sekunden(pd.Series([von + ":00", bis + ":00"]))
    c = c[(c.ab >= lo) & (c.ab <= hi)].copy()
    r = g["routes"].set_index("route_id")
    linie = trips.set_index("trip_id").route_id.reindex(c.fahrt).to_numpy()
    c["linie"] = r.route_short_name.reindex(linie).to_numpy()
    c["typ"] = r.route_type.reindex(linie).to_numpy()
    return c.sort_values(["ab", "an"], kind="stable").reset_index(drop=True)


def fusswege(g, max_meter=300):
    """Fußwege zwischen nahe beieinander liegenden Halten (Luftlinie mal Umwegfaktor).

    Ergebnis: dict halt -> Liste von (nachbarhalt, sekunden), einschließlich des
    Halts selbst mit der Umstiegszeit.
    """
    s = g["stops"]
    s = s[s.location_type.isin(["", "0"])][["stop_id", "stop_lat", "stop_lon"]].copy()
    # Gitter mit Zellen von etwa max_meter Kantenlänge
    s["gx"] = (s.stop_lon * 111320 * np.cos(np.radians(51.5)) // max_meter).astype(int)
    s["gy"] = (s.stop_lat * 110540 // max_meter).astype(int)
    paare = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            n = s.assign(gx=s.gx + dx, gy=s.gy + dy)
            paare.append(s.merge(n, on=["gx", "gy"], suffixes=("", "_2")))
    p = pd.concat(paare)
    p = p[p.stop_id != p.stop_id_2]
    p = p.assign(m=entfernung_m(p.stop_lat.to_numpy(), p.stop_lon.to_numpy(),
                                p.stop_lat_2.to_numpy(), p.stop_lon_2.to_numpy()))
    p = p[p.m <= max_meter]
    w = defaultdict(list)
    for halt in s.stop_id:
        w[halt].append((halt, UMSTIEGSZEIT))
    for a, b, m in zip(p.stop_id, p.stop_id_2, p.m):
        w[a].append((b, max(UMSTIEGSZEIT, int(m * UMWEGFAKTOR / GEHGESCHWINDIGKEIT))))
    return w


def halte_in_der_naehe(g, lat, lon, max_meter=800, tempo=GEHGESCHWINDIGKEIT):
    """Halte im Umkreis eines Ortes mit der Zeit dorthin in Sekunden (dict halt -> sekunden).

    Voreinstellung: zu Fuß bis 800 m. Mit dem Rad als Zubringer etwa
    max_meter=3000, tempo=4.2 (15 km/h).
    """
    s = g["stops"]
    s = s[s.location_type.isin(["", "0"])]
    m = entfernung_m(lat, lon, s.stop_lat.to_numpy(), s.stop_lon.to_numpy())
    nah = m <= max_meter
    return {h: int(d * UMWEGFAKTOR / tempo) for h, d in zip(s.stop_id[nah], m[nah])}


def gehzeit(von, nach):
    """Sekunden zu Fuß zwischen zwei Orten (lat, lon): Luftlinie mal Umwegfaktor."""
    return float(entfernung_m(von[0], von[1], nach[0], nach[1])) * UMWEGFAKTOR / GEHGESCHWINDIGKEIT


def halt_suchen(g, text):
    """Halte, deren Name den Text enthält (Groß-/Kleinschreibung egal)."""
    s = g["stops"]
    return s[s.stop_name.str.contains(text, case=False, regex=False)][
        ["stop_id", "stop_name", "parent_station", "stop_lat", "stop_lon"]]


def haltname(g, halt):
    if "_namen" not in g:
        g["_namen"] = dict(zip(g["stops"].stop_id, g["stops"].stop_name))
    return g["_namen"].get(halt, halt)


def takt_verdichten(c, linie, versatz_min):
    """Fügt für jede Fahrt der Linie eine zusätzliche Fahrt ein, die `versatz_min`
    Minuten später fährt. So lässt sich ausprobieren, was ein dichterer Takt bringt.
    Gibt eine neue, nach Abfahrt sortierte Tabelle zurück."""
    extra = c[c.linie == linie].copy()
    extra["ab"] += versatz_min * 60
    extra["an"] += versatz_min * 60
    extra["fahrt"] = extra.fahrt + "+"
    return pd.concat([c, extra]).sort_values(["ab", "an"], kind="stable").reset_index(drop=True)


def karte(g, reisen, start=None, ziel=None, namen=None):
    """Zeichnet eine oder mehrere Reisen (Listen von Abschnitten) auf eine Karte.
    Die Reisen unterscheiden sich in Farbe und Strichart."""
    import folium
    s = g["stops"].set_index("stop_id")
    k = folium.Map(location=start or (51.49, 7.45), zoom_start=12, tiles="OpenStreetMap")
    farben = ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]
    striche = [None, "10 6", "2 7", "14 5 2 5"]
    for i, reise in enumerate(reisen):
        for a in reise:
            punkte = [(s.stop_lat[h], s.stop_lon[h]) for h in a["halte"]]
            folium.PolyLine(punkte, color=farben[i % 4], weight=5, opacity=0.9,
                            dash_array=striche[i % 4],
                            tooltip=(f"{namen[i]}: " if namen else "")
                            + f"{a['linie']} ({a['verkehrsmittel']})").add_to(k)
    if start:
        folium.Marker(start, tooltip="Start").add_to(k)
    if ziel:
        folium.Marker(ziel, tooltip="Ziel", icon=folium.Icon(color="black", icon="flag")).add_to(k)
    return k
