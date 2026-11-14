# CLAUDE.md – iun-routenplanung

Starter-Repository für das Wahlmodul „Informatik und Nachhaltigkeit“ (CS228, TU Dortmund,
WiSe 2026/27), Sitzungen von Kevin Buchin am 18.11.2026 (Routenplanung) und 16.12.2026
(Fahrplanauskunft). Diese Datei hält Entscheidungen und Stand fest, damit spätere
Sitzungen anknüpfen können.

## Regeln für die Arbeit

- **Nicht pushen, Repo nicht öffentlich machen, kein Release anlegen, ohne vorher zu fragen.**
- Kleine Commits, Commit-Texte auf Deutsch.
- Alles für Studierende auf Deutsch, Anrede „Sie“, sachlich. Code-Bezeichner dürfen deutsch sein.
  Ausnahme: `webdemo/js/routing.js` und `werkzeuge/` sind aus der englischen AuS-Vorlesung übernommen.
- Keine Sicherheitsversprechen (besonders Projekt 4): Prototypen auf unvollständigen Daten.
- Gestaltung: schlicht, Okabe-Ito-Farben, Farbe nie einziger Bedeutungsträger (zusätzlich
  Strichart, Form oder Beschriftung), gute Kontraste, Alternativtexte.
- Daten nicht in den Git-Verlauf (Ausnahme: `webdemo/daten/`).
- Dateien immer mit `encoding="utf-8"` lesen und schreiben, Pfade mit `pathlib`.
- Nur lesen: Lehrmaterial unter
  `C:\Users\Buchin\Documents\GitLab\ls11ae\teaching\iun\seminarverzeichnis\2026-11-18_Buchin\`
  (Steckbriefe, Machbarkeitstest vom Oktober; `loesung/` und `otp/` nicht übernehmen) und die
  AuS-Vorlesung unter `C:\Users\Buchin\Documents\GitHub\ls11ae\algorithms-and-sustainability\`
  (`static/routing-demo`, `tools`, `lectures/05-route-planning-deck.md`).
- Rohdaten liegen in `C:\Users\Buchin\Documents\iun-rohdaten\` (nicht im Repo).

## Zielgruppe und Termine

- 40–50 Studierende (Bachelor ab 3. Semester), Gruppen mit 3–4 Personen, meist Windows.
  Vorwissen: Python, Dijkstra (DAP2). Kein GIS, Docker, Java voraussetzen.
- **Di 17.11. abends:** Teil A (Webdemo mit Algorithmen-Ansicht, Aufhänger-Karte, README).
- **ca. 01.12.:** Teil B (Python-Starter), Abstract der Gruppen am 02.12.
- **07.12.:** Der Fahrplan im Datenpaket läuft ab. 13.12. Fahrplanwechsel, 16.12. zweite
  Sitzung: Datenpaket vorher erneuern (siehe „Daten erneuern“). 27.01.2027 Poster.

## Die vier Projekte

1. Wo verliert der Nahverkehr gegen das Auto? → `nahverkehr/` (MOTIS, optional CSA)
2. Entspannt mit dem Rad ans Ziel → `wegenetz/`
3. Ohne Stufen ans Ziel (Rollstuhl, Rollator, Kinderwagen) → `wegenetz/`
4. Sicher über die Straße (blinde und sehbehinderte Menschen) → `wegenetz/`

## Aufbau

```
webdemo/              statische Seite für GitHub Pages, kein Build-Schritt
  index.html          Routen je Persona (Leaflet) und Pareto-Front      js/app.js, pareto.js, karte.js
  algorithmen.html    AuS-Demo auf Deutsch: Dijkstra, bidirektional, A*, ALT, CH   js/algorithmen.js
  reisezeit.html      Karte Nahverkehr gegen Auto                       js/reisezeit.js
  js/routing.js       DIE Routing-Bibliothek (aus AuS, erweitert); auch von kern.js benutzt
  js/kern.js          Netz lesen, Kosten je Persona, Pareto-Suche (Browser und Node)
  personas.json       EINE Datei für Python und JavaScript (Kriterien, Gewichte, Sperren, Tempo)
  daten/netz.json     Wegenetz Dortmund-Süd mit Kriterien (aus wegenetz/export_webdemo.py), 3 MB
  daten/dortmund-graph.json.gz, dortmund-ch.json.gz, radnetz-stats.json   Radnetz ganz Dortmund aus AuS, 8 MB
  daten/reisezeiten.json   Raster aus nahverkehr/reisezeitkarte.py
