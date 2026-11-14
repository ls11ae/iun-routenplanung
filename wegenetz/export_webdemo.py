"""Exportiert das Wegenetz mit allen Kriterien kompakt für die Webdemo.

Aufruf im Wurzelverzeichnis:  python wegenetz/export_webdemo.py

Die Kriterien werden hier in Python berechnet (routen_hilfen.kriterien_berechnen);
die Webdemo liest sie nur noch. So rechnen Python und JavaScript auf derselben
Grundlage. Aufbau von webdemo/daten/netz.json (alle Werte ganze Zahlen):

knoten.x, knoten.y   Länge und Breite in Millionstel Grad, relativ zu `ursprung`
knoten.h             Höhe in Dezimetern
kanten.u, kanten.v   Endknoten (Positionen in den Knotenlisten)
kanten.l             Länge in Dezimetern
kanten.f             Flaggen: Bit i gesetzt heißt, das Kriterium flaggen[i] gilt auf der
                     ganzen Kante (Wert des Kriteriums = Länge)
kanten.art           0 Fuß-/Radweg, 1 kleine Straße, 2 Hauptstraße (nur fürs Zeichnen)
kanten.hin, .rueck   Stückzahlen am Ende der Kante in Richtung u->v bzw. v->u:
                     Bits 0-1 Querung (1 ohne Ampel, 2 Ampel ohne Ton, 3 Ampel mit Ton),
                     Bit 2 Querung ohne Bodenindikatoren, Bit 3 hoher Bordstein;
                     -1 in `rueck`: Die Gegenrichtung gibt es nicht.
kanten.gn, geo       Zwischenpunkte des Verlaufs: gn[i] Punkte je Kante, in `geo`
                     hintereinander als (dx, dy) zum jeweils vorigen Punkt, beginnend bei u

Der Anstieg einer Richtung ist max(0, h[Ende] - h[Anfang]) in Metern.
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import routen_hilfen as r  # noqa: E402

FLAGGEN = ["hauptstrasse", "nebenstrasse", "fahrbahn", "treppe", "belag_schlecht",
           "belag_unbekannt", "steil", "rad_schieben", "rollstuhl_verboten",
           "fuss_verboten", "rad_verboten"]
QUERUNG = {"querung_ohne_ampel": 1, "querung_ampel_stumm": 2, "querung_akustisch": 3}
ZIEL = r.ORDNER.parent / "webdemo" / "daten" / "netz.json"


def richtungscode(d):
    code = next((c for k, c in QUERUNG.items() if d[k]), 0)
    return code | (4 if d["querung_ohne_bodenindikator"] else 0) | (8 if d["bordstein"] else 0)


def art(d):
    hw = r._werte(d, "highway")
    if hw & r.HAUPTSTRASSE:
        return 2
    return 1 if hw & r.STRASSE or "living_street" in hw else 0


def exportieren(G, ziel=ZIEL, toleranz=1e-5):
    knoten = sorted(G.nodes)
    nummer = {n: i for i, n in enumerate(knoten)}
    x0 = min(G.nodes[n]["x"] for n in knoten)
    y0 = min(G.nodes[n]["y"] for n in knoten)
    gx = lambda x: round((x - x0) * 1e6)
    gy = lambda y: round((y - y0) * 1e6)

    # Hin- und Rückrichtung derselben Strecke zusammenfassen
    gruppen = {}
    for u, v, k, d in G.edges(keys=True, data=True):
        schluessel = (min(u, v), max(u, v), str(d.get("osmid")), d["laenge"])
        gruppen.setdefault(schluessel, []).append((u, v, d))

    K = {name: [] for name in ["u", "v", "l", "f", "art", "hin", "rueck", "gn"]}
    geo, einzeln = [], 0
    for schluessel in sorted(gruppen):
        teile = sorted(gruppen[schluessel], key=lambda t: (t[0], t[1]))
        hin = [t for t in teile if t[0] <= t[1]]
        rueck = [t for t in teile if t[0] > t[1]]
        if teile[0][0] == teile[0][1]:            # Schleife: beide Umlaufrichtungen einzeln
            paare, einzeln = [(t, None) for t in teile], einzeln + len(teile)
        elif len(hin) == len(rueck):
            paare = list(zip(hin, rueck))
        else:
            paare, einzeln = [(t, None) for t in teile], einzeln + len(teile)
        for (u, v, d), gegen in paare:
            flaggen = sum(1 << i for i, name in enumerate(FLAGGEN) if d[name] > 0)
            if gegen is not None:
                assert flaggen == sum(1 << i for i, name in enumerate(FLAGGEN)
                                      if gegen[2][name] > 0), (u, v)
            K["u"].append(nummer[u])
            K["v"].append(nummer[v])
            K["l"].append(round(d["laenge"] * 10))
            K["f"].append(flaggen)
            K["art"].append(art(d))
            K["hin"].append(richtungscode(d))
            K["rueck"].append(richtungscode(gegen[2]) if gegen is not None else -1)
            punkte = []
            if "geometry" in d:
                linie = d["geometry"].simplify(toleranz)
                xy = list(linie.coords)
                if abs(xy[0][0] - G.nodes[u]["x"]) + abs(xy[0][1] - G.nodes[u]["y"]) > \
                        abs(xy[-1][0] - G.nodes[u]["x"]) + abs(xy[-1][1] - G.nodes[u]["y"]):
                    xy = xy[::-1]
                punkte = xy[1:-1]
            K["gn"].append(len(punkte))
            px, py = gx(G.nodes[u]["x"]), gy(G.nodes[u]["y"])
            for x, y in punkte:
                geo += [gx(x) - px, gy(y) - py]
                px, py = gx(x), gy(y)

    stand_datei = r.DATEN / "stand.json"
    stand = json.loads(stand_datei.read_text(encoding="utf-8")) if stand_datei.exists() else {}
    netz = {
        "erzeugt": date.today().isoformat(),
        "quellen": {
            "wege": "© OpenStreetMap-Mitwirkende (ODbL), " + ", ".join(stand.get("osm", {}).get("quelle", [])),
            "hoehen": stand.get("hoehen", {}).get("quelle", "") + " ("
                      + stand.get("hoehen", {}).get("lizenz", "") + ")",
        },
        "ursprung": [x0, y0],
        "orte": {name: [lat, lon] for name, (lat, lon) in r.ORTE.items()},
        "flaggen": FLAGGEN,
        "knoten": {"x": [gx(G.nodes[n]["x"]) for n in knoten],
                   "y": [gy(G.nodes[n]["y"]) for n in knoten],
                   "h": [round((G.nodes[n].get("elevation") or 0) * 10) for n in knoten]},
        "kanten": K,
        "geo": geo,
    }
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(netz, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{ziel}: {ziel.stat().st_size / 1e6:.2f} MB, {len(knoten)} Knoten, "
          f"{len(K['u'])} Kanten ({einzeln} ohne Gegenrichtung), {len(geo) // 2} Zwischenpunkte")
    return knoten


if __name__ == "__main__":
    t = time.time()
    G = r.lade_netz()
    r.kriterien_berechnen(G)
    r.hoehen_ergaenzen(G)
    exportieren(G)
    print(f"{time.time() - t:.0f} s")
