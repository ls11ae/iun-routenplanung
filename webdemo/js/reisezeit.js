/* Karte „Wo verliert der Nahverkehr gegen das Auto?“: Raster über Dortmund mit den
 * Reisezeiten zum Campus Nord. Die Daten (daten/reisezeiten.json) berechnet
 * nahverkehr/reisezeitkarte.py mit dem Routenplaner MOTIS; Klassengrenzen, Zuschlag und
 * die Grenzen für „in Gehweite“ stehen dort unter „darstellung“. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const de = (x, stellen = 0) => x.toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen });
  const mal = (v) => de(v, 1).replace(",0", "");

  // Eine Farbe, von hell nach dunkel: Die Helligkeit trägt die Reihenfolge, die Legende die Werte.
  const RAMPEN = { 4: ["#deebf7", "#9ecae1", "#4292c6", "#08519c"], 5: ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"] };
  const rampe = (a) => RAMPEN[a.grenzen.length + 1];
  // Sonderfälle: eigene Farbe UND eigene Randlinie, damit sie nicht nur an der Farbe erkennbar sind
  const SONDER = {
    campus: { fillColor: "#009E73", fillOpacity: 0.6, color: "#00513b", weight: 1.5, dashArray: null },
    kein_halt: { fillColor: "#8c8c88", fillOpacity: 0.45, color: "#3d3d3a", weight: 1, dashArray: "4 3" },
    kein_wert: { fillColor: "#ffffff", fillOpacity: 0.6, color: "#6b6b68", weight: 1, dashArray: "1 3" },
  };
  const FELD = {   // Muster der Legende, passend zu SONDER
    campus: "background:#009E73; opacity:0.75; border:2px solid #00513b",
    kein_halt: "background:#8c8c88; opacity:0.7; border:2px dashed #3d3d3a",
    kein_wert: "background:#fff; border:2px dotted #6b6b68",
  };

  let D, P, karte, rechtecke = [], gewaehlt = -1, legende;

  const verhaeltnis = (grenzen) => ({
    grenzen,
    klassen: (g) => [g[0] === 1 ? "höchstens gleich lang" : `höchstens ${mal(g[0])}-mal so lange`,
      ...g.slice(1).map((x, i) => `${mal(g[i])}- bis ${mal(x)}-mal so lange`), `mehr als ${mal(g[g.length - 1])}-mal so lange`],
    wert: (v) => `${de(v, 1)}-mal so lange`,
  });
  const minuten = (grenzen) => ({
    grenzen,
    klassen: (g) => [`bis ${g[0]} min`, ...g.slice(1).map((x, i) => `${g[i]} bis ${x} min`), `über ${g[g.length - 1]} min`],
    wert: (v) => `${de(v)} min`,
  });
  function ansichten() {
    return {
      oepnv_auto: Object.assign({ name: "Verhältnis Bus und Bahn zu Auto", frage: "Wie viel länger dauert es mit Bus und Bahn als mit dem Auto?", oepnv: true,
        f: (z) => (z.oepnv == null || z.auto == null ? null : z.oepnv / z.auto) }, verhaeltnis(P.verhaeltnis_grenzen)),
      oepnv_rad: Object.assign({ name: "Verhältnis Bus und Bahn zu Fahrrad", frage: "Wie viel länger dauert es mit Bus und Bahn als mit dem Rad?", oepnv: true,
        f: (z) => (z.oepnv == null || z.rad == null ? null : z.oepnv / z.rad) }, verhaeltnis([1, 1.5, 2])),
      oepnv: Object.assign({ name: "Reisezeit mit Bus und Bahn", frage: "Wie lange dauert es mit Bus und Bahn?", oepnv: true, f: (z) => z.oepnv }, minuten([30, 45, 60])),
      auto: Object.assign({ name: "Reisezeit mit dem Auto", frage: "Wie lange dauert es mit dem Auto (mit Zuschlag)?", f: (z) => z.auto }, minuten([10, 15, 20])),
      rad: Object.assign({ name: "Reisezeit mit dem Fahrrad", frage: "Wie lange dauert es mit dem Rad?", f: (z) => z.rad }, minuten([20, 35, 50])),
    };
  }
  let ANSICHTEN;

  /** Werte einer Zelle mit den aktuellen Einstellungen (Minuten oder null). */
  function zelle(i) {
    const Z = D.zellen, auto = Z.auto_min[i];
    return {
      oepnv: Z[$("#oepnv-art").value][i], auto: auto == null ? null : auto + +$("#zuschlag").value,
      rad: Z.rad_min[i], fuss: Z.fuss_min[i], umstiege: Z.umstiege[i], zumHalt: Z.zum_halt_min[i],
      halt: Z.halt_m[i], beste: Z.oepnv_beste_min[i], schlechteste: Z.oepnv_schlechteste_min[i],
    };
  }
  /** Kategorie: "campus", "kein_halt", "kein_wert" oder die Nummer der Klasse. */
  function kategorie(a, z) {
    if (z.fuss != null && z.fuss <= P.campus_fuss_max_min) return "campus";
    if (a.oepnv && z.halt != null && z.halt > P.halt_max_m) return "kein_halt";
    const v = a.f(z);
    return v == null ? "kein_wert" : a.grenzen.filter((g) => v > g).length;
  }
  const SONDER_NAME = () => ({
    campus: `Campus zu Fuß in höchstens ${P.campus_fuss_max_min} min`,
    kein_halt: `keine Haltestelle mit Abfahrt zwischen 7 und 9 Uhr im Umkreis von ${de(P.halt_max_m / 1000, 1).replace(",0", "")} km`,
    kein_wert: "kein Wert (kein Weg in der Nähe oder keine Verbindung)",
  });

  function zeichnen() {
    const a = ANSICHTEN[$("#ansicht").value], n = D.zellen.lat.length;
    const anzahl = { campus: 0, kein_halt: 0, kein_wert: 0 }, klassen = new Array(a.grenzen.length + 1).fill(0), werte = [];
    for (let i = 0; i < n; i++) {
      const z = zelle(i), k = kategorie(a, z);
      if (typeof k === "number") { klassen[k]++; werte.push(a.f(z)); } else anzahl[k]++;
      const stil = typeof k === "number"
        ? { fillColor: rampe(a)[k], fillOpacity: 0.85, color: "#ffffff", weight: 0.5, dashArray: null }
        : Object.assign({}, SONDER[k]);
      if (i === gewaehlt) Object.assign(stil, { color: "#000", weight: 3, dashArray: null });
      rechtecke[i].setStyle(stil);
    }
    if (gewaehlt >= 0) rechtecke[gewaehlt].bringToFront();
    const mit = werte.length, namen = a.klassen(a.grenzen), sonder = SONDER_NAME();
    $("#frage").textContent = a.frage;
    $("#zuschlag-wert").textContent = `+ ${$("#zuschlag").value} min`;
    werte.sort((x, y) => x - y);
    const median = mit ? (mit % 2 ? werte[(mit - 1) / 2] : (werte[mit / 2 - 1] + werte[mit / 2]) / 2) : null;
    $("#kennzahl").innerHTML = median == null ? "" : `Median über ${de(mit)} Zellen mit Wert: <b>${a.wert(median)}</b>.`;
    const zuschlag = +$("#zuschlag").value;
    const zeile = (feld, text, anteil) => `<li><span class="feld" style="${feld}"></span><span>${text}</span><span class="anteil">${anteil}</span></li>`;
    legende.innerHTML = `<details ${window.innerWidth > 820 ? "open" : ""}><summary>Legende und Annahmen</summary>
      <div class="legende-titel">${a.name}</div>
      <ul class="klassen">${namen.map((name, k) => zeile(`background:${rampe(a)[k]}`, name, `${de(100 * klassen[k] / Math.max(1, mit))} %`)).join("")}
      ${Object.keys(sonder).filter((k) => anzahl[k] || k === "campus").map((k) => zeile(FELD[k], sonder[k], `${de(anzahl[k])} Zellen`)).join("")}</ul>
      <ul class="annahmen-kurz">
        <li>Bus und Bahn: Median über ${D.abfahrten.anzahl} Abfahrten ${uhr(D.abfahrten.von)}–${uhr(D.abfahrten.bis)} Uhr, Wartezeit zählt mit, Tür zu Tür.</li>
        <li>Auto: Fahrzeit ohne Stau${zuschlag ? ` + ${zuschlag} min für Parken und Fußweg` : ", ohne Zuschlag für Parken"}.</li>
        <li>Ziel Campus Nord, ${tag(D.abfahrten.von)}; Fahrplan nach Plan; Raster ${D.raster_m} m.</li>
      </ul></details>`;
    zelleZeigen();
  }

  const uhr = (iso) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  const tag = (iso) => new Date(iso).toLocaleDateString("de-DE", { weekday: "short", day: "numeric", month: "numeric", year: "numeric" });

  function zelleZeigen() {
    if (gewaehlt < 0) return;
    const z = zelle(gewaehlt), t = (v) => (v == null ? "kein Wert" : `${de(v)} min`);
    const k = kategorie(ANSICHTEN[$("#ansicht").value], z);
    const umstiege = z.umstiege == null || z.oepnv == null ? "" : z.umstiege < 0 ? " (zu Fuß am schnellsten)"
      : ` (${z.umstiege} ${z.umstiege === 1 ? "Umstieg" : "Umstiege"}${z.zumHalt != null ? `, ${de(z.zumHalt)} min Fußweg zum ersten Halt` : ""})`;
    const spanne = z.beste != null && $("#oepnv-art").value === "oepnv_min" ? `<br><span class="leise">je nach Abfahrtsminute ${de(z.beste)} bis ${de(z.schlechteste)} min</span>` : "";
    const v = z.oepnv != null && z.auto != null ? `<br>Bus und Bahn brauchen <b>${de(z.oepnv / z.auto, 1)}-mal</b> so lange wie das Auto.` : "";
    const hinweis = typeof k === "string" ? `<br><i>${SONDER_NAME()[k]}</i>` : "";
    $("#zelle").innerHTML = `Bus und Bahn: <b>${t(z.oepnv)}</b>${umstiege}${spanne}<br>Auto: <b>${t(z.auto)}</b>${+$("#zuschlag").value ? " (mit Zuschlag)" : ""}` +
      `<br>Fahrrad: <b>${t(z.rad)}</b> · zu Fuß: <b>${t(z.fuss)}</b><br>Nächste Haltestelle mit Abfahrt 7–9 Uhr: ${z.halt == null ? "–" : de(z.halt) + " m (Luftlinie)"}${v}${hinweis}`;
  }

  async function laden() {
    try {
      const r = await fetch("daten/reisezeiten.json");
      if (!r.ok) throw new Error(r.status);
      D = await r.json();
    } catch (fehler) {
      $("#meldung").classList.add("fehler");
      $("#meldung").innerHTML = location.protocol === "file:"
        ? "Die Seite wurde direkt als Datei geöffnet. Starten Sie im Ordner <code>webdemo</code> einen Webserver mit <code>python -m http.server</code> und öffnen Sie <a href=\"http://localhost:8000/reisezeit.html\">http://localhost:8000/reisezeit.html</a>."
        : "Die Reisezeiten konnten nicht geladen werden.";
      return;
    }
    P = D.darstellung;
    ANSICHTEN = ansichten();
    const Z = D.zellen, [dx, dy] = D.zelle_grad;
    karte = L.map("karte", { minZoom: 10, maxZoom: 16, zoomSnap: 0.5 });
    karte.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    karte.attributionControl.addAttribution(IUNGrundkarte.NENNUNG);
    const grenze = L.geoJSON(D.grenze, { style: { color: "#1b1b1b", weight: 2, fill: false }, interactive: false });
    karte.fitBounds(grenze.getBounds());
    // Grundkarte: Flächen unter dem Raster, Bahn, Autobahn und Flüsse dünn darüber, Namen ganz oben
    IUNGrundkarte.laden().then((g) => {
      IUNGrundkarte.ebene(karte, g, ["gruen", "wasser"], "flaechen", 200);
      IUNGrundkarte.ebene(karte, g, ["fluss", "autobahn", "bundesstrasse", "bahn"], "linien", 420,
        { alle: { color: "#3b3b3b", opacity: 0.55, weight: 1.2 }, fluss: { color: "#1f6fb2", opacity: 0.7, weight: 1.4 } });
      IUNGrundkarte.ortsnamen(karte, g, "ortsnamen", 640, { gross: 12, klein: 14 },
        ["Mitte", "Hörde", "Aplerbeck", "Mengede", "Eving", "Scharnhorst", "Brackel", "Hombruch", "Lütgendortmund", "Huckarde"]);
    }).catch(() => {});
    const leinwand = L.canvas({ padding: 0.3 });
    for (let i = 0; i < Z.lat.length; i++) {
      const r = L.rectangle([[Z.lat[i] - dy / 2, Z.lon[i] - dx / 2], [Z.lat[i] + dy / 2, Z.lon[i] + dx / 2]], { renderer: leinwand });
      r.on("click", () => { gewaehlt = i; zeichnen(); });
      rechtecke.push(r.addTo(karte));
    }
    karte.createPane("grenze").style.zIndex = 430;
    karte.getPane("grenze").style.pointerEvents = "none";
    L.geoJSON(D.grenze, { pane: "grenze", style: { color: "#1b1b1b", weight: 2, fill: false }, interactive: false }).addTo(karte);
    L.marker([D.ziel.lat, D.ziel.lon], {
      title: "Ziel: " + D.ziel.name, alt: "Ziel: " + D.ziel.name, keyboard: false,
      icon: L.divIcon({ className: "", html: '<div class="marke marke-ziel">Z</div>', iconSize: [28, 28], iconAnchor: [14, 14] }),
    }).addTo(karte).bindTooltip("Ziel: " + D.ziel.name);
    // Legende mit den wichtigsten Annahmen direkt auf der Karte
    const Legende = L.Control.extend({ onAdd: () => { const d = L.DomUtil.create("div", "kartenlegende"); L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d); return d; } });
    legende = new Legende({ position: "topright" }).addTo(karte).getContainer();

    $("#rahmen").textContent = `Ziel: ${D.ziel.name}. Start in der Mitte jeder Rasterzelle (${D.raster_m} m), ` +
      `${new Date(D.abfahrten.von).toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}, ` +
      `Abfahrten ${uhr(D.abfahrten.von)} bis ${uhr(D.abfahrten.bis)} Uhr alle ${D.abfahrten.schritt_min} Minuten.`;
    $("#ansicht").innerHTML = Object.entries(ANSICHTEN).map(([id, a]) => `<option value="${id}">${a.name}</option>`).join("");
    $("#oepnv-art").innerHTML = `<option value="oepnv_min">Median ${uhr(D.abfahrten.von)}–${uhr(D.abfahrten.bis)} Uhr, mit Wartezeit</option>` +
      `<option value="oepnv_dauer_min">schnellste Verbindung, ohne Wartezeit</option>`;
    $("#zuschlag").value = P.zuschlag_min;
    $("#annahmen").innerHTML = (D.annahmen || []).map((s) => `<li>${s}</li>`).join("");
    if (D.fahrplan) $("#stand-fahrplan").textContent = `, gültig ${D.fahrplan.gueltig_von.split("-").reverse().join(".")} bis ${D.fahrplan.gueltig_bis.split("-").reverse().join(".")}`;
    for (const id of ["ansicht", "oepnv-art", "zuschlag"]) $("#" + id).addEventListener("input", zeichnen);
    $("#meldung").hidden = true;
    $("#inhalt").hidden = false;
    zeichnen();
  }

  laden();
})();
