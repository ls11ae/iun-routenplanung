# Wegenetz: Starter für die Projekte 2 bis 4

*Entspannt mit dem Rad ans Ziel*, *Ohne Stufen ans Ziel*, *Sicher über die Straße*:
Hier leiten Sie aus OpenStreetMap Kriterien wie Treppen, Belag, Querungen und Steigung ab
und berechnen Routen für verschiedene Personen.

## Loslegen

1. Python-Umgebung und Datenpaket wie im [README](../README.md) beschrieben.
2. [`routen_start.ipynb`](routen_start.ipynb) öffnen und alle Zellen ausführen. Das erste
   Laden des Netzes dauert etwa eine Minute und braucht rund 1 GB Arbeitsspeicher; danach
   liegt das Netz in einer Zwischendatei und lädt in Sekunden.

## Inhalt

| Datei | Zweck |
|---|---|
| `routen_start.ipynb` | Starter-Notebook: Netz laden, Datenqualität, Kriterien, Routen je Persona, Karte, Ideen |
| `routen_hilfen.py` | Laden mit OSMnx, Kriterien aus OSM-Merkmalen, Personas, Routen, Bewertung, Karte |
| `export_webdemo.py` | schreibt das Netz mit allen Kriterien für die Webdemo (`webdemo/daten/netz.json`) |
| `../webdemo/personas.json` | Kriterien, Gewichte und Sperren der Personas; dieselbe Datei liest die Webdemo |

## So hängt es zusammen

- `kriterien_berechnen` schreibt an jede Kante Zahlen: Meter (z. B. `treppe`,
  `hauptstrasse`, `belag_schlecht`) oder Stückzahlen (z. B. `querung_ohne_ampel`, `bordstein`).
- Eine Persona hat ein Tempo, Sperren und Gewichte. Kosten einer Kante:
  Zeit + Summe aus Gewicht mal Kriterium. Eine Kante ist gesperrt, wenn ein gesperrtes
  Kriterium auf ihr größer als 0 ist.
- Wenn Sie eine Regel ändern, ändern sich die Routen im Notebook sofort. Für die Webdemo
  rufen Sie danach `python wegenetz/export_webdemo.py` auf; `python -m pytest tests` prüft,
  dass Python und JavaScript weiter dasselbe rechnen.

## Daten und Annahmen

- **Wegenetz:** Dortmund-Süd (Hauptbahnhof, Campus, Phoenix-See), © OpenStreetMap-Mitwirkende,
  ODbL, Stand 12.11.2026. Andere Gebiete lädt `lade_netz_online` direkt aus OpenStreetMap.
- **Höhen:** Geländemodell DGM1 von Geobasis NRW, auf 5 m gemittelt. Auf Brücken und in
  Unterführungen liefert es die Höhe des Bodens darunter oder darüber.
- **Vereinfachungen:** Alle Wege sind in beide Richtungen benutzbar (Einbahnstraßen werden
  ignoriert); Wartezeiten an Ampeln zählen nicht; die Regeln sind bewusst grob. Fehlende
  Angaben sind die Regel: Die Eignung für Rollstühle ist an 2 % der Weglänge eingetragen.
- **Keine Navigationshilfe:** Die Routen sind Ergebnisse eines Prototyps auf unvollständigen
  Daten, auch und gerade für Menschen mit Behinderung.
