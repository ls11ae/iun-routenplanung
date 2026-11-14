# Webdemo

Statische Seite ohne Build-Schritt; GitHub Pages veröffentlicht diesen Ordner
(Workflow `.github/workflows/pages.yml`). Lokal: `python -m http.server` in diesem Ordner,
dann <http://localhost:8000>.

| Seite | Inhalt | Daten |
|---|---|---|
| `index.html#routen` | Routen mehrerer Personas vergleichen, Gewichte selbst einstellen, Kriterien auf der Karte hervorheben | `daten/netz.json` (Wegenetz Dortmund-Süd), `personas.json` |
| `index.html#pareto` | alle Pareto-optimalen Routen für zwei Kriterien; welche findet eine gewichtete Summe, wie viele Labels und wie viel Zeit kostet das | wie oben |
| `algorithmen.html` | Dijkstra, bidirektionaler Dijkstra, A*, ALT und Contraction Hierarchies mit Animation, Statistik je Lauf, „Alle vergleichen“ und „Zufällige Paare“ | `daten/dortmund-graph.json.gz`, `dortmund-ch.json.gz` (Radnetz ganz Dortmund) |
| `reisezeit.html` | Raster über Dortmund: Reisezeit zum Campus Nord mit Bus und Bahn (Median über die Abfahrten 7:00–8:00 Uhr), Auto (mit 5 min Zuschlag für Parken) und Rad; Legende mit Annahmen auf der Karte | `daten/reisezeiten.json` |

## Aufbau des Codes

- `js/routing.js`: die Routing-Bibliothek (aus der Vorlesung „Algorithms and Sustainability“);
  läuft auch in Node, siehe `tests/js/`.
- `js/kern.js`: liest `netz.json`, bildet das Kostenfeld einer Persona und berechnet die
  Pareto-Front; kürzeste Wege rechnet `routing.js`.
- `js/app.js`, `js/pareto.js`, `js/karte.js`: Bedienung und Karte (Leaflet) von `index.html`.
- `js/grundkarte.js`, `daten/grundkarte.json`: eigene Grundkarte (Gewässer, Grünflächen, Bahn,
  Hauptstraßen, Ortsteilnamen) aus OpenStreetMap-Daten, erzeugt mit `werkzeuge/grundkarte.py`.
- `js/algorithmen.js`, `js/reisezeit.js`: die beiden anderen Seiten.
- `vendor/leaflet-1.9.4/`: Leaflet liegt im Repository. Die Seiten laden nichts von fremden
  Servern, auch keine Kartenkacheln; `tests/test_webdemo.py` prüft das.

## Die Algorithmen-Ansicht in Folien einbetten

`algorithmen.html` versteht dieselben Parameter wie das Original, zum Beispiel
`algorithmen.html?algo=ch&ui=legend&state=anim`:

| Parameter | Werte |
|---|---|
| `algo` | `dijkstra`, `bidir`, `astar`, `alt`, `ch`, `compare` (schnell und ruhig) |
| `metric` | `fast` (Reisezeit), `quiet` (ruhig) |
| `s`, `t` | Ort (`tu`, `phoenix`, `hbf`, `stadium`, `city`) oder Knotennummer |
| `state` | `final` (Ergebnis), `anim` (Animation läuft), `start` (nur Karte) |
| `ui` | `full`, `legend` (nur Karte mit Legende), `compact` (Karte mit kleiner Bedienleiste), `none` |
| `speed` | Faktor für das Tempo der Animation |
| `view` | Ausschnitt `x0,y0,x1,y1` in Metern |
| `algos` | Liste der angebotenen Algorithmen, z. B. `astar,alt` |

## Daten erneuern

- `daten/netz.json`: `python wegenetz/export_webdemo.py`
- Radnetz und CH: siehe [`werkzeuge/`](../werkzeuge/)
- `daten/reisezeiten.json`: `python nahverkehr/reisezeitkarte.py` (MOTIS muss laufen)
