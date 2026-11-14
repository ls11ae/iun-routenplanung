"""Hilfsfunktionen für Routen auf dem Wegenetz (Projekte 2 bis 4).

Aus OpenStreetMap-Merkmalen (tags) werden Kriterien je Kante abgeleitet, zum Beispiel
„Meter auf Treppen“ oder „Querungen ohne Ampel“. Eine Persona (webdemo/personas.json)
legt fest, wie stark jedes Kriterium zählt und welche Kanten gesperrt sind:

    Kosten einer Kante = Zeit + Summe über alle Kriterien (Gewicht mal Wert)

Die Regeln in `kriterien_berechnen` sind bewusst einfach und angreifbar. Sie zu
verbessern und zu begründen ist Teil Ihres Projekts. Die Webdemo benutzt genau
dieselben Kriterien (siehe export_webdemo.py).
"""

import hashlib
import json
import math
import pickle
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox

ORDNER = Path(__file__).resolve().parent
PERSONAS_DATEI = ORDNER.parent / "webdemo" / "personas.json"
DATEN = ORDNER.parent / "daten"

ORTE = {
    "Campus Nord": (51.4930, 7.4145),
    "Campus Süd": (51.4835, 7.4155),
    "Hauptbahnhof": (51.5176, 7.4590),
    "Phoenix-See": (51.4880, 7.5030),
}

# OSM-Merkmale, die beim Laden an Wegen und Knoten erhalten bleiben
WEG_MERKMALE = [
    "highway", "name", "surface", "smoothness", "incline", "width", "lit", "maxspeed",
    "access", "foot", "bicycle", "wheelchair", "motorroad", "oneway", "oneway:bicycle",
    "cycleway", "cycleway:left", "cycleway:right", "cycleway:both", "segregated",
    "footway", "sidewalk", "sidewalk:left", "sidewalk:right", "sidewalk:both",
    "crossing", "crossing:markings", "crossing:signals", "crossing:island",
    "tactile_paving", "traffic_signals:sound", "traffic_signals:vibration", "kerb",
    "step_count", "handrail", "ramp", "ramp:wheelchair", "tracktype", "bridge", "tunnel",
]
KNOTEN_MERKMALE = [
    "highway", "barrier", "kerb", "crossing", "crossing:markings", "crossing:signals",
    "crossing:island", "tactile_paving", "traffic_signals:sound",
    "traffic_signals:vibration", "button_operated", "wheelchair",
]
# Wegstücke mit unterschiedlichen Werten dieser Merkmale werden nicht zusammengelegt
VERGLEICHS_MERKMALE = [
    "highway", "footway", "surface", "wheelchair", "access", "foot", "bicycle",
    "cycleway", "cycleway:left", "cycleway:right", "cycleway:both",
    "sidewalk", "sidewalk:left", "sidewalk:right", "sidewalk:both",
]
# Knoten mit einem dieser Merkmale bleiben beim Vereinfachen erhalten
KNOTEN_BEHALTEN = ["highway", "kerb", "crossing", "barrier"]

SCHLECHTER_BELAG = {"cobblestone", "sett", "unhewn_cobblestone", "gravel", "pebblestone",
                    "fine_gravel", "grass", "ground", "dirt", "earth", "mud", "sand",
                    "woodchips", "grass_paver", "rock", "stepping_stones", "unpaved"}
HAUPTSTRASSE = {"primary", "primary_link", "secondary", "secondary_link", "trunk"}
NEBENSTRASSE = {"tertiary", "tertiary_link", "unclassified"}
STRASSE = HAUPTSTRASSE | NEBENSTRASSE | {"residential", "service", "road"}
NUR_FUSS = {"footway", "pedestrian", "steps", "corridor"}
FUSSWEG = NUR_FUSS | {"path", "cycleway", "bridleway", "track"}
ERLAUBT = {"yes", "designated", "permissive"}
STEIL_AB = 0.06               # mehr als 6 % Steigung gelten für Rollstühle als problematisch

KRITERIEN = ["laenge", "hauptstrasse", "nebenstrasse", "fahrbahn", "treppe",
             "belag_schlecht", "belag_unbekannt", "anstieg", "steil", "bordstein",
             "querung_ohne_ampel", "querung_ampel_stumm", "querung_akustisch",
             "querung_ohne_bodenindikator", "rad_schieben", "rollstuhl_verboten",
             "fuss_verboten", "rad_verboten"]


