"""Abbildung für die Folien: Wo verliert der Nahverkehr gegen das Auto?

Liest webdemo/daten/reisezeiten.json (aus reisezeitkarte.py) und zeichnet das Verhältnis
der Reisezeit mit Bus und Bahn zur Autozeit (mit Zuschlag für Parken und Fußweg) als
Rasterkarte. Zellen in Gehweite zum Campus und Zellen ohne Haltestelle in Gehweite sind
eigene Kategorien. Die Annahmen stehen als Legende neben der Karte.

Aufruf im Wurzelverzeichnis:  python nahverkehr/abbildung_reisezeit.py [--zuschlag 5]
Ergebnis: abbildungen/oepnv-auto-campus-nord.svg und .png
"""

import argparse
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reisezeitkarte import kategorie  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent
GRUNDKARTE = WURZEL / "webdemo" / "daten" / "grundkarte.json"
# eine Farbe von hell nach dunkel (wie in der Webdemo): Die Helligkeit trägt die Reihenfolge
RAMPE = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]
# Sonderfälle: eigene Farbe UND eigene Schraffur
SONDER = {
    "campus": dict(facecolor="#7fcdb6", edgecolor="#00513b", hatch="...", linewidth=0.6),
    "kein_halt": dict(facecolor="#c8c8c4", edgecolor="#3d3d3a", hatch="////", linewidth=0.4),
    "kein_wert": dict(facecolor="#ffffff", edgecolor="#8a8a86", hatch="xx", linewidth=0.4),
}
TINTE, LEISE = "#1b1b1b", "#555555"
ORTE = {"Innenstadt": (51.514, 7.465), "Hörde": (51.488, 7.503), "Aplerbeck": (51.492, 7.557),
        "Mengede": (51.575, 7.385), "Eving": (51.551, 7.471), "Scharnhorst": (51.548, 7.540),
        "Brackel": (51.524, 7.546), "Hombruch": (51.466, 7.447), "Lütgendortmund": (51.500, 7.347),
        "Huckarde": (51.536, 7.410)}


def zahl(x, stellen=1):
    return f"{x:.{stellen}f}".replace(".", ",")


def klassennamen(grenzen):
    """„höchstens 2,5-mal“, „2,5- bis 3-mal“, …, „mehr als 4-mal“ (Komma, ohne „,0“)."""
    g = [zahl(x).replace(",0", "") for x in grenzen]
    return ([f"höchstens {g[0]}-mal"] + [f"{a}- bis {b}-mal" for a, b in zip(g, g[1:])]
            + [f"mehr als {g[-1]}-mal"])


def sondernamen(P):
    return {"campus": f"Campus zu Fuß in höchstens {P['campus_fuss_max_min']} min",
            "kein_halt": f"keine Haltestelle (Abfahrt 7–9 Uhr)\nim Umkreis von {zahl(P['halt_max_m'] / 1000).replace(',0', '')} km",
            "kein_wert": "kein Wert (kein Weg in der Nähe\noder keine Verbindung)"}


def ringe(geometrie):
    polygone = geometrie["coordinates"] if geometrie["type"] == "MultiPolygon" else [geometrie["coordinates"]]
    for polygon in polygone:
        yield from polygon


def linien(geometrie):
    if geometrie["type"] == "LineString":
        yield geometrie["coordinates"]
    elif geometrie["type"] == "MultiLineString":
        yield from geometrie["coordinates"]


