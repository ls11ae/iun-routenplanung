# CLAUDE.md – iun-routenplanung

Starter-Repository für das Wahlmodul „Informatik und Nachhaltigkeit“ (CS228, TU Dortmund,
WiSe 2026/27), Sitzungen von Kevin Buchin am 18.11.2026 (Routenplanung) und 16.12.2026
(Fahrplanauskunft). Diese Datei hält Entscheidungen und Stand fest, damit spätere
Sitzungen anknüpfen können. Der vollständige Auftrag steht in der ersten Sitzung
(14.11.2026); die Kurzfassung hier ist maßgeblich, wenn der Verlauf fehlt.

## Regeln für die Arbeit

- **Nicht pushen, Repo nicht öffentlich machen, kein Release anlegen, ohne vorher zu fragen.**
- Kleine Commits, Commit-Texte auf Deutsch.
- Alles für Studierende auf Deutsch, Anrede „Sie“, sachlich. Code-Bezeichner dürfen deutsch sein.
- Keine Sicherheitsversprechen (besonders Projekt 4): Prototypen auf unvollständigen Daten.
- Gestaltung: schlicht, Okabe-Ito-Farben, Farbe nie einziger Bedeutungsträger (zusätzlich
  Strichart, Symbol oder Beschriftung), gute Kontraste, Alternativtexte.
- Daten nicht in den Git-Verlauf (Ausnahme: kompakte Daten in `webdemo/daten/`).
- Dateien immer mit `encoding="utf-8"` lesen und schreiben, Pfade mit `pathlib`.
- Vorhandenes Material nur lesen:
  `C:\Users\Buchin\Documents\GitLab\ls11ae\teaching\iun\seminarverzeichnis\2026-11-18_Buchin\`
  (Steckbriefe in `projektideen/`, Machbarkeitstest in `projektpakete/`). `loesung/` und
  `otp/` nicht übernehmen.
- Rohdaten liegen in `C:\Users\Buchin\Documents\iun-rohdaten\` (nicht im Repo).

## Zielgruppe und Termine

- 40–50 Studierende (Bachelor ab 3. Semester), Gruppen mit 3–4 Personen, meist Windows.
  Vorwissen: Python, Dijkstra (DAP2). Kein GIS, Docker, Java voraussetzen.
- **Di 17.11. abends:** Teil A fertig (Webdemo, Aufhänger-Karte, minimales README).
- **ca. 01.12.:** Teil B fertig (Python-Starter), Abstract der Gruppen am 02.12.
- 13.12. Fahrplanwechsel, 16.12. zweite Sitzung, 27.01.2027 Poster.

## Die vier Projekte

1. Wo verliert der Nahverkehr gegen das Auto? → `nahverkehr/` (MOTIS, optional CSA)
2. Entspannt mit dem Rad ans Ziel → `wegenetz/`
3. Ohne Stufen ans Ziel (Rollstuhl, Rollator, Kinderwagen) → `wegenetz/`
4. Sicher über die Straße (blinde und sehbehinderte Menschen) → `wegenetz/`

## Aufbau des Repositorys (Plan)

```
README.md, LICENSE, requirements.txt, CLAUDE.md
webdemo/            statische Seite für GitHub Pages (kein Build-Schritt)
  index.html        Routen je Persona, Dijkstra/A*, Pareto-Front
  reisezeit.html    Karte ÖPNV/Auto zum Campus Nord (A3)
  personas.json     EINE Datei für Python und JavaScript (Gewichte, Sperren, Tempo)
  daten/            netz.json (aus Python exportiert), reisezeiten.json
  js/, css/, vendor/leaflet-1.9.4/