# ---------------------------------------------------------------- Laden

def _einstellungen():
    ox.settings.useful_tags_way = WEG_MERKMALE
    ox.settings.useful_tags_node = KNOTEN_MERKMALE


def _vereinfachen(G):
    """Legt Wegstücke zusammen, aber nur solche mit gleichen Merkmalen; Knoten mit
    Querung, Bordstein oder Sperre bleiben erhalten."""
    return ox.simplify_graph(G, edge_attrs_differ=VERGLEICHS_MERKMALE,
                             node_attrs_include=KNOTEN_BEHALTEN)


def lade_netz(pfad=DATEN / "dortmund-sued-wege.osm.bz2", zwischenspeicher=True):
    """Lädt das Wegenetz aus einer OSM-Datei (ohne Internet, etwa 40 Sekunden).

    Mit `zwischenspeicher=True` wird das fertige Netz neben der Datei abgelegt; der
    nächste Aufruf dauert dann nur wenige Sekunden.
    """
    pfad = Path(pfad)
    ablage = pfad.with_name(pfad.name + ".netz.pickle")
    stempel = (hashlib.sha256(pfad.read_bytes()).hexdigest(), tuple(WEG_MERKMALE), tuple(KNOTEN_MERKMALE),
               tuple(VERGLEICHS_MERKMALE), tuple(KNOTEN_BEHALTEN), ox.__version__)
    if zwischenspeicher and ablage.exists():
        with open(ablage, "rb") as f:
            alt, G = pickle.load(f)
        if alt == stempel:
            return G
    _einstellungen()
    G = ox.graph_from_xml(pfad, bidirectional=True, simplify=False, retain_all=False)
    G = _vereinfachen(G)
    if zwischenspeicher:
        with open(ablage, "wb") as f:
            pickle.dump((stempel, G), f, protocol=pickle.HIGHEST_PROTOCOL)
    return G


def lade_netz_online(ort=None, rechteck=None):
    """Lädt ein anderes Gebiet direkt aus OpenStreetMap (braucht Internet, dauert).

    ort: Name wie "Witten, Deutschland"; rechteck: (west, süd, ost, nord) in Grad.
    Einbahnstraßen werden wie in `lade_netz` ignoriert (alle Wege in beide Richtungen).
    """
    _einstellungen()
    filter_ = '["highway"]["area"!~"yes"]["highway"!~"motorway|motorway_link|trunk|' \
              'trunk_link|proposed|construction|platform|raceway|bus_guideway|abandoned|razed"]' \
              '["service"!~"parking_aisle|driveway|drive-through"]'
    alt = ox.settings.bidirectional_network_types
    ox.settings.bidirectional_network_types = ["all", "walk"]
    try:
        if ort is not None:
            G = ox.graph_from_place(ort, custom_filter=filter_, simplify=False)
        else:
            G = ox.graph_from_bbox(tuple(rechteck), custom_filter=filter_, simplify=False)
    finally:
        ox.settings.bidirectional_network_types = alt
    # custom_filter hat keinen Netztyp: Gegenrichtungen von Einbahnstraßen ergänzen
    fehlend = [(v, u, d) for u, v, d in G.edges(data=True) if not G.has_edge(v, u)]
    G.add_edges_from(fehlend)
    return _vereinfachen(G)


# ---------------------------------------------------------------- Kriterien

def _werte(d, schluessel):
    """Menge der Werte eines Merkmals (nach dem Vereinfachen kann es eine Liste sein)."""
    w = d.get(schluessel)
    if w is None:
        return set()
    return set(w) if isinstance(w, list) else {w}


def querungsart(d):
    """Art der Fußgängerquerung an einem Knoten (oder auf einem Querungsweg):
    '' (keine Querung), 'akustisch', 'ampel' oder 'ohne_ampel'."""
    hw, q = _werte(d, "highway"), _werte(d, "crossing") - {"no"}
    if not ("crossing" in hw or q or "crossing" in _werte(d, "footway")):
        return ""
    ampel = ("traffic_signals" in q or "traffic_signals" in hw
             or "yes" in _werte(d, "crossing:signals"))
    if not ampel:
        return "ohne_ampel"
    if _werte(d, "traffic_signals:sound") & {"yes", "walk"}:
        return "akustisch"
    return "ampel"


