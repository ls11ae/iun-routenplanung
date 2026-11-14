/* Reiter „Dijkstra und A*“: beide Suchen nebeneinander, mit Animation der
 * abgeschlossenen Knoten und deren Anzahl. */
(function () {
  "use strict";
  const A = window.APP, K = window.IUNKarte;
  const $ = (s) => document.querySelector(s);
  const FARBE = "#0072B2";
  const S = { d: null, a: null, lauf: null };

  const rate = () => Math.pow(10, +$("#suche-tempo").value);     // Knoten je Sekunde

  function tempoText() {
    const r = rate();
    $("#suche-tempo-text").textContent = `etwa ${A.de(r >= 1000 ? Math.round(r / 100) * 100 : Math.round(r / 10) * 10)} Knoten je Sekunde`;
  }

  function personenwahl() {
    const wahl = $("#suche-persona"), alt = wahl.value;
    wahl.innerHTML = A.allePersonas().map((p) => `<option value="${p.id}">${p.name}</option>`).join("");
    wahl.value = alt || "fuss";
  }

  /** Zeichnet die ersten `bis` abgeschlossenen Knoten einer Karte (ab Position `von`). */
  function knotenZeichnen(k, ctx, p, von, bis) {
    const folge = k.folge, netz = A.netz;
    if (!folge) return;
    const g = p.zoom >= 15.5 ? 4 : p.zoom >= 13.5 ? 3 : 2, h = g / 2;
    ctx.fillStyle = FARBE; ctx.globalAlpha = 0.8;
    bis = Math.min(bis, folge.length);
    for (let i = von; i < bis; i++) {
      const v = folge[i], x = p.x(netz.mx[v]), y = p.y(netz.my[v]);
      if (x < 0 || y < 0 || x > p.w || y > p.h) continue;
      ctx.fillRect(x - h, y - h, g, g);
    }
    ctx.globalAlpha = 1;
  }

  function kartenAnlegen() {
    S.d = K.karte("karte-dijkstra", A.netz);
    S.a = K.karte("karte-astern", A.netz);
    for (const k of [S.d, S.a]) {
      A.karteAnbinden(k, false);
      k.ebene = new K.Leinwand((ctx, p) => {
        ctx.clearRect(0, 0, p.w, p.h);
        if (S.lauf) knotenZeichnen(k, ctx, p, 0, S.lauf.k);
      }, { pane: "suche" }).addTo(k.map);
      k.weg = L.layerGroup().addTo(k.map);
    }
    // Beide Karten zeigen immer denselben Ausschnitt
    let gesperrt = false;
    const kopple = (a, b) => a.map.on("move zoomend", () => {
      if (gesperrt) return;
      gesperrt = true;
      b.map.setView(a.map.getCenter(), a.map.getZoom(), { animate: false });
      gesperrt = false;
    });
    kopple(S.d, S.a); kopple(S.a, S.d);
  }

  function zaehlerZeigen() {
    const l = S.lauf;
    const nd = l ? Math.min(l.k, l.d.reihenfolge.length) : null, na = l ? Math.min(l.k, l.a.reihenfolge.length) : null;
    $("#zahl-dijkstra").textContent = l ? A.de(Math.floor(nd)) : "–";
    $("#zahl-astern").textContent = l ? A.de(Math.floor(na)) : "–";
    $("#titel-dijkstra").textContent = l ? `· ${A.de(Math.floor(nd))} Knoten` : "";
    $("#titel-astern").textContent = l ? `· ${A.de(Math.floor(na))} Knoten` : "";
  }

  function zuruecksetzen() {
    if (S.lauf) cancelAnimationFrame(S.lauf.bild);
    S.lauf = null;
    for (const k of [S.d, S.a]) { if (!k) continue; k.folge = null; k.weg.clearLayers(); k.ebene.neu(); }
    zaehlerZeigen();
    $("#suche-ergebnis").textContent = "";
    $("#suche-pause").disabled = true; $("#suche-ende").disabled = true;
    $("#suche-pause").textContent = "Pause";
  }

  function starten() {
    zuruecksetzen();
    const p = A.persona($("#suche-persona").value), f = A.feld(p), e = A.endpunkte(p);
    const t0 = performance.now();
    const d = IUN.kuerzesterWeg(A.netz, f.kosten, e.start, e.ziel, { protokoll: true });
    const t1 = performance.now();
    const a = IUN.kuerzesterWeg(A.netz, f.kosten, e.start, e.ziel,
      { protokoll: true, astern: true, untergrenze: 1 / p.tempo + (p.gewichte.laenge || 0) });
    const t2 = performance.now();
    if (!d.kanten) { $("#suche-ergebnis").textContent = "Für diese Persona gibt es keinen Weg zwischen Start und Ziel."; return; }
    S.lauf = { p, d, a, k: 0, laeuft: true, zuletzt: 0, ms: [t1 - t0, t2 - t1], max: Math.max(d.reihenfolge.length, a.reihenfolge.length) };
    S.d.folge = d.reihenfolge; S.a.folge = a.reihenfolge;
    $("#suche-pause").disabled = false; $("#suche-ende").disabled = false;
    S.lauf.bild = requestAnimationFrame(schritt);
  }

  function schritt(jetzt) {
    const l = S.lauf;
    if (!l || !l.laeuft) return;
    const dt = l.zuletzt ? Math.min(0.1, (jetzt - l.zuletzt) / 1000) : 0;
    l.zuletzt = jetzt;
    weiter(l.k + rate() * dt);
    if (l.k < l.max) l.bild = requestAnimationFrame(schritt);
  }

  /** Zeigt die Suche bis zum Knoten Nummer `k` und schließt sie am Ende ab. */
  function weiter(k) {
    const l = S.lauf, alt = l.k;
    l.k = Math.min(k, l.max);
    for (const karte of [S.d, S.a]) karte.ebene.dazu((ctx, p) => knotenZeichnen(karte, ctx, p, Math.floor(alt), Math.floor(l.k)));
    zaehlerZeigen();
    if (l.k >= l.max) fertig();
  }

  function fertig() {
    const l = S.lauf;
    l.laeuft = false;
    const linie = IUN.linie(A.netz, l.d.kanten), linieA = IUN.linie(A.netz, l.a.kanten);
    K.routenlinie(linie, "#1b1b1b", "", 4).addTo(S.d.weg);
    K.routenlinie(linieA, "#1b1b1b", "", 4).addTo(S.a.weg);
    $("#suche-pause").disabled = true; $("#suche-ende").disabled = true;
    const nd = l.d.reihenfolge.length, na = l.a.reihenfolge.length;
    const gleich = Math.abs(l.d.kosten - l.a.kosten) <= 1e-9 * l.d.kosten;
    $("#suche-ergebnis").innerHTML =
      `${gleich ? "Beide finden einen Weg mit denselben Kosten" : "Achtung: unterschiedliche Kosten"} ` +
      `(${A.format("kosten", l.d.kosten)}, Länge ${A.format("laenge", IUN.summe(IUN.werte(A.netz, "laenge"), l.d.kanten))}). ` +
      `Dijkstra hat <b>${A.de(nd)}</b> Knoten abgeschlossen, A* <b>${A.de(na)}</b>: das sind ${A.de(100 * (1 - na / nd))} % weniger. ` +
      `Rechenzeit ohne Animation: ${A.de(l.ms[0])} ms und ${A.de(l.ms[1])} ms.`;
  }

  document.addEventListener("iun-bereit", () => {
    tempoText();
    $("#suche-tempo").addEventListener("input", tempoText);
    $("#suche-start").addEventListener("click", starten);
    $("#suche-start-karte").addEventListener("click", starten);   // auf dem Handy direkt auf der Karte
    $("#suche-pause").addEventListener("click", () => {
      const l = S.lauf;
      if (!l) return;
      l.laeuft = !l.laeuft; l.zuletzt = 0;
      $("#suche-pause").textContent = l.laeuft ? "Pause" : "Weiter";
      if (l.laeuft) l.bild = requestAnimationFrame(schritt);
    });
    $("#suche-ende").addEventListener("click", () => { if (S.lauf) weiter(S.lauf.max); });
    $("#suche-persona").addEventListener("change", zuruecksetzen);
    A.beiAenderung.push(() => { if (A.reiter === "suche") zuruecksetzen(); });
    A.beiReiter.push((name) => {
      if (name !== "suche") { if (S.lauf) { S.lauf.laeuft = false; $("#suche-pause").textContent = "Weiter"; } return; }
      if (!S.d) kartenAnlegen();
      S.d.map.invalidateSize(); S.a.map.invalidateSize();
      S.d.map.fitBounds(L.latLngBounds([[A.start.lat, A.start.lon], [A.ziel.lat, A.ziel.lon]]).pad(0.35), { animate: false });
      personenwahl();
    });
  });
})();
