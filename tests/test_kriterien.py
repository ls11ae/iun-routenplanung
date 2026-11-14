"""Kriterien und Personas an einem kleinen, von Hand gebauten Netz (ohne Datenpaket)."""

import json

import networkx as nx
import pytest

import routen_hilfen as r


def kleines_netz():
    """Fünf Knoten in einer Reihe (je 100 m), dazu eine Treppe als Abkürzung.

        0 --Wohnstraße-- 1 --Hauptstraße-- 2 --Fußweg--> 3 (Querung) --Fußweg-- 4
        0 ------------------- Treppe (150 m) ------------------ 2
    """
    G = nx.MultiDiGraph(crs="epsg:4326")
    for i in range(5):
        G.add_node(i, x=7.40 + i * 0.00144, y=51.49)
    G.nodes[3].update(highway="crossing", crossing="traffic_signals", **{"traffic_signals:sound": "yes"},
                      tactile_paving="yes")
    G.nodes[4].update(kerb="raised")

    def beide(u, v, laenge, **merkmale):
        G.add_edge(u, v, length=laenge, **merkmale)
        G.add_edge(v, u, length=laenge, **merkmale)

    beide(0, 1, 100.0, highway="residential", surface="asphalt", sidewalk="both")
    beide(1, 2, 100.04, highway="secondary", surface="asphalt")
    beide(2, 3, 100.0, highway="footway", surface="sett")
    beide(3, 4, 100.0, highway=["footway", "path"])          # nach dem Vereinfachen: Liste
    beide(0, 2, 150.0, highway="steps", wheelchair="no")
    return r.kriterien_berechnen(G)


def kante(G, u, v):
    return G[u][v][0]


def test_meter_kriterien():
    G = kleines_netz()
    assert kante(G, 1, 2)["laenge"] == 100.0                  # auf Dezimeter gerundet
    assert kante(G, 1, 2)["hauptstrasse"] == 100.0
    assert kante(G, 0, 1)["hauptstrasse"] == 0
    assert kante(G, 1, 2)["fahrbahn"] == 100.0                # kein Gehweg erfasst
    assert kante(G, 0, 1)["fahrbahn"] == 0                    # sidewalk=both
    assert kante(G, 0, 2)["treppe"] == 150.0
    assert kante(G, 0, 2)["rollstuhl_verboten"] == 150.0
    assert kante(G, 2, 3)["belag_schlecht"] == 100.0          # Kopfsteinpflaster
    assert kante(G, 3, 4)["belag_unbekannt"] == 100.0
    assert kante(G, 2, 3)["rad_schieben"] == 100.0            # reiner Fußweg
    assert kante(G, 3, 4)["rad_schieben"] == 100.0            # im Zweifel vorsichtig: ein Teilstück Fußweg genügt
    assert kante(G, 1, 2)["rad_schieben"] == 0


def test_radweg_hebt_hauptstrasse_auf():
    G = kleines_netz()
    for u, v in [(1, 2), (2, 1)]:
        kante(G, u, v)["cycleway:right"] = "lane"
    r.kriterien_berechnen(G)
    assert kante(G, 1, 2)["hauptstrasse"] == 0


def test_querung_zaehlt_an_der_kante_in_den_knoten():
    G = kleines_netz()
    assert kante(G, 2, 3)["querung_akustisch"] == 1           # Fußweg führt in die Querung
    assert kante(G, 4, 3)["querung_akustisch"] == 1
    assert kante(G, 3, 2)["querung_akustisch"] == 0           # aus der Querung heraus
    assert kante(G, 2, 3)["querung_ohne_ampel"] == 0
    assert kante(G, 2, 3)["querung_ohne_bodenindikator"] == 0
    assert kante(G, 3, 4)["bordstein"] == 1
    assert kante(G, 4, 3)["bordstein"] == 0


