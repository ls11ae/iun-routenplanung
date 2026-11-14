# CLAUDE.md – iun-routenplanung

Starter-Repository für das Modul „Informatik und Nachhaltigkeit“ an der TU Dortmund
(WiSe 2026/27): eine Webdemo zur Routenplanung und Python-Starter für vier Projektideen.
Diese Datei beschreibt Aufbau, Konventionen, Datenquellen und Tests für die Arbeit am Repo.

## Konventionen

- Alles für Studierende auf Deutsch, Anrede „Sie“, sachlich. Code-Bezeichner dürfen deutsch sein.
  Ausnahme: `webdemo/js/routing.js` und `werkzeuge/` stammen aus der englischsprachigen Vorlesung
  „Algorithms and Sustainability“ (AuS).
- Kleine Commits, Commit-Texte auf Deutsch.
- Keine Sicherheitsversprechen, besonders bei Barrierefreiheit: Alles sind Prototypen auf
  unvollständigen Daten, keine Navigationshilfe.
- Gestaltung: schlicht, Okabe-Ito-Farben, Farbe nie einziger Bedeutungsträger (zusätzlich
  Strichart, Form oder Beschriftung), gute Kontraste, Alternativtexte.
- Daten nicht in den Git-Verlauf. Ausnahme: die kompakten Daten der Webdemo in `webdemo/daten/`.
- Dateien immer mit `encoding="utf-8"` lesen und schreiben, Pfade mit `pathlib` (Windows!).
- Python und JavaScript rechnen auf derselben Grundlage: Kriterien werden in Python berechnet,
  JavaScript liest sie nur. Nach Änderungen an Kriterien oder Personas `export_webdemo.py`
  ausführen und die Tests laufen lassen.
- Lokale, nicht versionierte Notizen gehören in `CLAUDE.local.md` (steht in `.gitignore`).

## Die vier Projekte

1. Was wäre, wenn …? Eine bessere Verbindung zum Campus → `nahverkehr/` (Szenarien am Fahrplan
   mit MOTIS; die Reisezeitkarte „Nahverkehr gegen Auto“ ist der Aufhänger; optional Connection Scan)
2. Entspannt mit dem Rad ans Ziel → `wegenetz/`
3. Ohne Stufen ans Ziel (Rollstuhl, Rollator, Kinderwagen) → `wegenetz/`
4. Sicher über die Straße (blinde und sehbehinderte Menschen) → `wegenetz/`

## Aufbau

```
webdemo/              statische Seite für GitHub Pages, kein Build-Schritt
  index.html          Routen je Persona (Leaflet) und Pareto-Front      js/app.js, pareto.js, karte.js
  js/grundkarte.js    eigene Grundkarte aus daten/grundkarte.json (keine fremden Kacheln)
  algorithmen.html    Dijkstra, bidirektional, A*, ALT, CH mit Statistik   js/algorithmen.js
  reisezeit.html      Karte Nahverkehr gegen Auto                       js/reisezeit.js
  js/routing.js       die Routing-Bibliothek (aus AuS, erweitert); auch von kern.js benutzt
  js/kern.js          Netz lesen, Kosten je Persona, Pareto-Suche (Browser und Node)
  personas.json       EINE Datei für Python und JavaScript (Kriterien, Gewichte, Sperren, Tempo)
  daten/netz.json     Wegenetz Dortmund-Süd mit Kriterien (aus wegenetz/export_webdemo.py), 3 MB
  daten/dortmund-graph.json.gz, dortmund-ch.json.gz, radnetz-stats.json   Radnetz ganz Dortmund, 8 MB
  daten/reisezeiten.json   Raster aus nahverkehr/reisezeitkarte.py
wegenetz/             routen_hilfen.py (Kriterien, Personas, Routen), routen_start.ipynb, export_webdemo.py
nahverkehr/           motis_einrichten.py, starten.bat/.sh, reisezeitkarte.py, abbildung_reisezeit.py,
                      reisezeiten_motis.ipynb; optional gtfs_hilfen.py, csa.py, fahrplan_selbst_rechnen.ipynb
daten/                daten_vorbereiten.py, paket_bauen.py (Lehrende), herunterladen.py (Studierende), paket.json
werkzeuge/            make_routing_demo.py, routing_prep.mjs (Radnetz und CH), grundkarte.py
abbildungen/          Abbildung für die Folien
tests/                pytest; tests/js/ rechnet mit dem JavaScript-Kern in Node
.github/workflows/pages.yml   veröffentlicht webdemo/ über GitHub Pages
```