def kriterien_berechnen(G):
    """Schreibt an jede (gerichtete) Kante die Kriterien aus KRITERIEN als Zahlen:
    Meter (z. B. 'treppe') oder Stückzahlen (z. B. 'querung_ohne_ampel')."""
    for n, d in G.nodes(data=True):
        d["querung"] = querungsart(d) if "crossing" in _werte(d, "highway") or \
            _werte(d, "crossing") - {"no"} else ""
        d["bodenindikator"] = d.get("tactile_paving") == "yes"
        d["bordstein_hoch"] = d.get("kerb") in ("raised", "yes")

    for u, v, d in G.edges(data=True):
        m = round(d["length"], 1)      # Dezimeter genügen (und die Webdemo rechnet genauso)
        hw = _werte(d, "highway")
        belag = _werte(d, "surface")
        radweg = any(_werte(d, s) - {"no", "separate", "none"} for s in
                     ["cycleway", "cycleway:left", "cycleway:right", "cycleway:both"])
        rad_frei = bool(_werte(d, "bicycle") & ERLAUBT)
        rad_nein = bool(_werte(d, "bicycle") & {"no", "dismount"})
        fuss_frei = bool(_werte(d, "foot") & ERLAUBT)
        fuss_nein = bool(_werte(d, "foot") & {"no", "use_sidepath"}) or "yes" in _werte(d, "motorroad")
        gesperrt = bool(_werte(d, "access") & {"no", "private"})
        gehweg = any(_werte(d, s) & {"both", "left", "right", "yes"} for s in
                     ["sidewalk", "sidewalk:left", "sidewalk:right", "sidewalk:both"])
        fussweg = bool(hw & FUSSWEG)

        d["laenge"] = m
        # Im Zweifel vorsichtig: ein Teilstück mit Treppe macht die ganze Kante zur Treppe
        d["treppe"] = m * ("steps" in hw)
        d["belag_schlecht"] = m * bool(belag & SCHLECHTER_BELAG)
        d["belag_unbekannt"] = m * (not belag)
        ohne_radweg = not ("cycleway" in hw or radweg or rad_frei)
        d["hauptstrasse"] = m * (bool(hw & HAUPTSTRASSE) and ohne_radweg)
        d["nebenstrasse"] = m * (bool(hw & NEBENSTRASSE) and not (hw & HAUPTSTRASSE)
                                 and ohne_radweg)
        d["fahrbahn"] = m * (bool(hw & STRASSE) and not gehweg)
        d["rollstuhl_verboten"] = m * ("no" in _werte(d, "wheelchair"))
        d["fuss_verboten"] = m * ((fuss_nein and not fuss_frei) or (gesperrt and not fuss_frei))
        # Rad: auf reinen Fußwegen und wo Radfahren verboten ist, wird geschoben
        d["rad_schieben"] = m * ((bool(hw & NUR_FUSS) and not rad_frei) or rad_nein)
        d["rad_verboten"] = m * ((gesperrt and not rad_frei)
                                 or (rad_nein and d["fuss_verboten"] > 0))

        # Querung: zählt an der Kante, die über einen Fußweg in den Querungsknoten führt
        art = G.nodes[v]["querung"] if fussweg else ""
        d["querung_ohne_ampel"] = int(art == "ohne_ampel")
        d["querung_ampel_stumm"] = int(art == "ampel")
        d["querung_akustisch"] = int(art == "akustisch")
        tastbar = (G.nodes[v]["bodenindikator"] or G.nodes[u]["bodenindikator"]
                   or "yes" in _werte(d, "tactile_paving"))
        d["querung_ohne_bodenindikator"] = int(bool(art) and not tastbar)
        d["bordstein"] = int(G.nodes[v]["bordstein_hoch"] or
                             bool(_werte(d, "kerb") & {"raised", "yes"}))
        d.setdefault("anstieg", 0.0)
        d.setdefault("steil", 0.0)
    return G


