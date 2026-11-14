# Nahverkehr: Starter für Projekt 1

*Was wäre, wenn …? Eine bessere Verbindung zum Campus.* Ausgangspunkt ist die Karte
„Nahverkehr gegen Auto“: Mit Bus und Bahn dauert der Weg zum Campus meist deutlich länger als
mit dem Auto. Ihr Projekt sind Szenarien: Sie ändern den Fahrplan (GTFS), rechnen ihn mit dem
Routenplaner [MOTIS](https://github.com/motis-project/motis) auf Ihrem eigenen Rechner durch und
messen, was die Änderung bringt (Reisezeiten, Menschen, die den Campus in 30 Minuten
erreichen) und was sie kostet (Fahrzeugkilometer, Emissionen).

## Loslegen

1. Python-Umgebung und Datenpaket wie im [README](../README.md) beschrieben.
2. **MOTIS starten:** `starten.bat` doppelklicken (Windows) oder `./starten.sh` ausführen
   (macOS, Linux). Beim ersten Mal lädt das Skript MOTIS 2.11.4 (52 MB, mit Prüfsumme) nach
   `nahverkehr/motis/` und bereitet Fahrplan und Wegenetz vor: etwa eine Minute, gut 1 GB
   Arbeitsspeicher, 300 MB auf der Platte. Danach startet der Server in Sekunden.
   Das Fenster offen lassen; beenden mit Strg+C.
3. Unter <http://localhost:8080> hat MOTIS eine eigene Oberfläche zum Ausprobieren.
4. [`reisezeiten_motis.ipynb`](reisezeiten_motis.ipynb) öffnen und ausführen.
5. [`szenario_beispiel.ipynb`](szenario_beispiel.ipynb): ein Szenario von Anfang bis Ende
   (die X13 zwischen 6 und 9 Uhr alle 15 statt alle 30 Minuten), mit Karten vorher und
   nachher, Kennzahlen, Kosten und einer Vorlage für die Klimabilanz. Ihre eigenen Szenarien
   bauen Sie genauso.

MOTIS gibt es für Windows, Linux und macOS mit Apple-Chip; für Intel-Macs gibt es kein
fertiges Programm.

## Inhalt

| Datei | Zweck |
|---|---|
| `reisezeiten_motis.ipynb` | Starter-Notebook: eine Anfrage, viele Startpunkte, Karte des Verhältnisses Bus und Bahn zu Auto |
| `szenario_beispiel.ipynb` | Beispiel-Szenario: Fahrplan ändern, mit MOTIS rechnen, Wirkung und Kosten messen |
| `szenarien.py` | Funktionen dafür: Fahrplan laden und als Kopie schreiben, Takt verdoppeln, Linien entfernen, Fahrleistung, Szenario mit MOTIS rechnen, vorher und nachher vergleichen, Karten |
| `reisezeitkarte.py` | Funktionen für die Abfragen; als Skript berechnet es das Raster der Webdemo (500 m, Median über 13 Abfahrten 7:00–8:00 Uhr, etwa fünf Minuten) |
| `abbildung_reisezeit.py` | zeichnet daraus die Abbildung in `abbildungen/` |
| `motis_einrichten.py`, `starten.bat`, `starten.sh` | MOTIS laden, einrichten und starten |
| `fahrplan_selbst_rechnen.ipynb`, `gtfs_hilfen.py`, `csa.py` | optional: den Fahrplan selbst lesen, mit dem Connection Scan durchrechnen und verändern |

## Gut zu wissen

- **Der Fahrplan gilt nur etwa einen Monat.** MOTIS kennt nur Tage im Gültigkeitszeitraum;
  die Notebooks zeigen ihn an und wählen einen passenden Dienstag. Nach einem neuen
  Datenpaket MOTIS neu starten, der Import läuft dann von selbst noch einmal.
- **Zeiten in UTC.** MOTIS erwartet Weltzeit (7:30 Uhr in Dortmund ist im Winter 06:30 UTC);
  `reisezeitkarte.zeitpunkt` und `als_utc` rechnen um.
- **Aus Python `127.0.0.1` statt `localhost` benutzen**, sonst dauert unter Windows jede
  Anfrage zwei Sekunden.
- **Autozeiten sind optimistisch:** freie Fahrt nach OpenStreetMap, ohne Stau und ohne
  Parkplatzsuche. Der Campus ist autofrei; das Auto fährt bis zur Emil-Figge-Straße.
- **Reisezeit mit Bus und Bahn:** Median über die Abfahrten 7:00, 7:05, …, 8:00 Uhr; je
  Abfahrt zählt die Wartezeit mit. Eine einzige Anfrage über das ganze Zeitfenster genügt
  (`oepnv_ueber_abfahrten`); sie liefert dieselben Werte wie 13 Einzelanfragen.
- **Sonderfälle der Karte:** Zellen, von denen der Campus zu Fuß in höchstens 15 Minuten
  erreichbar ist, und Zellen ohne Haltestelle mit Abfahrt zwischen 7 und 9 Uhr im Umkreis von
  1 km (Luftlinie) sind eigene Kategorien. Reisezeiten über 3 Stunden gelten als keine Verbindung.
- **Fußweg zum Halt:** erlaubt sind bis zu 60 Minuten, die früheste Ankunft entscheidet.
  Kleinere Grenzen schneiden in MOTIS manchmal Haltestellen ab, ohne dass man es merkt
  (`--max-fussweg` in `reisezeitkarte.py`).

## Szenarien rechnen

- **Das Original bleibt unberührt.** `szenarien.gtfs_schreiben` weigert sich, den Fahrplan in
  `daten/` zu überschreiben; jedes Szenario bekommt eine eigene Datei, am besten in seinem
  Ordner `motis/szenarien/<name>/`.
- **Jedes Szenario hat einen eigenen MOTIS-Ordner** (`motis/szenarien/<name>/`, nicht im Git).
  `motis_rechnen` kopiert dorthin die Daten des Hauptimports, importiert nur den geänderten
  Fahrplan (5 bis 10 Sekunden), startet einen eigenen Server auf Port 8090, rechnet alle
  Zellen und beendet den Server wieder. Die Kopie der Daten (150 MB) wird danach gelöscht;
  das Ergebnis bleibt als `reisezeiten-500m.json` liegen und wird beim nächsten Aufruf mit
  demselben Fahrplan wiederverwendet. Der Hauptserver auf Port 8080 darf dabei laufen.
- **Rechenzeit** (Windows 11, 8 Kerne): etwa 2,5 Minuten je Szenario für ganz Dortmund
  (1.125 Zellen), mit `raster_m=1000` etwa 45 Sekunden (283 Zellen). Beim allerersten Mal
  kommen das Laden von MOTIS und der Hauptimport dazu (etwa zwei Minuten).
- **Einwohner:** Zensus 2022 im 100-m-Gitter, auf die Rasterzellen summiert. Die Datei
  `daten/dortmund-einwohner.csv` kommt mit dem Datenpaket `daten-2026-12`; bis dahin nimmt
  `szenarien.einwohner` die Summen je 500-m-Zelle aus `webdemo/daten/reisezeiten.json`.
- **Fahrleistung:** Kilometer als Luftlinie zwischen den Halten (zu wenig), Stunden ohne
  Wende- und Pausenzeiten.

Quellen: Fahrplan [gtfs.de](https://gtfs.de) / DELFI e.V. (CC BY 4.0), Wege
© OpenStreetMap-Mitwirkende (ODbL), Einwohner: Zensus 2022, © Statistische Ämter des Bundes
und der Länder, 2024 (dl-de/by-2-0).
