"""Szenarien (nahverkehr/szenarien.py) an einem kleinen, selbst gebauten Fahrplan.

Die Tests brauchen weder das Datenpaket noch MOTIS.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from pyproj import Transformer

import szenarien as sz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "daten"))
import herunterladen  # noqa: E402

DIENSTAG = date(2026, 11, 24)
SAMSTAG = date(2026, 11, 28)


def _tabelle(zeilen):
    return pd.DataFrame(zeilen).astype(str)


@pytest.fixture
def fahrplan():
    """Linie L1 von A über B nach C (je etwa 1,1 km): werktags alle 20 min von 6 bis 10 Uhr,
    samstags stündlich. Dazu Linie L2, die nicht verändert werden darf."""
    stops = _tabelle([{"stop_id": s, "stop_name": f"Halt {s}", "stop_lat": lat, "stop_lon": "7.4"}
                      for s, lat in [("A", "51.50"), ("B", "51.51"), ("C", "51.52")]])
    routes = _tabelle([{"route_id": "r1", "agency_id": "x", "route_short_name": "L1", "route_type": "3"},
                       {"route_id": "r2", "agency_id": "x", "route_short_name": "L2", "route_type": "3"}])
    tage = {"monday": "1", "tuesday": "1", "wednesday": "1", "thursday": "1", "friday": "1",
            "saturday": "0", "sunday": "0"}
    calendar = _tabelle([{"service_id": "werktag", **tage, "start_date": "20261101", "end_date": "20261130"},
                         {"service_id": "samstag", **{k: "0" for k in tage}, "saturday": "1",
                          "start_date": "20261101", "end_date": "20261130"}])
    trips, stop_times = [], []

    def fahrt(trip_id, route, dienst, ab_min, halte):
        trips.append({"route_id": route, "service_id": dienst, "trip_id": trip_id})
        for k, halt in enumerate(halte):
            t = (ab_min + 10 * k) * 60
            u = f"{t // 3600:02d}:{t % 3600 // 60:02d}:00"
            stop_times.append({"trip_id": trip_id, "arrival_time": u, "departure_time": u,
                               "stop_id": halt, "stop_sequence": str(k + 1)})

    for ab in range(6 * 60, 10 * 60, 20):
        fahrt(f"w{ab}", "r1", "werktag", ab, "ABC")
    for ab in range(6 * 60, 10 * 60, 60):
        fahrt(f"s{ab}", "r1", "samstag", ab, "ABC")
    for ab in range(6 * 60, 10 * 60, 30):
        fahrt(f"l2_{ab}", "r2", "werktag", ab, "CA")
    return {"agency": _tabelle([{"agency_id": "x", "agency_name": "Test"}]), "stops": stops,
            "routes": routes, "calendar": calendar,
            "calendar_dates": pd.DataFrame(columns=["service_id", "date", "exception_type"], dtype=str),
            "trips": _tabelle(trips), "stop_times": _tabelle(stop_times)}


def test_takt_verdoppeln(fahrplan):
    vorher = {k: v.copy() for k, v in fahrplan.items()}
    neu = sz.takt_verdoppeln(fahrplan, "L1", "07:00", "08:00", tag=DIENSTAG)
    # drei Fahrten (7:00, 7:20, 7:40) bekommen je eine Kopie 10 Minuten später
    kopien = neu["trips"][neu["trips"].trip_id.str.endswith("_takt")]
    assert sorted(kopien.trip_id) == ["w420_takt", "w440_takt", "w460_takt"]
    assert set(kopien.service_id) == {"werktag"}            # fährt an denselben Tagen wie das Vorbild
    st = neu["stop_times"][neu["stop_times"].trip_id == "w420_takt"]
    assert list(st.departure_time) == ["07:10:00", "07:20:00", "07:30:00"]
    # das Original bleibt unverändert
    for k in fahrplan:
        assert fahrplan[k].equals(vorher[k]), k
    # ohne Tag auch samstags (Takt 60 min: Kopie 30 min später)
    alle = sz.takt_verdoppeln(fahrplan, "L1", "07:00", "08:00")
    assert "s420_takt" in set(alle["trips"].trip_id)
    with pytest.raises(ValueError):
        sz.takt_verdoppeln(fahrplan, "X99")


def test_keine_kopie_auf_vorhandene_fahrt(fahrplan):
    """Liegt schon eine Fahrt im halben Takt daneben, wird nicht kopiert."""
    einmal = sz.takt_verdoppeln(fahrplan, "L1", "07:00", "08:00", tag=DIENSTAG)
    # Zweiter Aufruf: Der Takt (Median über den Tag) bleibt 20 min; jede Kopie läge 10 min
    # später genau auf einer vorhandenen Fahrt und entfällt.
    zweimal = sz.takt_verdoppeln(einmal, "L1", "07:00", "08:00", tag=DIENSTAG)
    assert len(zweimal["trips"]) == len(einmal["trips"])


def test_schreiben_und_lesen(fahrplan, tmp_path):
    neu = sz.takt_verdoppeln(fahrplan, "L1", "07:00", "08:00", tag=DIENSTAG)
    a = sz.gtfs_schreiben(neu, tmp_path / "a" / "gtfs.zip")
    b = sz.gtfs_schreiben(neu, tmp_path / "b" / "gtfs.zip")
    assert sz._pruefsumme(a) == sz._pruefsumme(b)            # gleicher Fahrplan, gleiche Datei
    gelesen = sz.gtfs_laden(a)
    for k in neu:
        assert gelesen[k].equals(neu[k].reset_index(drop=True)), k
    with pytest.raises(ValueError):
        sz.gtfs_schreiben(neu, sz.GTFS)                      # das Original bleibt unberührt


def test_fahrleistung_und_kennzahlen(fahrplan):
    f = sz.fahrleistung(fahrplan, DIENSTAG, linien=["L1"])
    assert f["Fahrten"] == 12
    km_je_fahrt = 2 * 0.01 * 6371.0 * 3.141592653589793 / 180       # zweimal 0,01° nach Norden
    assert f["Fahrzeugkilometer"] == pytest.approx(12 * km_je_fahrt, rel=1e-3)
    assert f["Fahrzeugstunden"] == pytest.approx(12 * 20 / 60)
    assert sz.fahrleistung(fahrplan, SAMSTAG, linien=["L1"])["Fahrten"] == 4
    assert sz.fahrleistung(fahrplan, DIENSTAG)["Fahrten"] == 12 + 8   # mit Linie L2
    neu = sz.takt_verdoppeln(fahrplan, "L1", "07:00", "08:00", tag=DIENSTAG)
    k = sz.kennzahlen(fahrplan, neu, DIENSTAG)
    assert k.loc["Fahrten", "Differenz"] == 3
    assert k.loc["Fahrzeugstunden", "Differenz"] == pytest.approx(1.0)
    assert k.loc["Fahrzeugkilometer", "Differenz"] == pytest.approx(3 * km_je_fahrt, abs=0.1)


def test_vergleichen():
    vorher = {"lat": [1, 2, 3, 4], "lon": [0, 0, 0, 0], "einwohner": [100, 200, 300, 400],
              "oepnv_min": [20, 40, 50, None]}
    nachher = dict(vorher, oepnv_min=[20, 28, 52, 30])
    tabelle, w = sz.vergleichen(vorher, nachher, grenze_min=30)
    assert list(tabelle.differenz[:3]) == [0, -12, 2]
    assert w.iloc[0] == 100                                  # vorher: nur die erste Zelle
    assert w.iloc[1] == 100 + 200 + 400                      # nachher: auch Zelle 2 und 4
    assert w.iloc[2] == pytest.approx((20 * 100 + 40 * 200 + 50 * 300) / 600, abs=0.01)
    assert w.iloc[3] == pytest.approx((20 * 100 + 28 * 200 + 52 * 300) / 600, abs=0.01)
    assert w["Zellen mindestens 1 min schneller"] == 1
    assert w["Zellen mindestens 1 min langsamer"] == 1
    with pytest.raises(ValueError):
        sz.vergleichen(vorher, dict(nachher, lat=[9, 9, 9, 9]))


def test_einwohner_je_zelle(tmp_path):
    """Jede 100-m-Zelle zählt zur 500-m-Zelle, in der ihr Mittelpunkt liegt."""
    import reisezeitkarte as rk
    utm_nach_3035 = Transformer.from_crs(rk.UTM, 3035, always_xy=True)
    utm_nach_grad = Transformer.from_crs(rk.UTM, 4326, always_xy=True)
    zeilen = []
    for x, y, ew in [(390_050, 5_707_050, 10), (390_450, 5_707_450, 5),   # in Zelle (780, 11414)
                     (390_550, 5_707_050, 7)]:                            # in der Nachbarzelle
        x3, y3 = utm_nach_3035.transform(x, y)
        zeilen.append(f"{x3:.1f},{y3:.1f},0,0,{ew}")
    datei = tmp_path / "einwohner.csv"
    datei.write_text("x_3035,y_3035,lon,lat,einwohner\n" + "\n".join(zeilen) + "\n", encoding="utf-8")
    punkte = []
    for x, y in [(390_250, 5_707_250), (390_750, 5_707_250), (391_250, 5_707_250)]:
        lon, lat = utm_nach_grad.transform(x, y)
        punkte.append((round(lat, 5), round(lon, 5)))
    assert rk.einwohner_je_zelle(punkte, 500, datei) == [15, 7, 0]


def test_paket_waehlen(tmp_path):
    datei = tmp_path / "paket.json"
    pk = lambda n: {"name": f"{n}.zip", "url": "u", "groesse": 1, "sha256": "x", "dateien": []}
    datei.write_text(json.dumps({"aktuell": "daten-2026-12", "pakete": {
        "daten-2026-11": pk("daten-2026-11"), "daten-2026-12": pk("daten-2026-12")}}), encoding="utf-8")
    assert herunterladen.paket_waehlen(None, datei)[0] == "daten-2026-12"
    assert herunterladen.paket_waehlen("daten-2026-11", datei)[0] == "daten-2026-11"
    assert herunterladen.paket_waehlen("daten-2026-11.zip", datei)[0] == "daten-2026-11"
    with pytest.raises(SystemExit):
        herunterladen.paket_waehlen("daten-2025-01", datei)
    # älteres Format mit nur einem Paket
    datei.write_text(json.dumps(pk("daten-2026-11")), encoding="utf-8")
    assert herunterladen.paket_waehlen(None, datei)[0] == "daten-2026-11"
