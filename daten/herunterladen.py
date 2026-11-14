"""Lädt das Datenpaket für die Python-Starter herunter und prüft es.

Aufruf im Wurzelverzeichnis des Repositorys:

    python daten/herunterladen.py

Das Paket (etwa 45 MB) enthält den Fahrplan, die OSM-Auszüge und die Höhen für Dortmund.
Welche Datei geladen wird und welche Prüfsumme sie haben muss, steht in daten/paket.json.
Der Fahrplan gilt nur etwa einen Monat; nach `git pull` holt dieses Skript ein neueres
Paket, sobald es eines gibt.

Ohne Internet: Paket von jemandem kopieren und mit --datei angeben:

    python daten/herunterladen.py --datei pfad/zu/daten-2026-11.zip

Braucht nur die Python-Standardbibliothek.
"""

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

ORDNER = Path(__file__).resolve().parent


def pruefsumme(datei: Path) -> str:
    h = hashlib.sha256()
    with open(datei, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def laden(url: str, ziel: Path):
    """Lädt `url` nach `ziel` und zeigt den Fortschritt."""
    teil = ziel.with_suffix(".teil")
    with urllib.request.urlopen(url, timeout=60) as antwort, open(teil, "wb") as aus:
        gesamt = int(antwort.headers.get("Content-Length") or 0)
        fertig = 0
        while block := antwort.read(1 << 18):
            aus.write(block)
            fertig += len(block)
            if gesamt:
                print(f"\r  {fertig / 1e6:5.1f} von {gesamt / 1e6:.1f} MB", end="", flush=True)
    print()
    teil.replace(ziel)


def hauptprogramm():
    p = argparse.ArgumentParser(description="Datenpaket herunterladen und prüfen")
    p.add_argument("--datei", type=Path, help="schon vorhandenes Paket benutzen (ohne Internet)")
    p.add_argument("--neu", action="store_true", help="auch laden, wenn die Daten schon da sind")
    a = p.parse_args()

    paket = json.loads((ORDNER / "paket.json").read_text(encoding="utf-8"))
    stand_datei = ORDNER / "stand.json"
    if stand_datei.exists() and not a.neu and not a.datei:
        stand = json.loads(stand_datei.read_text(encoding="utf-8"))
        vorhanden = all((ORDNER / name).exists() for name in paket["dateien"])
        if vorhanden and stand.get("paket") == paket["name"]:
            print(f"Das Datenpaket {paket['name']} ist schon vorhanden.")
            return hinweis_fahrplan(stand)

    zip_datei = a.datei or ORDNER / paket["name"]
    if not a.datei:
        print(f"Lade {paket['name']} ({paket['groesse'] / 1e6:.0f} MB) von\n  {paket['url']}")
        try:
            laden(paket["url"], zip_datei)
        except OSError as fehler:
            sys.exit(f"Der Download ist fehlgeschlagen ({fehler}).\n"
                     "Prüfen Sie die Internetverbindung oder laden Sie die Datei im Browser "
                     "und rufen Sie das Skript mit --datei auf.")
    if pruefsumme(zip_datei) != paket["sha256"]:
        sys.exit(f"Die Prüfsumme von {zip_datei.name} stimmt nicht. Die Datei ist unvollständig "
                 "oder gehört zu einem anderen Stand (dann hilft: git pull). Bitte neu laden.")
    with zipfile.ZipFile(zip_datei) as z:
        for name in z.namelist():
            if Path(name).name != name:               # nur Dateien ohne Unterordner auspacken
                sys.exit(f"Unerwarteter Pfad im Paket: {name}")
        z.extractall(ORDNER)
    stand = json.loads(stand_datei.read_text(encoding="utf-8"))
    stand["paket"] = paket["name"]
    stand_datei.write_text(json.dumps(stand, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not a.datei:
        zip_datei.unlink()
    print(f"Fertig: {len(paket['dateien'])} Dateien in {ORDNER}")
    hinweis_fahrplan(stand)


def hinweis_fahrplan(stand):
    g = stand.get("gtfs", {})
    if not g:
        return
    von, bis = (datetime.strptime(g[k], "%Y%m%d").date() for k in ("gueltig_von", "gueltig_bis"))
    print(f"Fahrplan gültig vom {von:%d.%m.%Y} bis {bis:%d.%m.%Y}.")
    if date.today() > bis:
        print("Achtung: Der Fahrplan ist abgelaufen. Holen Sie mit `git pull` den neuen Stand "
              "und rufen Sie dieses Skript erneut auf.")


if __name__ == "__main__":
    hauptprogramm()
