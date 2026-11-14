"""Gemeinsame Vorbereitung für die Tests: Pfade und das geladene Wegenetz."""

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "wegenetz"))
sys.path.insert(0, str(WURZEL / "nahverkehr"))


@pytest.fixture(scope="session")
def netz():
    """Wegenetz Dortmund-Süd mit Kriterien und Höhen (braucht das Datenpaket)."""
    import routen_hilfen as r
    datei = r.DATEN / "dortmund-sued-wege.osm.bz2"
    if not datei.exists():
        pytest.skip("Datenpaket fehlt: zuerst python daten/herunterladen.py ausführen")
    G = r.lade_netz(datei)
    r.kriterien_berechnen(G)
    r.hoehen_ergaenzen(G)
    return G


@pytest.fixture(scope="session")
def personas():
    import routen_hilfen as r
    return r.lade_personas()[0]
