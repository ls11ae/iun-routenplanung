/* Karte „Wo verliert der Nahverkehr gegen das Auto?“: Raster über Dortmund mit den
 * Reisezeiten zum Campus Nord. Die Daten (daten/reisezeiten.json) berechnet
 * nahverkehr/reisezeitkarte.py mit dem Routenplaner MOTIS. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const de = (x, stellen = 0) => x.toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen });

  // Eine Farbe, von hell nach dunkel: Die Helligkeit trägt die Reihenfolge, die Legende die Werte.
  const RAMPE = ["#eff3ff", "#bdd7e7", "#6baed6", "#2f7fbf", "#08488f"];
  const OHNE = "#8c8c88";
  const mal = (v) => de(v, 1).replace(",0", "");

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
  const ANSICHTEN = {
    oepnv_auto: Object.assign({ name: "Verhältnis Bus und Bahn zu Auto", frage: "Wie viel länger dauert es mit Bus und Bahn als mit dem Auto?", f: (z) => (z.oepnv == null || z.auto == null ? null : z.oepnv / z.auto) }, verhaeltnis([2, 3, 4, 5])),
    oepnv_rad: Object.assign({ name: "Verhältnis Bus und Bahn zu Fahrrad", frage: "Wie viel länger dauert es mit Bus und Bahn als mit dem Rad?", f: (z) => (z.oepnv == null || z.rad == null ? null : z.oepnv / z.rad) }, verhaeltnis([1, 1.25, 1.5, 2])),
    oepnv: Object.assign({ name: "Reisezeit mit Bus und Bahn", frage: "Wie lange dauert es mit Bus und Bahn?", f: (z) => z.oepnv }, minuten([20, 40, 60, 80])),
    auto: Object.assign({ name: "Reisezeit mit dem Auto", frage: "Wie lange dauert es mit dem Auto?", f: (z) => z.auto }, minuten([5, 10, 15, 20])),
    rad: Object.assign({ name: "Reisezeit mit dem Fahrrad", frage: "Wie lange dauert es mit dem Rad?", f: (z) => z.rad }, minuten([15, 30, 45, 60])),
  };

  let D, karte, rechtecke = [], gewaehlt = -1;

  /** Werte einer Zelle mit den aktuellen Einstellungen (Minuten oder null). */
  function zelle(i) {
    const Z = D.zellen, auto = Z.auto_min[i];
    return {
      oepnv: Z[$("#oepnv-art").value][i], auto: auto == null ? null : auto + +$("#zuschlag").value,
      rad: Z.rad_min[i], fuss: Z.fuss_min ? Z.fuss_min[i] : null, umstiege: Z.umstiege ? Z.umstiege[i] : null,
      zumHalt: Z.zum_halt_min ? Z.zum_halt_min[i] : null,
    };
  }
  const klasse = (v, grenzen) => (v == null ? -1 : grenzen.filter((g) => v > g).length);

  function zeichnen() {
    const a = ANSICHTEN[$("#ansicht").value], n = D.zellen.lat.length;
    const anzahl = new Array(a.grenzen.length + 1).fill(0), werte = [];
    let ohne = 0;
    for (let i = 0; i < n; i++) {
      const v = a.f(zelle(i)), k = klasse(v, a.grenzen);
      if (k < 0) ohne++; else { anzahl[k]++; werte.push(v); }
      rechtecke[i].setStyle(k < 0
        ? { fillColor: OHNE, fillOpacity: 0.35, color: "#555", weight: 1, dashArray: "3 3" }
        : { fillColor: RAMPE[k], fillOpacity: 0.82, color: i === gewaehlt ? "#000" : "#fff", weight: i === gewaehlt ? 3 : 0.5, dashArray: null });
    }
    if (gewaehlt >= 0) rechtecke[gewaehlt].bringToFront();
    const mit = n - ohne, namen = a.klassen(a.grenzen);
    $("#frage").textContent = a.frage;
    $("#zuschlag-wert").textContent = `+ ${$("#zuschlag").value} min`;
    $("#klassen").innerHTML = namen.map((name, k) =>
      `<li><span class="feld" style="background:${RAMPE[k]}"></span><span>${name}</span><span class="anteil">${de(100 * anzahl[k] / Math.max(1, mit))} % der Zellen</span></li>`).join("") +
      `<li><span class="feld" style="background:${OHNE}; opacity:0.6; border-style:dashed"></span><span>kein Wert (keine Verbindung oder kein Weg in der Nähe)</span><span class="anteil">${de(ohne)} Zellen</span></li>`;
    werte.sort((x, y) => x - y);
    const median = werte.length ? werte[Math.floor(werte.length / 2)] : null;
    $("#kennzahl").innerHTML = median == null ? "" : `Median über ${de(mit)} Zellen: <b>${a.wert(median)}</b>.`;
    zelleZeigen();
  }

  function zelleZeigen() {
    if (gewaehlt < 0) return;
    const z = zelle(gewaehlt), t = (v) => (v == null ? "kein Wert" : `${de(v)} min`);
    const umstiege = z.umstiege == null || z.oepnv == null ? "" : z.umstiege < 0 ? " (zu Fuß am schnellsten)" : ` (${z.umstiege} ${z.umstiege === 1 ? "Umstieg" : "Umstiege"}${z.zumHalt != null ? `, ${de(z.zumHalt)} min Fußweg zum ersten Halt` : ""})`;
    const v = z.oepnv != null && z.auto != null ? `<br>Bus und Bahn brauchen <b>${de(z.oepnv / z.auto, 1)}-mal</b> so lange wie das Auto.` : "";
    $("#zelle").innerHTML = `Bus und Bahn: <b>${t(z.oepnv)}</b>${umstiege}<br>Auto: <b>${t(z.auto)}</b>${+$("#zuschlag").value ? " (mit Zuschlag)" : ""}<br>Fahrrad: <b>${t(z.rad)}</b>${v}`;
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
    const Z = D.zellen, [dx, dy] = D.zelle_grad;
    karte = L.map("karte", { minZoom: 10, maxZoom: 17, zoomSnap: 0.5 });
    karte.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>',
    }).addTo(karte);
    const leinwand = L.canvas({ padding: 0.3 });
    const grenze = L.geoJSON(D.grenze, { style: { color: "#1b1b1b", weight: 2, fill: false }, interactive: false }).addTo(karte);
    karte.fitBounds(grenze.getBounds());
    for (let i = 0; i < Z.lat.length; i++) {
      const r = L.rectangle([[Z.lat[i] - dy / 2, Z.lon[i] - dx / 2], [Z.lat[i] + dy / 2, Z.lon[i] + dx / 2]], { renderer: leinwand });
      r.on("click", () => { gewaehlt = i; zeichnen(); });
      rechtecke.push(r.addTo(karte));
    }
    grenze.bringToFront();
    L.marker([D.ziel.lat, D.ziel.lon], {
      title: "Ziel: " + D.ziel.name, alt: "Ziel: " + D.ziel.name, keyboard: false,
      icon: L.divIcon({ className: "", html: '<div class="marke marke-ziel">Z</div>', iconSize: [28, 28], iconAnchor: [14, 14] }),
    }).addTo(karte).bindTooltip("Ziel: " + D.ziel.name);

    const zeit = new Date(D.zeitpunkt);
    $("#rahmen").textContent = `Ziel: ${D.ziel.name}. Start: ${zeit.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}, ` +
      `${zeit.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr, von der Mitte jeder Rasterzelle (${D.raster_m} m).`;
    $("#ansicht").innerHTML = Object.entries(ANSICHTEN).map(([id, a]) => `<option value="${id}">${a.name}</option>`).join("");
    $("#annahmen").innerHTML = (D.annahmen || []).map((s) => `<li>${s}</li>`).join("");
    if (D.fahrplan) $("#stand-fahrplan").textContent = `, gültig ${D.fahrplan.gueltig_von.split("-").reverse().join(".")} bis ${D.fahrplan.gueltig_bis.split("-").reverse().join(".")}`;
    for (const id of ["ansicht", "oepnv-art", "zuschlag"]) $("#" + id).addEventListener("input", zeichnen);
    $("#meldung").hidden = true;
    $("#inhalt").hidden = false;
    zeichnen();
  }

  laden();
})();