## Technische Entscheidungen

| Thema | Entscheidung | Grund |
|---|---|---|
| Werkzeuge | Python, OSMnx, NetworkX, pandas, folium; MOTIS als fertiger Routenplaner; kein Java, kein Docker | niedrige Einstiegshürde |
| Lizenz | Code MIT, © 2026 Kevin Buchin; Daten mit eigenen Lizenzen (siehe unten) | |
| osmium | pip-Paket `osmium` (pyosmium) statt `osmium-tool` | läuft unter Windows ohne conda |
| Zwei Netze | Algorithmen-Ansicht: Radnetz ganz Dortmund (112.743 Knoten, CH, 8 Landmarken). Personas: Wegenetz Dortmund-Süd (53.940 Knoten) mit Zusatzmerkmalen | das Radnetz hat keine Treppen und Fußwege nur zum Schieben |
| Routing-Bibliothek | `webdemo/js/routing.js`; erweitert um `relaxed` (Kantenzähler), Gewicht als Name oder Feld, `search` exportiert | eine Bibliothek für alle Ansichten |
| Kosten einer Kante | `Zeit + Σ Gewicht_k · Kriterium_k`; gesperrt, wenn ein Kriterium aus `sperren` > 0 | Kosten einer Route = gewichtete Summe ihrer Kennzahlen |
| Querungen | zählen an der Kante, die über einen Fußweg in einen Knoten `highway=crossing` führt | additiv, bewusst einfach |
| Höhen | DGM1 Geobasis NRW auf 5 m gemittelt; `anstieg = max(0, h(v) − h(u))` je Kante | additiv für Gewichte und Pareto; mit Hysterese 3 m etwa 10–20 % weniger |
| Einbahnstraßen | im Wegenetz Dortmund-Süd ignoriert; das Radnetz beachtet sie | Vereinfachung, im README genannt |
| Karte | Leaflet 1.9.4 in `webdemo/vendor/`; eigene Grundkarte (`werkzeuge/grundkarte.py`) statt OSM-Kacheln; Algorithmen-Ansicht zeichnet selbst auf Canvas | nichts von fremden Servern laden (Datenschutz); OSM erlaubt keinen Massen-Download von Kacheln |
| Pareto | exakter Label-Setting-Algorithmus in `kern.js` mit unteren Schranken aus Rückwärtssuchen; Ausdünnen mit `relevante` | Netz klein genug |
| Pages | Workflow `.github/workflows/pages.yml`, Quelle „GitHub Actions“ | ohne Actions nur `/` oder `/docs` |
| MOTIS | 2.11.4, `timetable.first_day` fest auf den Fahrplanbeginn, Server nur an 127.0.0.1:8080 | sonst liefern vergangene Tage nichts; keine Firewall-Nachfrage |
| Reisezeitkarte | Di 24.11.2026, Ziel Campus Nord (Auto: Emil-Figge-Straße, 180 m, weil der Campus autofrei ist), Raster 500 m; ÖPNV = Median über 13 Abfahrten 7:00–8:00 (je Abfahrt früheste Ankunft, Wartezeit zählt); über 3 h = keine Verbindung; Auto standardmäßig + 5 min; Klassen des Verhältnisses 1,5 / 2 / 2,5 / 3 / 4, ab 4 zusammengefasst; eigene Kategorien „Campus zu Fuß ≤ 15 min“ und „keine Haltestelle (Abfahrt 7–9 Uhr) im Umkreis von 1 km“; Fußweg zum Halt bis 60 min | eine feste Abfahrt hängt vom Zufall der Abfahrtsminute ab; kleinere Fußweg-Grenzen schneiden in MOTIS stillschweigend Halte ab |

