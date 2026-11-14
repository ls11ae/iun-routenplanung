"""Packt die erzeugten Daten zu einem Paket für ein GitHub-Release (für Lehrende).

Aufruf im Wurzelverzeichnis, nach daten/daten_vorbereiten.py:

    python daten/paket_bauen.py --name daten-2026-11

Schreibt daten/<name>.zip und trägt Name, Adresse, Größe und Prüfsumme in
daten/paket.json ein. Danach:
1. auf GitHub ein Release mit dem Tag <name> anlegen und die Zip-Datei anhängen,
2. daten/paket.json committen und pushen.
Studierende holen das Paket dann mit daten/herunterladen.py.
"""

import argparse
import json
import zipfile
from pathlib import Path

from herunterladen import pruefsumme

ORDNER = Path(__file__).resolve().parent
DATEIEN = ["dortmund-gtfs.zip", "dortmund-wege.osm.pbf", "dortmund-sued-wege.osm.bz2",
           "dortmund-sued-hoehen.tif", "dortmund-grenze.geojson", "stand.json"]
ADRESSE = "https://github.com/ls11ae/iun-routenplanung/releases/download/{name}/{name}.zip"

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--name", required=True, help="Name des Pakets und des Release-Tags, z. B. daten-2026-11")
    a = p.parse_args()

    fehlend = [d for d in DATEIEN if not (ORDNER / d).exists()]
    if fehlend:
        raise SystemExit(f"Es fehlen: {', '.join(fehlend)} (zuerst daten_vorbereiten.py ausführen)")
    stand = json.loads((ORDNER / "stand.json").read_text(encoding="utf-8"))
    stand.pop("paket", None)
    ziel = ORDNER / f"{a.name}.zip"
    # Die Dateien sind schon gepackt; ZIP_STORED hält das Paket zwischen zwei Läufen gleich
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_STORED) as z:
        for d in DATEIEN:
            if d == "stand.json":
                info = zipfile.ZipInfo(d, date_time=(2026, 1, 1, 0, 0, 0))
                z.writestr(info, json.dumps(stand, ensure_ascii=False, indent=2) + "\n")
            else:
                z.write(ORDNER / d, d)
    paket = {"name": ziel.name, "url": ADRESSE.format(name=a.name),
             "groesse": ziel.stat().st_size, "sha256": pruefsumme(ziel),
             "dateien": DATEIEN, "stand": stand}
    (ORDNER / "paket.json").write_text(json.dumps(paket, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
    print(f"{ziel} ({ziel.stat().st_size / 1e6:.1f} MB)\nSHA-256: {paket['sha256']}\n"
          f"Jetzt ein Release mit dem Tag {a.name} anlegen, die Zip-Datei anhängen "
          "und daten/paket.json committen.")
