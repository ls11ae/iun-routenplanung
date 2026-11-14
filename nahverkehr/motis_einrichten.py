"""MOTIS einrichten: Programm laden, Fahrplan und Straßennetz importieren, Server starten.

MOTIS (https://github.com/motis-project/motis) ist ein Routenplaner für den öffentlichen
Verkehr. Es ist ein einzelnes Programm; Java oder Docker brauchen Sie nicht. Dieses Skript

1. lädt MOTIS in der festen Version 2.11.4 passend zu Ihrem Betriebssystem nach
   nahverkehr/motis/ und entpackt es dort,
2. erzeugt die Konfiguration (config.yml) für die Daten aus dem Ordner daten/ und trägt
   den Gültigkeitszeitraum des Fahrplans ein,
3. importiert Fahrplan und Straßennetz (einmalig; etwa eine Minute, gut 1 GB
   Arbeitsspeicher, danach rund 180 MB im Ordner nahverkehr/motis/data),
4. startet mit --server den Server (http://localhost:8080, beenden mit Strg+C).

Aufruf im Wurzelverzeichnis des Repositorys:

    python nahverkehr/motis_einrichten.py            # nur einrichten
    python nahverkehr/motis_einrichten.py --server   # einrichten und Server starten

Noch einfacher: nahverkehr/starten.bat (Windows) oder nahverkehr/starten.sh (macOS, Linux).

Was schon vorhanden ist, wird übersprungen; importiert wird nur dann erneut, wenn sich die
Daten geändert haben. Das Skript braucht nur die Standardbibliothek von Python.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import platform
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

VERSION = "2.11.4"
ADRESSE = f"https://github.com/motis-project/motis/releases/download/v{VERSION}/"

# Archiv je Plattform mit SHA-256-Prüfsumme (von der Release-Seite, Stand 14.11.2026)
ARCHIVE = {
    ("Windows", "amd64"): ("motis-windows.zip",
                           "5617760d47c1828f11a45bc9d034d719dd1dded1e1ac694fd14a3cf757450ad0"),
    ("Linux", "amd64"): ("motis-linux-amd64.tar.bz2",
                         "b521bb29c961a3b994ff4dac663778ba64fee7b4cfaf3f2b20ff1d5e1d15e0dc"),
    ("Linux", "arm64"): ("motis-linux-arm64.tar.bz2",
                         "76f41df5bb4db14ccd163dad0a23dd85bebbb9f21a9736834e9b3d4201080f3b"),
    ("Darwin", "arm64"): ("motis-macos-arm64.tar.bz2",
                          "02753c7e6487beaede33b7ea1b37e6349cb5387de8be8c35be7137d55c7da9d7"),
}

ORDNER = Path(__file__).resolve().parent / "motis"   # Programm, config.yml, data/
DATEN = Path(__file__).resolve().parent.parent / "daten"
OSM = DATEN / "dortmund-wege.osm.pbf"
GTFS = DATEN / "dortmund-gtfs.zip"
STAND = DATEN / "stand.json"
MERKZETTEL = ORDNER / "import_stand.json"            # womit zuletzt importiert wurde
RECHNER = "127.0.0.1"   # nur vom eigenen Rechner erreichbar, so fragt die Firewall nicht
PORT = 8080


# ---------------------------------------------------------------- Programm laden

def archiv_fuer_plattform():
    """Liefert (Dateiname, Prüfsumme) des MOTIS-Archivs für dieses Betriebssystem."""
    system = platform.system()
    maschine = platform.machine().lower()
    bauart = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(maschine)
    if system == "Windows":
        bauart = "amd64"   # Windows auf ARM führt das x64-Programm in der Emulation aus
    if (system, bauart) not in ARCHIVE:
        raise SystemExit(
            f"Für {system} ({maschine}) gibt es kein fertiges MOTIS {VERSION}.\n"
            "Verfügbar: Windows (x64), Linux (x64, ARM), macOS (Apple Silicon).\n"
            "Auf einem Intel-Mac können Sie MOTIS in einer Linux-Umgebung nutzen oder\n"
            "in Ihrer Gruppe einen anderen Rechner verwenden.")
    return ARCHIVE[(system, bauart)]


def programmpfad(ordner: Path = ORDNER) -> Path:
    return ordner / ("motis.exe" if platform.system() == "Windows" else "motis")


def pruefsumme(datei: Path) -> str:
    summe = hashlib.sha256()
    with open(datei, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            summe.update(block)
    return summe.hexdigest()


def herunterladen(adresse: str, ziel: Path):
    """Lädt eine Datei mit Fortschrittsanzeige; erst nach dem Ende erhält sie ihren Namen."""
    teil = ziel.with_name(ziel.name + ".teil")
    anfrage = urllib.request.Request(adresse, headers={"User-Agent": "python-urllib"})
    with urllib.request.urlopen(anfrage, timeout=60) as antwort, open(teil, "wb") as f:
        gesamt = int(antwort.headers.get("Content-Length") or 0)
        geladen, naechste_meldung = 0, 0
        while block := antwort.read(1 << 20):
            f.write(block)
            geladen += len(block)
            if geladen >= naechste_meldung:
                von = f" von {gesamt / 1e6:.0f}" if gesamt else ""
                print(f"  {geladen / 1e6:5.0f}{von} MB", flush=True)
                naechste_meldung += 10_000_000
    teil.replace(ziel)


def motis_laden(ordner: Path = ORDNER) -> Path:
    """Lädt und entpackt MOTIS, falls das Programm noch fehlt. Liefert den Programmpfad."""
    programm = programmpfad(ordner)
    marke = ordner / "version.txt"
    if programm.exists() and marke.exists() and marke.read_text(encoding="utf-8").strip() == VERSION:
        print(f"MOTIS {VERSION} ist vorhanden: {programm}")
        return programm

    name, soll = archiv_fuer_plattform()
    ordner.mkdir(parents=True, exist_ok=True)
    archiv = ordner / name
    if not (archiv.exists() and pruefsumme(archiv) == soll):
        print(f"Lade {ADRESSE}{name} (etwa 50 MB) ...")
        t0 = time.time()
        herunterladen(ADRESSE + name, archiv)
        print(f"  fertig nach {time.time() - t0:.0f} s")
        if pruefsumme(archiv) != soll:
            archiv.unlink()
            raise SystemExit("Die Prüfsumme des geladenen Archivs stimmt nicht. Bitte erneut "
                             "versuchen; bleibt der Fehler, wenden Sie sich an die Betreuung.")

    print(f"Entpacke {name} ...")
    if name.endswith(".zip"):
        with zipfile.ZipFile(archiv) as z:
            z.extractall(ordner)
    else:
        with tarfile.open(archiv, "r:bz2") as t:
            try:
                t.extractall(ordner, filter="data")   # sichere Voreinstellung neuerer Pythons
            except TypeError:
                t.extractall(ordner)
    if not programm.exists():
        raise SystemExit(f"Im Archiv fehlt das Programm {programm.name}.")
    if platform.system() != "Windows":
        programm.chmod(0o755)
    marke.write_text(VERSION + "\n", encoding="utf-8")
    archiv.unlink()   # wird nicht mehr gebraucht
    return programm


# ---------------------------------------------------------------- Konfiguration

def fahrplan_zeitraum(stand: Path = STAND, gtfs: Path = GTFS):
    """Erster und letzter Tag des Fahrplans als date.

    Steht in daten/stand.json; fehlt die Datei (oder ist `stand` None), wird im GTFS-Paket
    nachgesehen (calendar.txt und calendar_dates.txt).
    """
    def tag(text):
        return datetime.strptime(text, "%Y%m%d").date()

    if stand is not None and stand.exists():
        g = json.loads(stand.read_text(encoding="utf-8"))["gtfs"]
        return tag(g["gueltig_von"]), tag(g["gueltig_bis"])

    tage = []
    with zipfile.ZipFile(gtfs) as z:
        for name, spalten in (("calendar.txt", ("start_date", "end_date")),
                              ("calendar_dates.txt", ("date",))):
            if name not in z.namelist():
                continue
            with z.open(name) as f:
                for zeile in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
                    tage.extend(zeile[s] for s in spalten if zeile.get(s))
    if not tage:
        raise SystemExit(f"In {gtfs.name} stehen keine Betriebstage (calendar.txt fehlt).")
    return tag(min(tage)), tag(max(tage))


def yaml_setzen(text: str, abschnitt: str, schluessel: str, wert) -> str:
    """Setzt in einer einfachen YAML-Datei `abschnitt: schluessel: wert`.

    Reicht für die config.yml von MOTIS (Abschnitte ohne Einrückung, Einträge mit zwei
    Leerzeichen) und spart das Paket PyYAML. Vorhandene Einträge werden ersetzt, fehlende
    hinter der Überschrift des Abschnitts eingefügt; fehlt der Abschnitt, wird er angehängt.
    """
    zeilen = text.splitlines()
    neu = f"  {schluessel}: {wert}"
    try:
        start = next(i for i, z in enumerate(zeilen) if z.split("#")[0].rstrip() == f"{abschnitt}:")
    except StopIteration:
        return "\n".join(zeilen + [f"{abschnitt}:", neu]) + "\n"
    for i in range(start + 1, len(zeilen)):
        if zeilen[i].strip() and not zeilen[i].startswith(" "):
            break   # nächster Abschnitt
        if zeilen[i].startswith(f"  {schluessel}:"):
            zeilen[i] = neu
            break
    else:
        i = len(zeilen)
    if i == len(zeilen) or zeilen[i] != neu:
        zeilen.insert(start + 1, neu)
    return "\n".join(zeilen) + "\n"


def konfiguration_schreiben(programm: Path, von: date, bis: date, ordner: Path = ORDNER):
    """Erzeugt config.yml mit `motis config` und passt Zeitraum und Serveradresse an."""
    # Pfade relativ zum Ordner motis/: unabhängig von Leerzeichen oder Umlauten im Benutzernamen
    osm = Path(os.path.relpath(OSM, ordner)).as_posix()
    gtfs = Path(os.path.relpath(GTFS, ordner)).as_posix()
    subprocess.run([str(programm), "config", osm, gtfs], cwd=ordner, check=True)

    datei = ordner / "config.yml"
    text = datei.read_text(encoding="utf-8")
    tage = (bis - von).days + 1
    # Voreinstellung ist first_day: TODAY – dann gäbe es für vergangene Tage keine Auskunft.
    text = yaml_setzen(text, "timetable", "num_days", tage)
    text = yaml_setzen(text, "timetable", "first_day", von.isoformat())
    text = yaml_setzen(text, "server", "port", PORT)
    text = yaml_setzen(text, "server", "host", RECHNER)
    datei.write_text(text, encoding="utf-8", newline="\n")
    print(f"config.yml: Fahrplan {von:%d.%m.%Y} bis {bis:%d.%m.%Y} ({tage} Tage), "
          f"Server nur auf {RECHNER}:{PORT}")
    return von, tage


# ---------------------------------------------------------------- Import

def daten_stand(von: date, tage: int) -> dict:
    """Beschreibt, womit importiert wird: Version, Zeitraum, Größe und Änderungszeit der Daten."""
    dateien = {p.name: {"groesse": p.stat().st_size, "geaendert": int(p.stat().st_mtime)}
               for p in (OSM, GTFS)}
    return {"motis": VERSION, "first_day": von.isoformat(), "num_days": tage, "dateien": dateien}


def importieren(programm: Path, ordner: Path = ORDNER, neu: bool = False):
    """Führt `motis import` aus, wenn sich die Daten seit dem letzten Import geändert haben."""
    fehlend = [p for p in (OSM, GTFS) if not p.exists()]
    if fehlend:
        raise SystemExit("Es fehlen Daten: " + ", ".join(p.name for p in fehlend) +
                         f"\nBitte zuerst die Daten in den Ordner {DATEN} laden.")
    von, bis = fahrplan_zeitraum()
    tage = (bis - von).days + 1
    stand = daten_stand(von, tage)
    if not neu and MERKZETTEL.exists() and (ordner / "data").is_dir() and (ordner / "config.yml").exists():
        if json.loads(MERKZETTEL.read_text(encoding="utf-8")) == stand:
            print("Import ist aktuell (Daten unverändert).")
            return

    konfiguration_schreiben(programm, von, bis, ordner)
    MERKZETTEL.unlink(missing_ok=True)
    print("Importiere Fahrplan und Straßennetz (etwa eine Minute, gut 1 GB Arbeitsspeicher) ...")
    t0 = time.time()
    subprocess.run([str(programm), "import"], cwd=ordner, check=True)
    print(f"Import fertig nach {time.time() - t0:.0f} s")
    MERKZETTEL.write_text(json.dumps(stand, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- Server

def port_belegt(rechner: str = RECHNER, port: int = PORT) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex((rechner, port)) == 0


def server_starten(programm: Path, ordner: Path = ORDNER):
    """Startet `motis server` und kehrt erst zurück, wenn der Server beendet wird."""
    if port_belegt():
        raise SystemExit(f"Auf Port {PORT} läuft schon ein Programm – vermutlich ein MOTIS-Server "
                         "in einem anderen Fenster. Dann können Sie direkt weiterarbeiten.")
    print(f"Starte den Server: http://localhost:{PORT}  (beenden mit Strg+C)")
    try:
        ergebnis = subprocess.run([str(programm), "server"], cwd=ordner)
    except KeyboardInterrupt:
        print("\nServer beendet.")
        return
    if ergebnis.returncode != 0:
        print(f"Der Server wurde beendet (Rückgabewert {ergebnis.returncode}).")


def main():
    parser = argparse.ArgumentParser(description="MOTIS laden, Daten importieren, Server starten")
    parser.add_argument("--server", action="store_true", help="nach dem Einrichten den Server starten")
    parser.add_argument("--neu", action="store_true", help="Import erzwingen, auch wenn die Daten unverändert sind")
    args = parser.parse_args()

    programm = motis_laden()
    importieren(programm, neu=args.neu)
    if args.server:
        server_starten(programm)
    else:
        print("Fertig. Server starten mit: python nahverkehr/motis_einrichten.py --server")


if __name__ == "__main__":
    main()