def karte(ax, D, zuschlag):
    """Zeichnet das Raster; gibt (Anzahl je Kategorie, Verhältnisse) zurück."""
    Z, (dx, dy), P = D["zellen"], D["zelle_grad"], D["darstellung"]
    grenzen = P["verhaeltnis_grenzen"]
    anzahl, werte = {}, []
    for i, (lat, lon) in enumerate(zip(Z["lat"], Z["lon"])):
        k = kategorie(Z, i, zuschlag, P["halt_max_m"], P["campus_fuss_max_min"], grenzen)
        anzahl[k] = anzahl.get(k, 0) + 1
        ecke = (lon - dx / 2, lat - dy / 2)
        if isinstance(k, int):
            werte.append(Z["oepnv_min"][i] / (Z["auto_min"][i] + zuschlag))
            ax.add_patch(Rectangle(ecke, dx, dy, facecolor=RAMPE[k], edgecolor="white", linewidth=0.3))
        else:
            ax.add_patch(Rectangle(ecke, dx, dy, **SONDER[k]))
    # Orientierung: Autobahnen, Bahnstrecken und Flüsse aus der Grundkarte, dünn darüber
    if GRUNDKARTE.exists():
        g = json.loads(GRUNDKARTE.read_text(encoding="utf-8"))
        stil = {"autobahn": dict(color="#2b2b2b", linewidth=0.9, alpha=0.6),
                "bahn": dict(color="#2b2b2b", linewidth=0.6, alpha=0.6, linestyle=(0, (4, 2))),
                "fluss": dict(color="#1f6fb2", linewidth=0.8, alpha=0.7)}
        for f in g["features"]:
            k = f["properties"]["k"]
            if k in stil:
                for linie in linien(f["geometry"]):
                    ax.plot([p[0] for p in linie], [p[1] for p in linie], **stil[k], zorder=3)
    for ring in ringe(D["grenze"]):
        ax.plot([p[0] for p in ring], [p[1] for p in ring], color=TINTE, linewidth=1.4, zorder=4)
    for name, (lat, lon) in ORTE.items():
        ax.annotate(name, (lon, lat), ha="center", va="center", fontsize=9, color=TINTE, zorder=5,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.8))
    z = D["ziel"]
    ax.plot(z["lon"], z["lat"], marker="s", markersize=11, markerfacecolor="white", markeredgecolor=TINTE,
            markeredgewidth=2, zorder=6)
    ax.annotate("Campus Nord", (z["lon"], z["lat"]), xytext=(0, -15), textcoords="offset points", ha="center",
                va="top", fontsize=10, fontweight="bold", color=TINTE, zorder=6,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85))
    ax.set_aspect(1 / math.cos(math.radians(z["lat"])))
    xs = [p[0] for r in ringe(D["grenze"]) for p in r]
    ys = [p[1] for r in ringe(D["grenze"]) for p in r]
    ax.set_xlim(min(xs) - 0.01, max(xs) + 0.01)
    ax.set_ylim(min(ys) - 0.006, max(ys) + 0.006)
    ax.axis("off")
    return anzahl, werte


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--zuschlag", type=float, help="Minuten für Parkplatzsuche und Fußweg (Standard aus den Daten)")
    p.add_argument("--daten", type=Path, default=WURZEL / "webdemo" / "daten" / "reisezeiten.json")
    p.add_argument("--ziel", type=Path, default=WURZEL / "abbildungen")
    a = p.parse_args()
    D = json.loads(a.daten.read_text(encoding="utf-8"))
    P, A = D["darstellung"], D["abfahrten"]
    zuschlag = P["zuschlag_min"] if a.zuschlag is None else a.zuschlag
    von, bis = datetime.fromisoformat(A["von"]), datetime.fromisoformat(A["bis"])

    plt.switch_backend("Agg")                 # ohne Fenster zeichnen
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none", "hatch.linewidth": 0.5,
                         "svg.hashsalt": "iun-reisezeit"})
    fig = plt.figure(figsize=(13, 7.4))
    ax = fig.add_axes([0.0, 0.02, 0.64, 0.84])
    anzahl, werte = karte(ax, D, zuschlag)
    ohne = [D["zellen"]["oepnv_min"][i] / D["zellen"]["auto_min"][i] for i in range(len(D["zellen"]["lat"]))
            if isinstance(kategorie(D["zellen"], i, 0, P["halt_max_m"], P["campus_fuss_max_min"],
                                    P["verhaeltnis_grenzen"]), int)]
    mit = len(werte)

    fig.text(0.015, 0.955, "Wo verliert der Nahverkehr gegen das Auto?", fontsize=17, color=TINTE, fontweight="bold")
    fig.text(0.015, 0.905, f"Reisezeit zum Campus Nord: Bus und Bahn im Verhältnis zum Auto (+ {zuschlag:g} min für Parken). "
             f"Median: {zahl(statistics.median(werte))}-mal so lange", fontsize=12.5, color=TINTE)

    # Legende mit Klassen, Sonderfällen und Annahmen rechts neben der Karte
    lx = 0.655
    namen = klassennamen(P["verhaeltnis_grenzen"])
    eintraege = [Patch(facecolor=f, edgecolor="#777777", label=f"{n}  ({zahl(100 * anzahl.get(k, 0) / mit, 0)} %)")
                 for k, (f, n) in enumerate(zip(RAMPE, namen))]
    sonder = sondernamen(P)
    eintraege += [Patch(**SONDER[k], label=f"{sonder[k]}  ({anzahl.get(k, 0)} Zellen)") for k in SONDER]
    fig.legend(handles=eintraege, loc="upper left", bbox_to_anchor=(lx, 0.86), frameon=False, fontsize=10.5,
               title=f"Bus und Bahn brauchen … so lange\nwie das Auto (Anteil der {mit} Zellen)",
               title_fontsize=11, alignment="left", handlelength=2.4, handleheight=1.4, labelspacing=0.7)
    annahmen = [
        f"Bus und Bahn: Median über {A['anzahl']} Abfahrten von {von:%H:%M} bis {bis:%H:%M} Uhr "
        f"(alle {A['schritt_min']} min), Tür zu Tür, Wartezeit zählt mit; Dienstag, {von:%d.%m.%Y}.",
        f"Auto: Fahrzeit nach OpenStreetMap ohne Stau + {zuschlag:g} min für Parken und Fußweg. "
        f"Ohne Zuschlag: Median {zahl(statistics.median(ohne))}-mal.",
        f"Gehweite: Haltestelle höchstens {zahl(P['halt_max_m'] / 1000).replace(',0', '')} km Luftlinie, "
        f"Campus höchstens {P['campus_fuss_max_min']} min zu Fuß.",
        f"Start in der Mitte jeder Rasterzelle ({D['raster_m']} m); Fahrplan nach Plan, ohne Verspätungen.",
    ]
    import textwrap
    text = "\n".join("• " + "\n   ".join(textwrap.wrap(s, 52)) for s in annahmen)
    fig.text(lx + 0.004, 0.39, "Annahmen", fontsize=11, fontweight="bold", color=TINTE, va="top")
    fig.text(lx + 0.004, 0.36, text, fontsize=9.3, color=TINTE, va="top", linespacing=1.35)
    fig.text(lx + 0.004, 0.03, f"Berechnet mit {D['werkzeug']}. Fahrplan: gtfs.de / DELFI e.V. (CC BY 4.0).\n"
             "Karte und Wege: © OpenStreetMap-Mitwirkende (ODbL).", fontsize=8, color=LEISE, va="bottom")

    a.ziel.mkdir(parents=True, exist_ok=True)
    for endung in ("svg", "png"):
        datei = a.ziel / f"oepnv-auto-campus-nord.{endung}"
        fig.savefig(datei, dpi=200, facecolor="white", metadata={"Date": None} if endung == "svg" else None)
        print(datei, f"({datei.stat().st_size / 1e3:.0f} kB)")
    print(f"Zuschlag {zuschlag:g} min: Median {statistics.median(werte):.2f} über {mit} Zellen; ohne Zuschlag "
          f"{statistics.median(ohne):.2f}; Anteile {[round(100 * anzahl.get(k, 0) / mit) for k in range(len(RAMPE))]} %; "
          f"Sonderfälle {[(k, anzahl.get(k, 0)) for k in SONDER]}")
