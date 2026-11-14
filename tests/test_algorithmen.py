"""Die fünf Algorithmen der Routing-Bibliothek liefern dieselben Distanzen (braucht Node.js)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent


def test_alle_algorithmen_gleiche_distanz():
    if shutil.which("node") is None:
        pytest.skip("Node.js ist nicht installiert")
    aus = subprocess.run(["node", str(WURZEL / "tests" / "js" / "algorithmen.js"), "40"],
                         capture_output=True, text=True, encoding="utf-8", check=True)
    e = json.loads(aus.stdout)
    assert e["abweichungen"] == 0
    # Die Zahlen der Folie „How much faster?“ (TU Dortmund → Phoenix-See, abgearbeitete Knoten)
    stand = json.loads((WURZEL / "webdemo" / "daten" / "radnetz-stats.json").read_text(encoding="utf-8"))
    folie = stand["tuPhoenix"]
    assert e["tuPhoenix"] == {"dijkstra": folie["dijkstra"]["settled"], "bidir": folie["bidirectional"]["settled"],
                              "astar": folie["astar"]["settled"], "alt": folie["alt"]["settled"],
                              "ch": folie["ch"]["settled"]}
    m = e["mittel"]
    assert m["dijkstra"] > m["bidir"] > m["astar"] > m["alt"] > m["ch"]