def hoehen_ergaenzen(G, raster=DATEN / "dortmund-sued-hoehen.tif"):
    """Höhe je Knoten aus einem Höhenraster (bilinear interpoliert), daraus je Kante
    'anstieg' (Höhenmeter bergauf) und 'steil' (Meter mit mehr als 6 % Steigung)."""
    raster = Path(raster)
    if not raster.exists():
        print("Kein Höhenraster gefunden; Anstiege fehlen.")
        return G
    import rasterio
    knoten = list(G.nodes)
    x = np.array([G.nodes[n]["x"] for n in knoten])
    y = np.array([G.nodes[n]["y"] for n in knoten])
    with rasterio.open(raster) as src:
        band = src.read(1).astype("float64")
        t = ~src.transform                       # Koordinaten -> Rasterposition
        spalte, zeile = t.a * x + t.b * y + t.c, t.d * x + t.e * y + t.f
    # bilineare Interpolation zwischen den vier umliegenden Rasterpunkten (Zellmitten)
    s, z = spalte - 0.5, zeile - 0.5
    s0 = np.clip(np.floor(s).astype(int), 0, band.shape[1] - 2)
    z0 = np.clip(np.floor(z).astype(int), 0, band.shape[0] - 2)
    fs, fz = np.clip(s - s0, 0, 1), np.clip(z - z0, 0, 1)
    h = (band[z0, s0] * (1 - fs) * (1 - fz) + band[z0, s0 + 1] * fs * (1 - fz)
         + band[z0 + 1, s0] * (1 - fs) * fz + band[z0 + 1, s0 + 1] * fs * fz)
    aussen = (spalte < 0) | (spalte > band.shape[1]) | (zeile < 0) | (zeile > band.shape[0])
    h[aussen] = np.nan
    for n, wert in zip(knoten, h):
        G.nodes[n]["elevation"] = None if np.isnan(wert) else round(float(wert), 1)
    for u, v, d in G.edges(data=True):
        hu, hv = G.nodes[u]["elevation"], G.nodes[v]["elevation"]
        if hu is None or hv is None:
            d["anstieg"], d["steil"] = 0.0, 0.0
            continue
        dh = hv - hu
        m = round(d["length"], 1)
        d["anstieg"] = max(0.0, dh)
        # sehr kurze Kanten: Höhenunterschiede unter einem halben Meter sind Rauschen
        d["steil"] = m * (abs(dh) >= 0.5 and abs(dh) / max(m, 0.1) > STEIL_AB)
    return G


def datenqualitaet(G):
    """Wie vollständig sind die Angaben in OpenStreetMap? Gibt zwei Tabellen zurück:
    Anteil der Wegstücke mit Angabe je Merkmal und Angaben an den Querungen."""
    import pandas as pd
    kanten = [d for u, v, d in G.edges(data=True) if u < v]       # jede Strecke einmal
    gesamt = sum(d["length"] for d in kanten)
    merkmale = [("Belag", ["surface"]), ("Oberflächengüte", ["smoothness"]),
                ("Breite", ["width"]), ("Steigung", ["incline"]), ("Beleuchtung", ["lit"]),
                ("Tempolimit", ["maxspeed"]), ("für Rollstuhl geeignet", ["wheelchair"]),
                ("Gehweg an der Straße", ["sidewalk", "sidewalk:left", "sidewalk:right",
                                          "sidewalk:both"]),
                ("Radweg an der Straße", ["cycleway", "cycleway:left", "cycleway:right",
                                          "cycleway:both"]),
                ("Bodenindikatoren am Weg", ["tactile_paving"])]
    zeilen = []
    for name, schluessel in merkmale:
        mit = [d for d in kanten if any(d.get(s) is not None for s in schluessel)]
        zeilen.append({"Merkmal": name, "OSM-Schlüssel": ", ".join(schluessel),
                       "Anteil der Wegstücke": len(mit) / len(kanten),
                       "Anteil der Länge": sum(d["length"] for d in mit) / gesamt})
    wege = pd.DataFrame(zeilen).set_index("Merkmal")

    querungen = [d for _, d in G.nodes(data=True) if querungsart(d)]
    ampeln = [d for d in querungen if querungsart(d) != "ohne_ampel"]
    def anteil(liste, schluessel, werte=None):
        if not liste:
            return 0.0
        return sum(1 for d in liste if d.get(schluessel) is not None
                   and (werte is None or d.get(schluessel) in werte)) / len(liste)
    knoten = pd.DataFrame([
        {"Angabe": "Art der Querung (crossing)", "bezogen auf": f"{len(querungen)} Querungen",
         "Anteil mit Angabe": anteil(querungen, "crossing"), "davon ja": None},
        {"Angabe": "Bodenindikatoren (tactile_paving)", "bezogen auf": f"{len(querungen)} Querungen",
         "Anteil mit Angabe": anteil(querungen, "tactile_paving"),
         "davon ja": anteil(querungen, "tactile_paving", {"yes"})},
        {"Angabe": "Bordstein (kerb)", "bezogen auf": f"{len(querungen)} Querungen",
         "Anteil mit Angabe": anteil(querungen, "kerb"), "davon ja": None},
        {"Angabe": "akustisches Signal (traffic_signals:sound)", "bezogen auf": f"{len(ampeln)} Ampeln",
         "Anteil mit Angabe": anteil(ampeln, "traffic_signals:sound"),
         "davon ja": anteil(ampeln, "traffic_signals:sound", {"yes", "walk"})},
        {"Angabe": "Vibration (traffic_signals:vibration)", "bezogen auf": f"{len(ampeln)} Ampeln",
         "Anteil mit Angabe": anteil(ampeln, "traffic_signals:vibration"),
         "davon ja": anteil(ampeln, "traffic_signals:vibration", {"yes"})},
        {"Angabe": "Anforderungstaster (button_operated)", "bezogen auf": f"{len(ampeln)} Ampeln",
         "Anteil mit Angabe": anteil(ampeln, "button_operated"),
         "davon ja": anteil(ampeln, "button_operated", {"yes"})},
    ]).set_index("Angabe")
    return wege, knoten


