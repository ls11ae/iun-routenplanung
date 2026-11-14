"""Die Webdemo lädt nichts von fremden Servern, und ihre Daten passen zusammen."""

import json
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "webdemo"
FREMD = re.compile(r"^(https?:|wss?:)?//", re.I)


def test_keine_fremden_ladequellen():
    """Skripte, Stylesheets, Bilder, Daten und Kartenkacheln kommen nur aus webdemo/.
    Links (<a href>) auf andere Seiten sind erlaubt: Sie laden nichts, solange niemand klickt."""
    fehler = []
    for html in WEB.glob("*.html"):
        s = html.read_text(encoding="utf-8")
        for tag, attr in [("script", "src"), ("link", "href"), ("img", "src"), ("iframe", "src"),
                          ("source", "src"), ("video", "src"), ("audio", "src"), ("embed", "src"),
                          ("object", "data")]:
            for m in re.finditer(rf"<{tag}\b[^>]*?\b{attr}\s*=\s*[\"']([^\"']+)", s, re.I):
                if FREMD.match(m.group(1)):
                    fehler.append(f"{html.name}: <{tag} {attr}={m.group(1)}>")
    for css in WEB.rglob("*.css"):
        for m in re.finditer(r"(?:url\(|@import\s+)\s*[\"']?([^\"')\s;]+)", css.read_text(encoding="utf-8")):
            if FREMD.match(m.group(1)):
                fehler.append(f"{css.relative_to(WEB)}: {m.group(0)}")
    for js in (WEB / "js").glob("*.js"):
        s = js.read_text(encoding="utf-8")
        if re.search(r"tileLayer|TileLayer", s):
            fehler.append(f"js/{js.name}: Kartenkacheln (tileLayer)")
        for m in re.finditer(r"(?:fetch|importScripts|Worker|WebSocket|EventSource)\(\s*[\"'`]([^\"'`]+)", s):
            if FREMD.match(m.group(1)):
                fehler.append(f"js/{js.name}: {m.group(0)}")
        for m in re.finditer(r"[\"'`(]((?:https?:)?//[^\"'`\s)]+\.(?:png|jpe?g|gif|svg|webp|js|mjs|css|json|woff2?|ttf|gz|pbf))\b", s, re.I):
            fehler.append(f"js/{js.name}: {m.group(1)}")
    assert not fehler, "Fremde Ladequellen:\n" + "\n".join(fehler)


def test_reisezeiten_passen_zusammen():
    datei = WEB / "daten" / "reisezeiten.json"
    if not datei.exists():
        pytest.skip("webdemo/daten/reisezeiten.json fehlt")
    D = json.loads(datei.read_text(encoding="utf-8"))
    Z = D["zellen"]
    laengen = {k: len(v) for k, v in Z.items()}
    assert len(set(laengen.values())) == 1, laengen
    for k in ["oepnv_min", "oepnv_dauer_min", "umstiege", "zum_halt_min", "halt_m", "auto_min", "rad_min", "fuss_min"]:
        assert k in Z, k
    P = D["darstellung"]
    assert P["verhaeltnis_grenzen"] == sorted(P["verhaeltnis_grenzen"])
    assert P["verhaeltnis_grenzen"][-1] == 4          # ab 4 zusammengefasst
    assert D["abfahrten"]["anzahl"] >= 2
    # Reisezeiten über drei Stunden gelten als keine Verbindung
    assert all(v is None or v <= 180 for v in Z["oepnv_min"])
    # Mit Zuschlag ist das Auto nie schneller als „gar keine Zeit“: alle Verhältnisse positiv
    assert all(o is None or a is None or o / (a + P["zuschlag_min"]) > 0 for o, a in zip(Z["oepnv_min"], Z["auto_min"]))


def test_daten_der_webdemo_klein_genug():
    """Pages liefert alles aus webdemo/ aus; die Seite soll auch mobil schnell laden."""
    groessen = {p.name: p.stat().st_size for p in (WEB / "daten").glob("*")}
    assert sum(groessen.values()) < 16e6, groessen
    if "grundkarte.json" in groessen:
        assert groessen["grundkarte.json"] < 3e6
