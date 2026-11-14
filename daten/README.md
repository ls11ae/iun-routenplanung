# Daten

Die Daten liegen nicht im Repository, weil der Fahrplan etwa monatlich erneuert wird.

## Für Studierende

```
python daten/herunterladen.py
```

lädt das aktuelle Datenpaket (47 MB), prüft seine Prüfsumme und packt es in diesen Ordner aus.
Ohne Internet: `python daten/herunterladen.py --datei pfad/zum/paket.zip`.

Ältere Pakete bleiben abrufbar, etwa um den Fahrplan vor und nach dem Fahrplanwechsel am
13.12.2026 zu vergleichen. Welche es gibt, steht in `paket.json`:

```
python daten/herunterladen.py --liste
python daten/herunterladen.py --release daten-2026-11 --ziel daten/vor-fahrplanwechsel
```

Unterordner von `daten/` stehen in `.gitignore`.

| Datei | Inhalt | Quelle und Lizenz |
|---|---|---|
| `dortmund-gtfs.zip` | Fahrplan für Dortmund und Umgebung (GTFS) | gtfs.de / DELFI e.V., CC BY 4.0 |
| `dortmund-wege.osm.pbf` | Wege und Haltestellen für MOTIS | © OpenStreetMap-Mitwirkende, ODbL |
| `dortmund-sued-wege.osm.bz2` | Wegenetz Dortmund-Süd für OSMnx | © OpenStreetMap-Mitwirkende, ODbL |
| `dortmund-sued-hoehen.tif` | Geländehöhen, 5-m-Raster | DGM1, Geobasis NRW, Datenlizenz Deutschland Zero 2.0 |
| `dortmund-grenze.geojson` | Stadtgrenze Dortmund | © OpenStreetMap-Mitwirkende, ODbL |
| `dortmund-einwohner.csv` | Einwohner im 100-m-Gitter (ab `daten-2026-12`) | Zensus 2022, © Statistische Ämter des Bundes und der Länder, 2024, Datenlizenz Deutschland – Namensnennung – Version 2.0 |
| `stand.json` | Quellen, Stand und Gültigkeit des Fahrplans | |

## Für Lehrende: Datenpaket erneuern

Etwa monatlich und nach jedem Fahrplanwechsel. Braucht zusätzlich
`python -m pip install -r daten/requirements-lehrende.txt`.

1. Rohdaten laden: [GTFS Deutschland](https://download.gtfs.de/germany/free/latest.zip)
   und von [Geofabrik](https://download.geofabrik.de/europe/germany/nordrhein-westfalen.html)
   die Regierungsbezirke Arnsberg und Münster mit demselben Stand; einmalig vom
   [Zensus 2022](https://www.zensus2022.de) die Gitterzellen `Zensus2022_Bevoelkerungszahl.zip` (18 MB).
2. `python daten/daten_vorbereiten.py --rohdaten ORDNER --gtfs GTFS.zip --osm ARNSBERG.osm.pbf MUENSTER.osm.pbf --dgm1 --zensus Zensus2022_Bevoelkerungszahl.zip`
   (etwa sieben Minuten; die Höhen lädt `--dgm1` kachelweise von Geobasis NRW, 280 MB).
3. `python daten/paket_bauen.py --name daten-JJJJ-MM` schreibt die Zip-Datei und trägt sie als
   aktuelles Paket in `paket.json` ein; ältere Pakete bleiben dort stehen.
4. Auf GitHub ein Release mit dem Tag `daten-JJJJ-MM` anlegen, die Zip-Datei anhängen,
   `daten/paket.json` committen und pushen. Ältere Releases nicht löschen.
5. Reisezeitkarte der Webdemo neu berechnen: siehe [`nahverkehr/`](../nahverkehr/).

Gebiet: Rechteck 7,15–7,70° O, 51,38–51,62° N (Dortmund mit Bochum, Herne, Witten, Unna,
Lünen); Wegenetz für OSMnx: 7,37–7,53° O, 51,465–51,525° N.