@pytest.mark.parametrize("merkmale, art", [
    ({"highway": "crossing", "crossing": "uncontrolled"}, "ohne_ampel"),
    ({"highway": "crossing", "crossing": "zebra"}, "ohne_ampel"),
    ({"highway": "crossing"}, "ohne_ampel"),
    ({"highway": "crossing", "crossing": "traffic_signals"}, "ampel"),
    ({"highway": "crossing", "crossing": "traffic_signals", "traffic_signals:sound": "no"}, "ampel"),
    ({"highway": "crossing", "crossing": "traffic_signals", "traffic_signals:sound": "yes"}, "akustisch"),
    ({"highway": "bus_stop"}, ""),
    ({}, ""),
])
def test_querungsart(merkmale, art):
    assert r.querungsart(merkmale) == art


def test_personas_passen_zu_den_kriterien():
    daten = json.loads(r.PERSONAS_DATEI.read_text(encoding="utf-8"))
    ids = [k["id"] for k in daten["kriterien"]]
    assert sorted(ids) == sorted(r.KRITERIEN), "personas.json und routen_hilfen.KRITERIEN müssen übereinstimmen"
    assert set(daten["kennzahlen"]) <= set(ids) | {"zeit"}
    personas = daten["personas"]
    assert [p["id"] for p in personas] == ["fuss", "rad", "rollstuhl", "blind"]
    for p in personas:
        assert p["tempo"] > 0
        assert set(p["sperren"]) <= set(ids), p["id"]
        assert set(p["gewichte"]) <= set(ids), p["id"]
        assert all(g >= 0 for g in p["gewichte"].values()), "negative Gewichte machen Dijkstra falsch"
    # Routen unterscheiden sich in Farbe und Strichart
    assert len({p["farbe"] for p in personas}) == len(personas)
    assert len({p["strich"] for p in personas}) == len(personas)


def test_kosten_und_sperren(personas):
    G = kleines_netz()
    rad, rollstuhl = personas["rad"], personas["rollstuhl"]
    d = kante(G, 1, 2)                                         # 100 m Hauptstraße ohne Radweg
    assert r.zeit(d, rad) == pytest.approx(100 / rad["tempo"])
    assert r.kosten(d, rad) == pytest.approx(100 / rad["tempo"] + rad["gewichte"]["hauptstrasse"] * 100)
    schieben = kante(G, 2, 3)                                  # Fußweg: schieben
    assert r.zeit(schieben, rad) == pytest.approx(100 / rad["tempo_schieben"])
    assert r.kosten(kante(G, 0, 2), rad) is None               # Treppe gesperrt
    assert r.kosten(kante(G, 0, 2), rollstuhl) is None
    assert r.kosten(kante(G, 3, 4), rollstuhl) is None         # hoher Bordstein am Ende
    assert r.kosten(kante(G, 0, 2), personas["fuss"]) == pytest.approx(150 / personas["fuss"]["tempo"])


def test_route_meidet_gesperrtes(personas):
    G = kleines_netz()
    fuss, rad = personas["fuss"], personas["rad"]
    assert r.route(G, 0, 2, r.gewicht_fuer(fuss)) == [0, 2]            # Treppe ist kürzer
    assert r.route(G, 0, 2, r.gewicht_fuer(rad)) == [0, 1, 2]          # Treppe ist gesperrt
    k = r.bewerten(G, [0, 1, 2], rad)
    assert k["laenge"] == pytest.approx(200.0) and k["hauptstrasse"] == pytest.approx(100.0)
    assert k["kosten"] == pytest.approx(k["zeit"] + rad["gewichte"]["hauptstrasse"] * 100)
    # Der Rollstuhl erreicht Knoten 4 nicht (hoher Bordstein): nicht in der größten Komponente
    assert 4 not in r.groesste_komponente(G, r.gewicht_fuer(personas["rollstuhl"]))


def test_hoehenmeter_mit_hysterese():
    G = nx.MultiDiGraph()
    for i, h in enumerate([100, 101, 100, 101, 100, 106, 105, 110]):
        G.add_node(i, elevation=float(h))
    pfad = list(range(8))
    assert r.hoehenmeter(G, pfad, schwelle=3.0) == pytest.approx(10.0)   # nur der Anstieg 100 -> 110
    assert r.hoehenmeter(G, pfad, schwelle=0.5) == pytest.approx(13.0)   # jede Welle zählt
