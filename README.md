# Routenplanung für wen? Starter für Informatik und Nachhaltigkeit

Material zu den Sitzungen „Routenplanung“ (18.11.2026) und „Fahrplanauskunft“ (16.12.2026)
im Modul *Informatik und Nachhaltigkeit* an der TU Dortmund (WiSe 2026/27) und
Startpunkt für vier Projektideen.

**Zur Webdemo:** <https://ls11ae.github.io/iun-routenplanung/>
(läuft im Browser, auch auf dem Handy, ohne Installation; auf Deutsch oder Englisch, Knopf
oben rechts; *English version:* <https://ls11ae.github.io/iun-routenplanung/?lang=en>)

| Ordner | Inhalt | für |
|---|---|---|
| [`webdemo/`](webdemo/) | Webseite: Routen für verschiedene Personen vergleichen, Algorithmen für kürzeste Wege beobachten und messen, Pareto-optimale Routen erkunden, Karte „Nahverkehr gegen Auto“ | Sitzung am 18.11., alle Projekte |
| [`wegenetz/`](wegenetz/) | Python-Starter mit OSMnx und NetworkX: Wegenetz laden, Kriterien aus OpenStreetMap ableiten, Routen je Persona | Projekte 2 bis 4 |
| [`nahverkehr/`](nahverkehr/) | Python-Starter mit dem Routenplaner MOTIS: Reisezeiten mit Bus und Bahn, Auto und Rad, Fahrplan-Szenarien; dazu ein eigener Connection Scan | Projekt 1 |
| [`daten/`](daten/) | Skripte, die das Datenpaket herunterladen oder neu erzeugen | alle |

Webseite und Python-Starter benutzen dieselben Daten und dieselben Kriterien: Die Personas
(wer bewertet Wege wie?) stehen in [`webdemo/personas.json`](webdemo/personas.json), die
Regeln dazu in [`wegenetz/routen_hilfen.py`](wegenetz/routen_hilfen.py).

## Die vier Projektideen

1. **Was wäre, wenn …? Eine bessere Verbindung zum Campus.** Die Karte „Nahverkehr gegen
   Auto“ in der Webdemo zeigt: Mit Bus und Bahn dauert der Weg zum Campus meist deutlich
   länger als mit dem Auto. Sie übernehmen die Verkehrsplanung: Sie entwerfen Änderungen am
   Fahrplan (dichterer Takt, neue Linie, abgestimmte Anschlüsse, Rad als Zubringer, …), bauen
   sie in den Fahrplan ein und messen ihre Wirkung: Reisezeiten, Menschen, die den Campus in
   30 Minuten erreichen, zusätzliche Fahrzeugkilometer und Emissionen. → [`nahverkehr/`](nahverkehr/)
2. **Entspannt mit dem Rad ans Ziel.** Was macht eine gute Radroute aus, was davon steht
   in OpenStreetMap, und welche weiteren Daten helfen (Unfallatlas, Höhenmodell)? Sie
   bauen einen Prototyp und prüfen ihn in der Umgebung der Uni. → [`wegenetz/`](wegenetz/)
3. **Ohne Stufen ans Ziel.** Dasselbe für Menschen mit Rollstuhl, Rollator oder
   Kinderwagen: Treppen, Bordsteine, Belag, Steigung, Aufzüge und der Umgang mit
   fehlenden Angaben. → [`wegenetz/`](wegenetz/)
4. **Sicher über die Straße.** Dasselbe für blinde und sehbehinderte Menschen: sichere
   Querungen, Ampeln mit akustischem Signal, Bodenindikatoren, einfache Wege und eine
   Wegbeschreibung. → [`wegenetz/`](wegenetz/)

## Loslegen mit Python

Sie brauchen Python 3.11 oder 3.12 ([python.org](https://www.python.org/downloads/); unter
Windows beim Installieren „Add python.exe to PATH“ ankreuzen) und etwa 1,5 GB Platz.
Kein Java, kein Docker.

**1. Repository holen:** mit `git clone https://github.com/ls11ae/iun-routenplanung.git`
oder über „Code → Download ZIP“. Danach eine Eingabeaufforderung im Ordner öffnen.

**2. Umgebung anlegen und Pakete installieren** (gemessen: knapp 7 Minuten, 630 MB):

Windows (Eingabeaufforderung `cmd`):

```
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

macOS und Linux:

```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Wer lieber conda benutzt: `conda create -n iun python=3.12`, `conda activate iun`, dann
ebenfalls `python -m pip install -r requirements.txt` (diese Variante ist nicht getestet).

**3. Datenpaket holen** (47 MB: Fahrplan, Wege, Höhen):

```
python daten/herunterladen.py
```

**4. Notebook starten:**

```
jupyter notebook
```

Im Browser öffnen Sie dann [`wegenetz/routen_start.ipynb`](wegenetz/routen_start.ipynb)
(Projekte 2 bis 4) oder [`nahverkehr/reisezeiten_motis.ipynb`](nahverkehr/reisezeiten_motis.ipynb)
(Projekt 1; dafür vorher MOTIS starten, siehe [`nahverkehr/`](nahverkehr/)). Für Projekt 1
zeigt danach [`nahverkehr/szenario_beispiel.ipynb`](nahverkehr/szenario_beispiel.ipynb) an
einem Beispiel, wie man den Fahrplan ändert und die Wirkung misst.

Alle Notebooks liegen mit ihren Ergebnissen im Repository. Sie können also erst lesen und
dann ausführen. Gemessen unter Windows 11 (8 Kerne, 16 GB): Wegenetz-Notebook etwa
2,5 Minuten beim ersten Mal, MOTIS-Notebook 1,5 Minuten, Szenario-Notebook gut 5 Minuten
beim ersten Mal (danach Sekunden), Fahrplan-Notebook unter einer Minute.

**Der Fahrplan veraltet:** Er gilt vom 07.11. bis 07.12.2026. Die Notebooks zeigen den
Zeitraum an und warnen. Ein neues Datenpaket holen Sie mit `git pull` und danach erneut
`python daten/herunterladen.py`. Ältere Pakete bleiben abrufbar (siehe [`daten/`](daten/)).

## Die Webdemo auf dem eigenen Rechner

Die Seite besteht nur aus HTML, CSS und JavaScript, es gibt keinen Build-Schritt. Weil
der Browser Daten nicht aus lokalen Dateien nachladen darf, braucht sie einen kleinen
Webserver. Python bringt einen mit:

```
cd webdemo
python -m http.server
```

Danach öffnen Sie <http://localhost:8000>. Die Seite lädt nichts von fremden Servern,
auch keine Kartenkacheln: Die Grundkarte ist aus OpenStreetMap-Daten erzeugt und liegt mit
im Ordner. Sie funktioniert deshalb auch ohne Internet.

**Zwei Sprachen:** Deutsch steht im HTML, die englische Fassung direkt daneben
(`data-en="…"` für den Inhalt eines Elements, `data-en-aria-label="…"` usw. für Attribute);
Texte, die erst das JavaScript erzeugt, stehen als `w("Deutsch", "English")` im Code, die
englischen Namen der Personas und Kriterien als `name_en` und `beschreibung_en` in
`personas.json`. Gewählt wird mit `?lang=en` bzw. `?lang=de` oder mit dem Knopf oben rechts
(`webdemo/js/sprache.js`); der Browser merkt sich die Wahl. Ein Test prüft, dass kein
sichtbarer Text ohne englische Fassung bleibt.

## Tests

```
python -m pytest tests
```

Geprüft werden die Kriterien und Personas an einem kleinen Beispielnetz, die Funktionen für
Fahrplan-Szenarien an einem kleinen Beispielfahrplan und, wenn
[Node.js](https://nodejs.org) installiert ist, dass Python und JavaScript dieselben Routen
liefern und dass alle Algorithmen der Webdemo dieselben Distanzen berechnen.

## Wichtig: Prototypen, keine Navigation

Alles hier dient der Lehre. Die Daten aus OpenStreetMap sind unvollständig und können
falsch sein, die Regeln und Gewichte sind bewusst einfach. Die berechneten Routen sind
**keine Empfehlung und keine Navigationshilfe**, auch nicht für Menschen mit Behinderung.
Bekannte Vereinfachungen: Im Wegenetz für die Personas werden Einbahnstraßen nicht
beachtet, Wartezeiten an Ampeln zählen nicht, Autozeiten sind ohne Stau und ohne
Parkplatzsuche gerechnet.

## Daten und Lizenzen

- Wege und Karte: © [OpenStreetMap-Mitwirkende](https://www.openstreetmap.org/copyright),
  Open Database License (ODbL); Auszüge von Geofabrik (Stand 12.11.2026), Radnetz der
  Algorithmen-Ansicht mit Stand 09.11.2026
- Fahrplan: [gtfs.de](https://gtfs.de), Daten von DELFI e.V., CC BY 4.0
- Höhen: Digitales Geländemodell DGM1, Geobasis NRW, Datenlizenz Deutschland Zero 2.0
- Einwohner: Zensus 2022, Bevölkerung im 100-m-Gitter, © Statistische Ämter des Bundes und der
  Länder, 2024, [Datenlizenz Deutschland – Namensnennung – Version 2.0](https://www.govdata.de/dl-de/by-2-0);
  auf Dortmund zugeschnitten und in `webdemo/daten/reisezeiten.json` je 500-m-Zelle summiert
- Emissionsfaktoren im Szenario-Notebook: Umweltbundesamt, Emissionsdaten Personenverkehr,
  Bezugsjahr 2024 (TREMOD)
- Kartendarstellung: [Leaflet](https://leafletjs.com) (BSD-2-Clause); Grundkarte der Webdemo
  aus OpenStreetMap-Daten (ODbL)
- Routenplaner: [MOTIS](https://github.com/motis-project/motis) (MIT)
- Die Algorithmen-Ansicht und die Bibliothek `webdemo/js/routing.js` stammen aus der
  Vorlesung „Algorithms and Sustainability“ (Kevin Buchin, TU Dortmund).

Der Code in diesem Repository steht unter der [MIT-Lizenz](LICENSE). Bitte nennen Sie in
Ihrem Poster die Datenquellen.

## Kontakt

Kevin Buchin, TU Dortmund, Fakultät für Informatik
