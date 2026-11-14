# Nahverkehr: Starter für Projekt 1

*Wo verliert der Nahverkehr gegen das Auto?* Hier fragen Sie den Routenplaner
[MOTIS](https://github.com/motis-project/motis) ab, der auf Ihrem eigenen Rechner läuft:
Reisezeiten von Tür zu Tür mit Bus und Bahn, Auto, Rad und zu Fuß.

## Loslegen

1. Python-Umgebung und Datenpaket wie im [README](../README.md) beschrieben.
2. **MOTIS starten:** `starten.bat` doppelklicken (Windows) oder `./starten.sh` ausführen
   (macOS, Linux). Beim ersten Mal lädt das Skript MOTIS 2.11.4 (52 MB, mit Prüfsumme) nach
   `nahverkehr/motis/` und bereitet Fahrplan und Wegenetz vor: etwa eine Minute, gut 1 GB
   Arbeitsspeicher, 300 MB auf der Platte. Danach startet der Server in Sekunden.
   Das Fenster offen lassen; beenden mit Strg+C.
3. Unter <http://localhost:8080> hat MOTIS eine eigene Oberfläche zum Ausprobieren.
4. [`reisezeiten_motis.ipynb`](reisezeiten_motis.ipynb) öffnen und ausführen.

MOTIS gibt es für Windows, Linux und macOS mit Apple-Chip; für Intel-Macs gibt es kein
fertiges Programm.

## Inhalt

| Datei | Zweck |
|---|---|
| `reisezeiten_motis.ipynb` | Starter-Notebook: eine Anfrage, viele Startpunkte, Karte des Verhältnisses Bus und Bahn zu Auto |
| `reisezeitkarte.py` | Funktionen für die Abfragen; als Skript berechnet es das Raster der Webdemo (500 m, etwa vier Minuten) |
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
- **Fußweg zum Halt:** erlaubt sind bis zu 60 Minuten, die früheste Ankunft entscheidet.
  Kleinere Grenzen schneiden in MOTIS manchmal Haltestellen ab, ohne dass man es merkt
  (`--max-fussweg` in `reisezeitkarte.py`).

Quellen: Fahrplan [gtfs.de](https://gtfs.de) / DELFI e.V. (CC BY 4.0), Wege
© OpenStreetMap-Mitwirkende (ODbL).
