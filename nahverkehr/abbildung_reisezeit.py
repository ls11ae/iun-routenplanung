"""Abbildung für die Folien: Wo verliert der Nahverkehr gegen das Auto?

Liest webdemo/daten/reisezeiten.json (aus reisezeitkarte.py) und zeichnet das Verhältnis
der Reisezeit mit Bus und Bahn zur Autozeit als Rasterkarte, einmal mit der reinen
Fahrzeit und einmal mit einem Zuschlag für Parkplatzsuche und Fußweg.

Aufruf im Wurzelverzeichnis:  python nahverkehr/abbildung_reisezeit.py [--zuschlag 5]
Ergebnis: abbildungen/oepnv-auto-campus-nord.svg und .png
"""

import argparse
import json
import math
import statistics
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

WURZEL = Path(__file__).resolve().parent.parent
GRENZEN = [2, 3, 4, 5]
# eine Farbe von hell nach dunkel (wie in der Webdemo): Die Helligkeit trägt die Reihenfolge
RAMPE = ["#eff3ff", "#bdd7e7", "#6baed6", "#2f7fbf", "#08488f"]
NAMEN = ["höchstens 2-mal", "2- bis 3-mal", "3- bis 4-mal", "4- bis 5-mal", "mehr als 5-mal"]
TINTE, LEISE = "#1b1b1b", "#555555"
ORTE = {"Innenstadt": (51.514, 7.465), "Hörde": (51.488, 7.503), "Aplerbeck": (51.492, 7.557),
        "Mengede": (51.575, 7.385), "Eving": (51.551, 7.471), "Scharnhorst": (51.548, 7.540),
        "Brackel": (51.524, 7.546), "Hombruch": (51.466, 7.447), "Lütgendortmund": (51.500, 7.347),
        "Huckarde": (51.536, 7.410)}


def ringe(geometrie):
    polygone = geometrie["coordinates"] if geometrie["type"] == "MultiPolygon" else [geometrie["coordinates"]]
    for polygon in polygone:
        yield from polygon


def karte(ax, D, zuschlag, titel):
    Z, (dx, dy) = D["zellen"], D["zelle_grad"]
    anzahl, werte = [0] * 5, []
    for lat, lon, oepnv, auto in zip(Z["lat"], Z["lon"], Z["oepnv_min"], Z["auto_min"]):
        ecke = (lon - dx / 2, lat - dy / 2)
        if oepnv is None or auto is None:
            ax.add_patch(Rectangle(ecke, dx, dy, facecolor="#dddddd", edgecolor="#888888", hatch="////", linewidth=0))
            continue
        v = oepnv / (auto + zuschlag)
        k = sum(v > g for g in GRENZEN)
        anzahl[k] += 1
        werte.append(v)
        ax.add_patch(Rectangle(ecke, dx, dy, facecolor=RAMPE[k], edgecolor="white", linewidth=0.3))
    for ring in ringe(D["grenze"]):
        ax.plot([p[0] for p in ring], [p[1] for p in ring], color=TINTE, linewidth=1.4)
    for name, (lat, lon) in ORTE.items():
        ax.annotate(name, (lon, lat), ha="center", va="center", fontsize=9, color=TINTE,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.75))
    z = D["ziel"]
    ax.plot(z["lon"], z["lat"], marker="s", markersize=11, markerfacecolor="white", markeredgecolor=TINTE, markeredgewidth=2)
    ax.annotate("Campus Nord", (z["lon"], z["lat"]), xytext=(0, -15), textcoords="offset points", ha="center",
                va="top", fontsize=10, fontweight="bold", color=TINTE,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85))
    ax.set_aspect(1 / math.cos(math.radians(z["lat"])))
    ax.autoscale_view()
    ax.axis("off")
    median = statistics.median(werte)
    ax.set_title(f"{titel}\nMedian: {median:.1f}-mal so lange".replace(".", ","), fontsize=13, color=TINTE, loc="left")
    return anzahl


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--zuschlag", type=float, default=5, help="Minuten für Parkplatzsuche und Fußweg")
    p.add_argument("--daten", type=Path, default=WURZEL / "webdemo" / "daten" / "reisezeiten.json")
    p.add_argument("--ziel", type=Path, default=WURZEL / "abbildungen")
    a = p.parse_args()
    D = json.loads(a.daten.read_text(encoding="utf-8"))
    zeit = datetime.fromisoformat(D["zeitpunkt"])

    plt.switch_backend("Agg")                 # ohne Fenster zeichnen
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none", "hatch.linewidth": 0.5,
                         "hatch.color": "#888888"})
    fig, achsen = plt.subplots(1, 2, figsize=(13, 6.6))
    karte(achsen[0], D, 0, "Auto: reine Fahrzeit")
    karte(achsen[1], D, a.zuschlag, f"Auto: Fahrzeit + {a.zuschlag:g} min für Parken und Fußweg")
    legende = [Patch(facecolor=f, edgecolor="#777777", label=n) for f, n in zip(RAMPE, NAMEN)]
    legende.append(Patch(facecolor="#dddddd", edgecolor="#888888", hatch="////", label="kein Wert"))
    fig.legend(handles=legende, title="Bus und Bahn brauchen … so lange wie das Auto", loc="lower center",
               ncol=6, frameon=False, fontsize=10, title_fontsize=11, bbox_to_anchor=(0.5, 0.055))
    fig.suptitle(f"Wo verliert der Nahverkehr gegen das Auto? Reisezeit zum Campus Nord, "
                 f"Dienstag, {zeit:%d.%m.%Y}, Start {zeit:%H:%M} Uhr", fontsize=15, color=TINTE, x=0.02, ha="left")
    fig.text(0.02, 0.012, f"Raster {D['raster_m']} m über das Stadtgebiet Dortmund. Bus und Bahn: früheste Ankunft bei Start um "
             f"{zeit:%H:%M} Uhr, mit Fußwegen und Wartezeit. Auto: Fahrzeit nach OpenStreetMap ohne Stau.\n"
             f"Berechnet mit {D['werkzeug']}. Fahrplan: gtfs.de / DELFI e.V. (CC BY 4.0). "
             "Karte: © OpenStreetMap-Mitwirkende (ODbL).", fontsize=8.5, color=LEISE, va="bottom")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.86, bottom=0.14, wspace=0.02)
    a.ziel.mkdir(parents=True, exist_ok=True)
    for endung in ("svg", "png"):
        datei = a.ziel / f"oepnv-auto-campus-nord.{endung}"
        fig.savefig(datei, dpi=200, facecolor="white")
        print(datei, f"({datei.stat().st_size / 1e3:.0f} kB)")