# ---------------------------------------------------------------- Personas

def lade_personas(pfad=PERSONAS_DATEI):
    """Liest die gemeinsame Datei; gibt (dict id -> Persona, Liste der Kriterien) zurück."""
    daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    return {p["id"]: p for p in daten["personas"]}, daten["kriterien"]


def zeit(d, persona):
    """Sekunden für eine Kante (Daten `d`) mit dem Tempo der Persona."""
    schieben = d["rad_schieben"] if persona.get("tempo_schieben") else 0.0
    t = (d["laenge"] - schieben) / persona["tempo"]
    return t + schieben / persona["tempo_schieben"] if schieben else t


def kosten(d, persona):
    """Kosten einer Kante für eine Persona oder None, wenn die Kante gesperrt ist."""
    for s in persona["sperren"]:
        if d[s] > 0:
            return None
    k = zeit(d, persona)
    for kriterium, gewicht in persona["gewichte"].items():
        k += gewicht * d[kriterium]
    return k


def gewicht_fuer(persona):
    """Gewichtsfunktion gewicht(u, v, daten) für `route` und `bewerten`."""
    return lambda u, v, d: kosten(d, persona)


# ---------------------------------------------------------------- Routen

def groesste_komponente(G, gewicht):
    """Knoten des größten stark zusammenhängenden Teils, der mit `gewicht` benutzbar ist."""
    H = nx.DiGraph()
    H.add_edges_from((u, v) for u, v, d in G.edges(data=True) if gewicht(u, v, d) is not None)
    return max(nx.strongly_connected_components(H), key=len)


def naechster_knoten(G, lat, lon, gewicht=None, erlaubt=None):
    """Knoten mit der kleinsten Luftlinie zum Punkt.

    Mit `gewicht` (oder einer fertigen Knotenmenge `erlaubt`) werden nur Knoten im
    größten zusammenhängenden Teil des Netzes betrachtet, der mit diesem Kriterium
    benutzbar ist. Sonst landet man leicht auf einer „Insel“, etwa einem Bahnsteig,
    der nur über Treppen erreichbar ist.
    """
    if erlaubt is None and gewicht is not None:
        erlaubt = groesste_komponente(G, gewicht)
    knoten = list(G.nodes) if erlaubt is None else list(erlaubt)
    y = np.array([G.nodes[n]["y"] for n in knoten])
    x = np.array([G.nodes[n]["x"] for n in knoten])
    d = (y - lat) ** 2 + ((x - lon) * math.cos(math.radians(lat))) ** 2
    return knoten[int(np.argmin(d))]


def route(G, start, ziel, gewicht):
    """Kürzester Weg für eine Gewichtsfunktion gewicht(u, v, daten) -> Zahl oder None.

    None bedeutet: Kante darf nicht benutzt werden.
    """
    def w(u, v, kanten):
        werte = [gewicht(u, v, d) for d in kanten.values()]
        werte = [x for x in werte if x is not None]
        return min(werte) if werte else None
    return nx.shortest_path(G, start, ziel, weight=w)


