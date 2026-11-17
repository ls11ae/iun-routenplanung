"""Die Webdemo lädt nichts von fremden Servern, und ihre Daten passen zusammen."""

import json
import re
from html.parser import HTMLParser
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


class _Texte(HTMLParser):
    """Sammelt sichtbare Texte und übersetzbare Attribute ohne englische Fassung."""
    LEER = {"meta", "link", "input", "br", "img", "hr", "source", "area", "base", "col", "embed", "wbr"}
    OHNE = {"script", "style", "code"}             # wird nicht übersetzt
    ERLAUBT = {"km/h"}                             # in beiden Sprachen gleich

    def __init__(self):
        super().__init__()
        self.stapel, self.fehlend = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for attr in ("aria-label", "title", "alt", "placeholder"):
            if attr in a and f"data-en-{attr}" not in a and re.search(r"[A-Za-zÄÖÜäöüß]", a[attr]):
                self.fehlend.append(f"<{tag} {attr}={a[attr][:50]!r}>")
        if tag == "meta" and a.get("name") == "description" and "data-en-content" not in a:
            self.fehlend.append("<meta name=description> ohne data-en-content")
        if tag not in self.LEER:
            self.stapel.append((tag, "data-en" in a))

    def handle_endtag(self, tag):
        while self.stapel:
            if self.stapel.pop()[0] == tag:
                break

    def handle_data(self, text):
        text = text.strip()
        if (not text or text in self.ERLAUBT or not re.search(r"[A-Za-zÄÖÜäöüß]", text)
                or any(t in self.OHNE for t, _ in self.stapel) or any(en for _, en in self.stapel)):
            return
        self.fehlend.append(repr(text[:60]))


def test_englische_texte_im_html():
    """Jeder sichtbare Text und jedes Attribut wie aria-label hat eine englische Fassung
    (data-en bzw. data-en-<attribut>), und jede Seite lädt js/sprache.js vor den übrigen Skripten."""
    fehler = []
    for html in sorted(WEB.glob("*.html")):
        s = html.read_text(encoding="utf-8")
        p = _Texte()
        p.feed(s)
        fehler += [f"{html.name}: {f}" for f in p.fehlend]
        skripte = re.findall(r'<script src="([^"]+)"', s)
        if skripte and skripte[0] != "js/sprache.js":
            fehler.append(f"{html.name}: js/sprache.js muss das erste Skript sein")
    assert not fehler, "Ohne englische Fassung:\n" + "\n".join(fehler)


def test_englische_texte_in_daten_und_skripten():
    personas = json.loads((WEB / "personas.json").read_text(encoding="utf-8"))
    for k in personas["kriterien"]:
        assert {"name_en", "beschreibung_en", "gewicht_einheit_en"} <= set(k), k["id"]
    for p in personas["personas"]:
        assert {"name_en", "beschreibung_en"} <= set(p), p["id"]
    datei = WEB / "daten" / "reisezeiten.json"
    if datei.exists():
        D = json.loads(datei.read_text(encoding="utf-8"))
        assert len(D["annahmen"]["de"]) == len(D["annahmen"]["en"]) > 0
        assert D["ziel"]["name_en"]
    # Zahlen und Daten formatiert nur sprache.js; alle anderen Skripte benutzen IUNSprache.zahl
    for js in (WEB / "js").glob("*.js"):
        if js.name != "sprache.js":
            assert "de-DE" not in js.read_text(encoding="utf-8"), js.name


def test_daten_der_webdemo_klein_genug():
    """Pages liefert alles aus webdemo/ aus; die Seite soll auch mobil schnell laden."""
    groessen = {p.name: p.stat().st_size for p in (WEB / "daten").glob("*")}
    assert sum(groessen.values()) < 16e6, groessen
    if "grundkarte.json" in groessen:
        assert groessen["grundkarte.json"] < 3e6
