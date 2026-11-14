# Routenplanung für wen? Starter für Informatik und Nachhaltigkeit

Material zu den Sitzungen „Routenplanung“ (18.11.2026) und „Fahrplanauskunft“ (16.12.2026)
im Modul *Informatik und Nachhaltigkeit* an der TU Dortmund (WiSe 2026/27) und
Startpunkt für vier Projektideen.

**Zur Webdemo:** <https://ls11ae.github.io/iun-routenplanung/>
(läuft im Browser, auch auf dem Handy, ohne Installation)

| Ordner | Inhalt | für |
|---|---|---|
| [`webdemo/`](webdemo/) | Webseite: Routen für verschiedene Personen vergleichen, Dijkstra und A* beobachten, Pareto-optimale Routen erkunden, Karte „Nahverkehr gegen Auto“ | Sitzung am 18.11., alle Projekte |
| [`wegenetz/`](wegenetz/) | Python-Starter mit OSMnx und NetworkX: Wegenetz laden, Kriterien aus OpenStreetMap ableiten, Routen je Persona | Projekte 2 bis 4 |
| [`nahverkehr/`](nahverkehr/) | Python-Starter mit dem Routenplaner MOTIS: Reisezeiten mit Bus und Bahn, Auto und Rad | Projekt 1 |
| [`daten/`](daten/) | Skripte, die das Datenpaket herunterladen oder neu erzeugen | alle |

Webseite und Python-Starter benutzen dieselben Daten und dieselben Kriterien: Die Personas
(wer bewertet Wege wie?) stehen in [`webdemo/personas.json`](webdemo/personas.json), die
Regeln dazu in [`wegenetz/routen_hilfen.py`](wegenetz/routen_hilfen.py).

## Die vier Projektideen

1. **Wo verliert der Nahverkehr gegen das Auto?** Sie berechnen für viele Startpunkte in
   Dortmund die Reisezeit mit Bus und Bahn, mit dem Auto und mit dem Rad, zeigen auf einer
   Karte, wo der Nahverkehr mithalten kann, und ordnen Ihre Annahmen kritisch ein
   (Parkplatzsuche, Stau, Takt, Tageszeit). → `nahverkehr/`
2. **Entspannt mit dem Rad ans Ziel.** Was macht eine gute Radroute aus, was davon steht
   in OpenStreetMap, und welche weiteren Daten helfen (Unfallatlas, Höhenmodell)? Sie
   bauen einen Prototyp und prüfen ihn in der Umgebung der Uni. → `wegenetz/`
3. **Ohne Stufen ans Ziel.** Dasselbe für Menschen mit Rollstuhl, Rollator oder
   Kinderwagen: Treppen, Bordsteine, Belag, Steigung, Aufzüge und der Umgang mit
   fehlenden Angaben. → `wegenetz/`
4. **Sicher über die Straße.** Dasselbe für blinde und sehbehinderte Menschen: sichere
   Querungen, Ampeln mit akustischem Signal, Bodenindikatoren, einfache Wege und eine
   Wegbeschreibung. → `wegenetz/`

## Die Webdemo auf dem eigenen Rechner

Die Seite besteht nur aus HTML, CSS und JavaScript, es gibt keinen Build-Schritt. Weil
der Browser Daten nicht aus lokalen Dateien nachladen darf, braucht sie einen kleinen
Webserver. Python bringt einen mit:

```
cd webdemo
python -m http.server
```

Danach öffnen Sie <http://localhost:8000>. Die Karte im Hintergrund kommt von
openstreetmap.org; ohne Internet zeichnet die Seite stattdessen das Wegenetz aus den Daten.

## Wichtig: Prototypen, keine Navigation

Alles hier dient der Lehre. Die Daten aus OpenStreetMap sind unvollständig und können
falsch sein, die Regeln und Gewichte sind bewusst einfach. Die berechneten Routen sind
**keine Empfehlung und keine Navigationshilfe**, auch nicht für Menschen mit Behinderung.
Bekannte Vereinfachungen: Einbahnstraßen werden nicht beachtet, Wartezeiten an Ampeln
zählen nicht, Autozeiten sind ohne Stau und ohne Parkplatzsuche gerechnet.

## Daten und Lizenzen

- Wege und Karte: © [OpenStreetMap-Mitwirkende](https://www.openstreetmap.org/copyright),
  Open Database License (ODbL), Auszüge von Geofabrik (Stand 12.11.2026)
- Fahrplan: [gtfs.de](https://gtfs.de), Daten von DELFI e.V., CC BY 4.0
  (gültig 07.11. bis 07.12.2026; der Fahrplan wird etwa monatlich erneuert)
- Höhen: Digitales Geländemodell DGM1, Geobasis NRW, Datenlizenz Deutschland Zero 2.0
- Kartendarstellung: [Leaflet](https://leafletjs.com) (BSD-2-Clause)
- Routenplaner: [MOTIS](https://github.com/motis-project/motis) (MIT)

Der Code in diesem Repository steht unter der [MIT-Lizenz](LICENSE). Bitte nennen Sie in
Ihrem Poster die Datenquellen.

## Kontakt

Kevin Buchin, TU Dortmund, Fakultät für Informatik