wegenetz/           routen_hilfen.py, Notebook, export_webdemo.py
nahverkehr/         MOTIS-Startskripte, Notebook, reisezeitkarte.py, optional csa.py
daten/              daten_vorbereiten.py (Lehrende), herunterladen.py (Studierende), Prüfsummen
abbildungen/        Abbildungen für die Folien (A3)
tests/              pytest, Vergleich Python/JavaScript (Node)
.github/workflows/  pages.yml (veröffentlicht webdemo/)
```

## Technische Entscheidungen

| Thema | Entscheidung | Grund |
|---|---|---|
| Werkzeuge | Python, OSMnx, NetworkX, pandas, folium; MOTIS; kein OTP, kein Docker | Vorgabe |
| osmium | Python-Paket `osmium` (pyosmium) per pip statt `osmium-tool` | conda ist auf dem Rechner nicht installiert; pip-Rad für Windows vorhanden; `daten_vorbereiten.py` läuft damit auf allen Systemen |
| Gemeinsame Grundlage | Kriterien je gerichteter Kante werden in Python berechnet (`wegenetz/routen_hilfen.py`) und nach `webdemo/daten/netz.json` exportiert; JavaScript rechnet nur noch Gewichte × Kriterien | Python und JS liefern dieselben Routen (Test in `tests/`) |
| Kosten einer Kante | `zeit + Σ gewicht_k · kriterium_k` (Sekunden-Äquivalente), `None`/∞ bei Sperre | Kosten einer Route = gewichtete Summe ihrer Kennzahlen; gut erklärbar |
| Personas | `webdemo/personas.json`: zu Fuß, Radpendlerin, Rollstuhlfahrer, blinde Studentin | liegt in `webdemo/`, weil Pages nur diesen Ordner ausliefert |
| Querungen | Zählen an der Kante, die über einen Fußweg in einen Knoten `highway=crossing` führt; Klassen: mit Ampel, mit akustischem Signal, ohne Ampel | additiv je Kante, bewusst einfache Regel |
| Höhenmeter | additiv je gerichteter Kante: `max(0, h(v) − h(u))` aus dem Geländemodell | muss kantenweise additiv sein (Gewichte, Pareto) |
| Höhenmodell | DGM1 Geobasis NRW (117 Kacheln, 239 MB roh), verkleinert auf 5 m; Copernicus nur als Rückfall | Geländemodell ohne Gebäude; Lizenz dl-de/zero-2-0 |
| Einbahnstraßen | werden ignoriert (wie im Oktober) | Vereinfachung, im README genannt; mögliche Projektaufgabe |
| Karte | Leaflet 1.9.4 lokal in `webdemo/vendor/` (kein CDN), OSM-Standardkacheln mit Namensnennung, zusätzlich eigenes Netz als Hintergrund | läuft auch ohne Internet im Hörsaal; Kachel-Richtlinie beachtet |
| Pareto | exakter zweikriterieller Label-Setting-Algorithmus in JS (Web Worker), Schranken aus Rückwärts-Dijkstra, Ausdünnen wie `relevante` | Netz ist klein genug |
| Pages | GitHub-Actions-Workflow, der `webdemo/` veröffentlicht | ohne Actions gingen nur `/` oder `/docs` |
| MOTIS | Version 2.11.4 (21.10.2026); `timetable.first_day` in `config.yml` fest setzen | sonst liefern vergangene Tage nichts |
| A3 | Di 24.11.2026, 7:30 Uhr (MEZ = 06:30 UTC), Ziel Campus Nord, Raster 500 m über Dortmund | Tag im Fahrplan und nicht vor heute |

## Stand

Stand 14.11.2026:

- [x] Material gesichtet, Werkzeuge geprüft (Python 3.12.4, Node 24, WSL vorhanden, kein conda)
- [x] Rohdaten geladen: `gtfs-de-free-261107.zip` (Feed vom 07.11.), `muenster-regbez-261112.osm.pbf`
- [ ] A1 Daten erneuern (GTFS-Zuschnitt, OSM für MOTIS, Wegenetz Dortmund-Süd, Höhen)
- [ ] A2 Webdemo
- [ ] A3 Aufhänger-Karte ÖPNV/Auto
- [ ] A4 Minimales README
- [ ] B1 `wegenetz/`
- [ ] B2 `nahverkehr/`
- [ ] B3 requirements, Anleitung, Tests, Release (vorher fragen)

## Offene Entscheidungen (Kevin)

- Lizenz MIT bestätigen, Copyright-Zeile
- Arnsberg-Auszug neu laden (Stand 12.11. wie Münster) oder Stand 14.10. behalten
- Push, Repo öffentlich, Pages aktivieren (nötig bis 17.11. abends)
- Release mit Daten (Teil B)

## Bekannte Stolpersteine

- gtfs.de-Feed gilt etwa einen Monat; Gültigkeit im Notebook anzeigen und warnen.
- MOTIS: Zeiten in UTC; `directModes=CAR&transitModes=` für Auto; `legGeometry` Polyline
  mit Genauigkeit 6; Import braucht bis 3,6 GB; `localhost` ohne Proxy ansprechen.
- OSMnx: `edge_attrs_differ` beim Vereinfachen; Merkmale können Listen sein; Start/Ziel auf
  die größte stark zusammenhängende Komponente des jeweiligen Netzes einrasten.
- pandas 3: kein `DataFrame._append`.
- OSM-Datenlage (Oktober): Belag 87 %, `wheelchair` 3 %, `incline` 4 % der Wegstücke.
