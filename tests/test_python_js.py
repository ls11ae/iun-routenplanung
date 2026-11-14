"""Python (OSMnx/NetworkX) und JavaScript (Webdemo) müssen dieselben Routen liefern.

Python rechnet auf dem aus OSM geladenen Netz, JavaScript auf webdemo/daten/netz.json.
Verglichen werden Start- und Zielknoten nach dem Einrasten, die Kosten und alle
Kennzahlen für mehrere Start-Ziel-Paare und alle Personas. Braucht Node.js.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import routen_hilfen as r

WURZEL = Path(__file__).resolve().parent.parent
PAARE = [("Hauptbahnhof", "Phoenix-See"), ("Campus Nord", "Hauptbahnhof"),
         ("Campus Süd", "Phoenix-See"), ("Phoenix-See", "Campus Nord"),
         ("Campus Nord", "Campus Süd")]


@pytest.fixture(scope="module")
def js_ergebnisse(personas):
    if shutil.which("node") is None:
        pytest.skip("Node.js ist nicht installiert")
    if not (WURZEL / "webdemo" / "daten" / "netz.json").exists():
        pytest.skip("webdemo/daten/netz.json fehlt")
    anfragen = [{"persona": pid, "von": r.ORTE[a], "nach": r.ORTE[b]}
                for a, b in PAARE for pid in personas]
    aus = subprocess.run(["node", str(WURZEL / "tests" / "js" / "routen.js")],
                         input=json.dumps(anfragen), capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return anfragen, json.loads(aus.stdout)


def test_gleiche_kriterien(netz, js_ergebnisse):
    """Der Export enthält dieselben Kanten und Kriterien wie das Netz in Python."""
    summen = js_ergebnisse[1]["summen"]
    assert summen["kanten"] == netz.number_of_edges()
    for name in r.KRITERIEN:
        gesamt = sum(d[name] for _, _, d in netz.edges(data=True))
        assert summen[name] == pytest.approx(gesamt, rel=1e-9), name


def test_gleiche_routen(netz, personas, js_ergebnisse):
    anfragen, js = js_ergebnisse[0], js_ergebnisse[1]["routen"]
    knoten = sorted(netz.nodes)                      # Reihenfolge wie im Export
    komponenten = {}
    for q, e in zip(anfragen, js):
        p = personas[q["persona"]]
        gewicht = r.gewicht_fuer(p)
        if p["id"] not in komponenten:
            komponenten[p["id"]] = r.groesste_komponente(netz, gewicht)
        erlaubt = komponenten[p["id"]]
        assert e["komponente"] == len(erlaubt)
        start = r.naechster_knoten(netz, *q["von"], erlaubt=erlaubt)
        ziel = r.naechster_knoten(netz, *q["nach"], erlaubt=erlaubt)
        assert (knoten[e["start"]], knoten[e["ziel"]]) == (start, ziel), q
        k = r.bewerten(netz, r.route(netz, start, ziel, gewicht), p)
        assert e["kosten"] == pytest.approx(k["kosten"], rel=1e-9), q
        assert e["kosten_astern"] == pytest.approx(k["kosten"], rel=1e-9), q
        assert e["abgeschlossen_astern"] <= e["abgeschlossen"]
        # Verglichen werden die Kennzahlen, die in die Kosten eingehen. Die übrigen können
        # abweichen, wenn es zwei verschiedene Wege mit genau gleichen Kosten gibt (etwa
        # zwei gleich lange Kanten zwischen denselben Knoten).
        for name in ["zeit", *p["gewichte"]]:
            assert e["kennzahlen"][name] == pytest.approx(k[name], rel=1e-9, abs=1e-6), (q, name)