wegenetz/             routen_hilfen.py (Kriterien, Personas, Routen), routen_start.ipynb, export_webdemo.py
nahverkehr/           motis_einrichten.py, starten.bat/.sh, reisezeitkarte.py, abbildung_reisezeit.py,
                      reisezeiten_motis.ipynb; optional gtfs_hilfen.py, csa.py, fahrplan_selbst_rechnen.ipynb
daten/                daten_vorbereiten.py, paket_bauen.py (Lehrende), herunterladen.py (Studierende), paket.json
werkzeuge/            make_routing_demo.py, routing_prep.mjs (Radnetz und CH neu erzeugen)
abbildungen/          Abbildung für die Folien
tests/                pytest; tests/js/routen.js für den Vergleich Python/JavaScript
.github/workflows/pages.yml   veröffentlicht webdemo/
```

## Technische Entscheidungen

| Thema | Entscheidung | Grund |
|---|---|---|
| Werkzeuge | Python, OSMnx, NetworkX, pandas, folium; MOTIS; kein OTP, kein Docker | Vorgabe |
| Lizenz | Code MIT, © 2026 Kevin Buchin (bestätigt 14.11.) | |
| osmium | pip-Paket `osmium` (pyosmium) statt `osmium-tool` | conda ist nicht installiert; läuft so auf allen Systemen |
| Zwei Netze | Algorithmen-Ansicht: Radnetz ganz Dortmund aus AuS (112.743 Knoten, CH, 8 Landmarken, OSM 09.11.). Personas: Wegenetz Dortmund-Süd (53.940 Knoten) mit Zusatzmerkmalen | Wunsch vom 14.11.: AuS-Demo wiederverwenden; Zahlen stimmen mit der Folie „How much faster?“ |
| Routing-Bibliothek | `webdemo/js/routing.js` aus AuS; erweitert um `relaxed` (Kantenzähler), Gewicht als Name oder Feld, `search` exportiert | eine Bibliothek für Algorithmen- und Persona-Ansicht |
| Kosten einer Kante | `Zeit + Σ Gewicht_k · Kriterium_k`; gesperrt, wenn ein Kriterium aus `sperren` > 0 | Kosten einer Route = gewichtete Summe ihrer Kennzahlen |
| Gemeinsame Grundlage | Kriterien je gerichteter Kante in Python (`routen_hilfen.kriterien_berechnen`), Export nach `netz.json`; JS liest nur | Test: Python und JS liefern dieselben Kosten |
| Querungen | zählen an der Kante, die über einen Fußweg in einen Knoten `highway=crossing` führt | additiv, bewusst einfach |
| Höhen | DGM1 Geobasis NRW auf 5 m gemittelt; `anstieg = max(0, h(v) − h(u))` je Kante | additiv nötig für Gewichte und Pareto; mit Hysterese 3 m etwa 10–20 % weniger |
| Einbahnstraßen | im Wegenetz Dortmund-Süd ignoriert; das AuS-Radnetz beachtet sie | Vereinfachung wie im Oktober |
| Karte | Leaflet 1.9.4 in `webdemo/vendor/`, OSM-Kacheln mit Namensnennung, ohne Netz das eigene Wegenetz als Hintergrund; Algorithmen-Ansicht zeichnet selbst auf Canvas | läuft auch ohne Internet |
| Pareto | exakter Label-Setting-Algorithmus in `kern.js` mit unteren Schranken aus Rückwärtssuchen | 113 Routen Hbf → Phoenix-See in etwa 0,25 s (AuS ohne Schranken: 1,36 Mio. Labels, 7 s) |
| Pages | Workflow `.github/workflows/pages.yml`; in den Repo-Einstellungen Source „GitHub Actions“ wählen | |
| MOTIS | 2.11.4, `first_day` fest auf den Fahrplanbeginn, Server nur an 127.0.0.1:8080 | sonst liefern vergangene Tage nichts; keine Firewall-Nachfrage |
| A3 | Di 24.11.2026, 7:30 Uhr, Ziel Campus Nord (Auto: Emil-Figge-Straße, 180 m, weil der Campus autofrei ist), Raster 500 m, ÖPNV = früheste Ankunft bei Start 7:30 (bestätigt 14.11.), Fußweg zum Halt bis 60 min | 20 min schneidet in MOTIS stillschweigend Halte ab |

## Messwerte (14.11.2026, dieser Rechner, Windows 11, 8 Kerne, 16 GB)

- Datenvorbereitung: GTFS 138 s, OSM 220 s, Höhen 53 s (plus Download DGM1, 130 Kacheln, 282 MB)
- Datenpaket `daten-2026-11.zip`: 46,9 MB
- Netz laden: 50 s beim ersten Mal, danach wenige Sekunden (Zwischenspeicher); Route in Python 0,2–0,5 s
- Python und JS: 20 Routen und Summen aller 18 Kriterien identisch
- Algorithmen (TU → Phoenix-See, abgearbeitete Knoten): Dijkstra 62.880, bidirektional 33.547, A* 8.725, ALT 6.123, CH 239
- MOTIS: Download 52 MB, Import 44 s und 1,3 GB RAM, Server 0,1–0,3 GB, Raster (1.125 Zellen) 242 s
- Reisezeit: Median ÖPNV 52 min, Auto 12,4 min, Verhältnis 4,3 (mit +5 min: 2,9)
- Connection Scan: Tabelle der Verbindungen 7–8 s, eine Anfrage 0,3 s
- Installation der Pakete: 609 s (erster Versuch, während Downloads liefen)

## Stand

Stand 14.11.2026 (nichts gepusht, kein Release):

- [x] A1 Daten erneuert (Feed vom 07.11., gültig bis 07.12.; OSM 12.11.; DGM1)
- [x] A2 Webdemo: Routen je Persona, Pareto-Front, Algorithmen-Ansicht mit Statistik und Vergleich
- [x] A3 Reisezeitkarte: Daten, `reisezeit.html`, Abbildung in `abbildungen/`
- [x] A4 README (Grundfassung)
- [x] B1 `wegenetz/`: Hilfsmodul, Datenqualität, Notebook (ausgeführt)
- [x] B2 `nahverkehr/`: MOTIS-Skripte, Connection Scan mit Notebook (ausgeführt)
- [ ] B2 Notebook `reisezeiten_motis.ipynb`
- [ ] B3 requirements.txt, Installationsanleitung, pytest für Kriterien und Personas
- [ ] Release mit Daten (vorher fragen); `herunterladen.py` funktioniert erst danach

## Offene Entscheidungen (Kevin)

- Push, Repo öffentlich, Pages aktivieren (nötig bis 17.11. abends)
- Release `daten-2026-11` mit `daten/daten-2026-11.zip` (gh ist nicht installiert: im Browser anlegen)
- Reisezeitkarte: Fußweg-Grenze 60 oder 30 min; Ausreißerzelle Westfalenhütte (367 min)
- Soll der frühere Reiter „Dijkstra und A*“ (zwei Karten nebeneinander) zusätzlich zurückkommen?
- Impressum/Datenschutz-Hinweis auf den Pages-Seiten

## Daten erneuern (etwa monatlich, vor dem 07.12. und nach dem 13.12.)

```
# Rohdaten laden: gtfs.de (latest.zip), Geofabrik Arnsberg und Münster mit demselben Stand
python daten/daten_vorbereiten.py --rohdaten C:\Users\Buchin\Documents\iun-rohdaten --gtfs <gtfs>.zip --osm <arnsberg>.osm.pbf <muenster>.osm.pbf --dgm1
python wegenetz/export_webdemo.py          # nur wenn sich das Wegenetz oder die Kriterien geändert haben
python daten/paket_bauen.py --name daten-JJJJ-MM
python nahverkehr/motis_einrichten.py --server    # dann in zweitem Fenster:
python nahverkehr/reisezeitkarte.py --datum JJJJ-MM-TT && python nahverkehr/abbildung_reisezeit.py
```

## Bekannte Stolpersteine

- gtfs.de-Feed gilt etwa einen Monat; Notebooks zeigen die Gültigkeit und warnen.
- MOTIS: Zeiten in UTC; `localhost` ist aus Python langsam (IPv6 zuerst), daher 127.0.0.1;
  `directModes=CAR&transitModes=` für Auto; viele Ziele über `/api/v1/one-to-many` (höchstens 128).
- OSMnx: `edge_attrs_differ` und `node_attrs_include` beim Vereinfachen; Merkmale können Listen sein.
- Bash-Heredocs mit Backticks/Anführungszeichen scheitern im Werkzeug: Skripte lieber als Datei schreiben.
- Vorschau im minimierten Fenster liefert keine Bildschirmfotos: Edge ohne Fenster über das DevTools-Protokoll benutzen.
- pandas 3: kein `DataFrame._append`; Zeichenketten-Spalten langsam in Schleifen, vorher `.tolist()`.