## Datenquellen und Lizenzen

- Wege: © OpenStreetMap-Mitwirkende, ODbL (Geofabrik-Auszüge der Regierungsbezirke Arnsberg und
  Münster; Radnetz der Algorithmen-Ansicht aus der Overpass-API)
- Fahrplan: gtfs.de, Daten von DELFI e.V., CC BY 4.0 (gilt nur etwa einen Monat)
- Höhen: DGM1, Geobasis NRW, Datenlizenz Deutschland Zero 2.0
- Leaflet (BSD-2-Clause) in `webdemo/vendor/`; MOTIS (MIT) wird zur Laufzeit geladen
- Daten kommen als Release-Datei (`daten-JJJJ-MM.zip`); `daten/paket.json` nennt Adresse und Prüfsumme

## Daten erneuern (etwa monatlich und nach jedem Fahrplanwechsel)

```
python -m pip install -r daten/requirements-lehrende.txt
python daten/daten_vorbereiten.py --rohdaten ROHDATEN --gtfs GTFS.zip --osm ARNSBERG.osm.pbf MUENSTER.osm.pbf --dgm1
python wegenetz/export_webdemo.py          # nur wenn sich das Wegenetz oder die Kriterien geändert haben
python daten/paket_bauen.py --name daten-JJJJ-MM   # danach Release anlegen, paket.json committen
python nahverkehr/motis_einrichten.py --server    # dann in zweitem Fenster:
python nahverkehr/reisezeitkarte.py --datum JJJJ-MM-TT && python nahverkehr/abbildung_reisezeit.py
```

## Testen

```
python -m pytest tests                     # Kriterien, Personas; mit Node.js auch Python gegen JS und alle Algorithmen
jupyter nbconvert --to notebook --execute --inplace wegenetz/routen_start.ipynb
cd webdemo && python -m http.server        # Webdemo lokal unter http://localhost:8000
```

- `tests/test_python_js.py`: Python und JavaScript liefern dieselben Kosten und Kriterien.
- `tests/test_algorithmen.py`: Dijkstra, bidirektional, A*, ALT und CH liefern dieselben Distanzen.
- `tests/test_webdemo.py`: keine fremden Ladequellen (Skripte, Stylesheets, Kacheln, Daten) und
  stimmige Reisezeitdaten. Links auf Impressum und Datenschutz (Lehrstuhlseite) sind erlaubt.
- `nahverkehr/reisezeiten_motis.ipynb` braucht einen laufenden MOTIS-Server.
- Die Webdemo muss auch bei 390 px Breite ohne waagerechtes Scrollen funktionieren.

## Bekannte Stolpersteine

- Der gtfs.de-Feed gilt etwa einen Monat; Notebooks zeigen die Gültigkeit und warnen.
- MOTIS: Zeiten in UTC; aus Python `127.0.0.1` statt `localhost` (sonst 2 s je Verbindung unter
  Windows); Auto mit `directModes=CAR&transitModes=`; viele Ziele über `/api/v1/one-to-many`
  (höchstens 128 je Anfrage).
- OSMnx: `edge_attrs_differ` und `node_attrs_include` beim Vereinfachen; Merkmale können Listen sein.
- Bahnhöfe sind für den Rollstuhl oft Inseln hinter Treppen: Start und Ziel auf die größte stark
  zusammenhängende Komponente des jeweiligen Netzes einrasten.
- pandas 3: kein `DataFrame._append`; Zeichenketten-Spalten sind in Schleifen langsam, vorher `.tolist()`.
