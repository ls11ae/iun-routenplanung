# Werkzeuge für die Algorithmen-Ansicht (für Lehrende)

Die Seite [`webdemo/algorithmen.html`](../webdemo/algorithmen.html) rechnet auf dem Radnetz
von ganz Dortmund. Graph, Contraction Hierarchy und Landmarken stammen aus der Vorlesung
„Algorithms and Sustainability“ (Kevin Buchin, TU Dortmund) und liegen fertig in
`webdemo/daten/` (OSM-Stand 09.11.2026). So lassen sie sich neu erzeugen:

```
python werkzeuge/make_routing_demo.py dortmund-highways.osm.gz webdemo/daten
node werkzeuge/routing_prep.mjs webdemo
```

| Skript | Aufgabe | Ergebnis |
|---|---|---|
| `make_routing_demo.py` | Radnetz aus OSM-XML (alle Wege mit `highway` im Stadtgebiet): Kreuzungsgraph mit den Gewichten „schnell“ (Reisezeit) und „ruhig“ | `dortmund-graph.json.gz` |
| `grundkarte.py` | Grundkarte der Webdemo aus den Geofabrik-Auszügen: Gewässer, Grünflächen, Bahn, Hauptstraßen, Ortsteilnamen (braucht `osmium`) | `webdemo/daten/grundkarte.json` |
| `routing_prep.mjs` | Contraction Hierarchy für die Reisezeit, 8 Landmarken, Prüfung aller Algorithmen gegen Dijkstra auf 300 Zufallspaaren, Messwerte für die Folien | `dortmund-ch.json.gz`, `radnetz-stats.json` |

Die Algorithmen selbst stehen in [`webdemo/js/routing.js`](../webdemo/js/routing.js); die
Persona-Ansicht benutzt dieselbe Bibliothek auf dem Wegenetz Dortmund-Süd.

Daten: © OpenStreetMap-Mitwirkende, ODbL. Der exportierte Graph ist eine abgeleitete Datenbank
und steht ebenfalls unter der ODbL.