def beste_kante(G, u, v, gewicht):
    """Zwischen zwei Knoten kann es mehrere Kanten geben: die mit den kleinsten Kosten."""
    return min((d for d in G[u][v].values() if gewicht(u, v, d) is not None),
               key=lambda d: gewicht(u, v, d))


def bewerten(G, pfad, persona):
    """Kennzahlen einer Route für eine Persona: Zeit, Kosten und alle Kriterien."""
    gewicht = gewicht_fuer(persona)
    s = dict.fromkeys(["zeit", "kosten"] + KRITERIEN, 0.0)
    for u, v in zip(pfad, pfad[1:]):
        d = beste_kante(G, u, v, gewicht)
        s["zeit"] += zeit(d, persona)
        s["kosten"] += gewicht(u, v, d)
        for k in KRITERIEN:
            s[k] += d[k]
    return s


def hoehenmeter(G, pfad, schwelle=3.0):
    """Summe der Anstiege entlang einer Route mit Hysterese: Ein Anstieg zählt erst,
    wenn er seit dem letzten Tiefpunkt mehr als `schwelle` Meter beträgt.

    Für grobe Oberflächenmodelle (Copernicus, mit Gebäuden und Bäumen) nötig, weil sich
    sonst das Rauschen kurzer Kanten aufsummiert. Mit dem Geländemodell DGM1 genügt die
    einfache Summe im Kriterium 'anstieg'; diese Funktion dient zum Vergleich.
    """
    hoehen = [G.nodes[n].get("elevation") for n in pfad]
    if any(h is None for h in hoehen):
        return 0.0
    summe, tief, hoch = 0.0, hoehen[0], hoehen[0]
    for h in hoehen[1:]:
        if h > hoch:
            hoch = h
        if hoch - h > schwelle:          # Abstieg beginnt: Anstieg abschließen
            if hoch - tief > schwelle:
                summe += hoch - tief
            tief = hoch = h
        elif h < tief:
            tief = hoch = h
    if hoch - tief > schwelle:
        summe += hoch - tief
    return summe


def linie(G, pfad, gewicht=None):
    """Koordinaten (lat, lon) einer Route mit dem genauen Verlauf der Kanten."""
    gewicht = gewicht or (lambda u, v, d: d["length"])
    punkte = [(G.nodes[pfad[0]]["y"], G.nodes[pfad[0]]["x"])]
    for u, v in zip(pfad, pfad[1:]):
        d = beste_kante(G, u, v, gewicht)
        if "geometry" in d:
            xy = list(d["geometry"].coords)
            if abs(xy[0][0] - G.nodes[u]["x"]) + abs(xy[0][1] - G.nodes[u]["y"]) > \
                    abs(xy[-1][0] - G.nodes[u]["x"]) + abs(xy[-1][1] - G.nodes[u]["y"]):
                xy = xy[::-1]
            punkte += [(y, x) for x, y in xy[1:]]
        else:
            punkte.append((G.nodes[v]["y"], G.nodes[v]["x"]))
    return punkte


def karte(G, routen, namen=None, farben=None, striche=None, gewichte=None):
    """Zeichnet Routen (Listen von Knoten) auf eine folium-Karte.

    Die Routen unterscheiden sich nicht nur in der Farbe, sondern auch in der Strichart.
    """
    import folium
    farben = farben or ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
    striche = striche or ["", "10 6", "1 9", "14 5 2 5", "6 5", "1 5"]
    alle = [n for r in routen for n in r]
    mitte = (np.mean([G.nodes[n]["y"] for n in alle]), np.mean([G.nodes[n]["x"] for n in alle]))
    k = folium.Map(location=mitte, zoom_start=14, tiles="OpenStreetMap")
    for i, r in enumerate(routen):
        folium.PolyLine(linie(G, r, gewichte[i] if gewichte else None),
                        color=farben[i % len(farben)], weight=5, opacity=0.9,
                        dash_array=striche[i % len(striche)] or None,
                        line_cap="round" if striche[i % len(striche)][:1] in ("", "1", "2") else "butt",
                        tooltip=(namen[i] if namen else f"Route {i + 1}")).add_to(k)
    return k
