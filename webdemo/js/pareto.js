/* Reiter „Pareto-Front“: alle Pareto-optimalen Routen für zwei Kriterien, als
 * Diagramm, Tabelle und auf der Karte. Markiert, welche Punkte eine gewichtete
 * Summe findet, und dünnt fast identische Routen aus. */
(function () {
  "use strict";
  const A = window.APP, K = window.IUNKarte, S = window.IUNSprache, w = S.w;
  const $ = (s) => document.querySelector(s);
  const BLAU = "#0072B2", ROT = "#D55E00", TINTE = "#1b1b1b";
  const P = { ergebnis: null, auswahl: -1, ebene: null };

  // Spielraum beim Ausdünnen, je nach Einheit des Kriteriums: [Voreinstellung, Maximum, Schritt]
  function spielraum(id) {
    if (id === "zeit") return [30, 300, 5];
    if (id === "anstieg") return [5, 30, 1];
    return A.kriterium(id).einheit === "Stück" ? [1, 5, 1] : [100, 1000, 10];
  }
  const STUECK = w("Stück", "items");
  const einheit = (id) => (id === "zeit" ? "s" : A.kriterium(id).einheit === "Stück" ? STUECK : "m");
  const achsentext = (id) => (id === "zeit" ? w("Zeit (min)", "Time (min)") : id === "laenge" ? w("Länge (m)", "Length (m)")
    : `${A.name(id)} (${A.kriterium(id).einheit === "Stück" ? STUECK : A.kriterium(id).einheit})`);
  const achsenwert = (id, w) => (id === "zeit" ? w / 60 : w);

  const VORSCHLAG = { fuss: "fahrbahn", rad: "hauptstrasse", rollstuhl: "belag_unbekannt", blind: "querung_ohne_ampel", eigene: "hauptstrasse" };

  function auswahlen() {
    const wahl = $("#pareto-persona"), alt = wahl.value;
    wahl.innerHTML = A.allePersonas().map((p) => `<option value="${p.id}">${S.feld(p, "name")}</option>`).join("");
    wahl.value = alt || "rad";
    if (!$("#pareto-a").options.length) {
      const opt = `<option value="zeit">${w("Zeit", "Time")}</option>` + A.kriterien.filter((k) => !k.nur_sperre).map((k) => `<option value="${k.id}">${S.feld(k, "name")}</option>`).join("");
      $("#pareto-a").innerHTML = opt; $("#pareto-b").innerHTML = opt;
      $("#pareto-a").value = "zeit"; $("#pareto-b").value = VORSCHLAG[wahl.value];
    }
  }

  function berechnen() {
    const p = A.persona($("#pareto-persona").value), a = $("#pareto-a").value, b = $("#pareto-b").value;
    if (a === b) { $("#pareto-status").textContent = w("Bitte zwei verschiedene Kriterien wählen.", "Please choose two different criteria."); return; }
    $("#pareto-status").textContent = w("Rechnet …", "Computing …");
    $("#pareto-start").disabled = true;
    setTimeout(() => {
      const e = A.endpunkte(p), FA = IUN.kriteriumFeld(A.netz, p, a), FB = IUN.kriteriumFeld(A.netz, p, b);
      const t0 = performance.now();
      const r = IUN.paretoFront(A.netz, FA, FB, e.start, e.ziel, { maxMarken: 12e6 });
      const ms = performance.now() - t0;
      // zum Vergleich: ein einzelner Dijkstra-Lauf für das erste Kriterium
      const t1 = performance.now(), dj = IUN.kuerzesterWeg(A.netz, FA, e.start, e.ziel), msDijkstra = performance.now() - t1;
      $("#pareto-start").disabled = false;
      if (!r.routen.length) {
        P.ergebnis = null; $("#pareto-ergebnis").hidden = true; P.ebene.clearLayers();
        $("#pareto-status").textContent = w("Für diese Persona gibt es keinen Weg zwischen Start und Ziel.", "For this persona there is no path between start and destination.");
        return;
      }
      P.ergebnis = { p, a, b, routen: r.routen, art: IUN.gestuetzt(r.routen), marken: r.marken, ms, abgebrochen: r.abgebrochen,
                     abgeschlossen: r.abgeschlossen, dijkstra: { ms: msDijkstra, knoten: dj.abgeschlossen } };
      P.auswahl = -1;
      for (const [x, id] of [["a", a], ["b", b]]) {
        const [vor, max, schritt] = spielraum(id), regler = $("#spiel-" + x);
        regler.max = max; regler.step = schritt; regler.value = vor;
        $("#spiel-" + x + "-name").textContent = w("Spielraum ", "Tolerance ") + A.name(id);
      }
      $("#pareto-ergebnis").hidden = false;
      zeigen();
    }, 30);
  }

  function zeigen() {
    const E = P.ergebnis;
    if (!E) return;
    const ta = +$("#spiel-a").value, tb = +$("#spiel-b").value;
    $("#spiel-a-wert").textContent = `${A.zahl(ta)} ${einheit(E.a)}`;
    $("#spiel-b-wert").textContent = `${A.zahl(tb)} ${einheit(E.b)}`;
    E.relevant = IUN.relevante(E.routen, ta, tb);
    if (P.auswahl < 0 || P.auswahl >= E.routen.length) P.auswahl = E.relevant[0];
    const n = E.routen.length, mit = E.art.filter((x) => x > 0).length;
    const z = A.zahl;
    $("#pareto-status").innerHTML = w(
      `<b>${z(n)}</b> Pareto-optimale ${n === 1 ? "Route" : "Routen"}. ` +
      `<b>${z(mit)}</b> davon findet eine gewichtete Summe, <b>${z(n - mit)}</b> nicht. ` +
      `Spürbar verschieden: <b>${E.relevant.length}</b>.` +
      (E.abgebrochen ? " Achtung: Die Suche wurde wegen zu vieler Marken abgebrochen; die Liste ist unvollständig." : ""),
      `<b>${z(n)}</b> Pareto-optimal ${n === 1 ? "route" : "routes"}. ` +
      `<b>${z(mit)}</b> of them are found by a weighted sum, <b>${z(n - mit)}</b> are not. ` +
      `Noticeably different: <b>${E.relevant.length}</b>.` +
      (E.abgebrochen ? " Caution: the search was stopped because of too many labels; the list is incomplete." : ""));
    $("#pareto-aufwand").innerHTML = w(
      `Aufwand: ${z(E.marken)} Marken (Labels) erzeugt, ${z(E.abgeschlossen)} davon abgearbeitet, ${z(E.ms)} ms. ` +
      `Zum Vergleich: Dijkstra für ${A.name(E.a)} allein arbeitet ${z(E.dijkstra.knoten)} Knoten ab und braucht ${z(E.dijkstra.ms)} ms. ` +
      `Marken, die das Ziel nachweislich nicht mehr verbessern können, werden verworfen; sonst wären es um ein Vielfaches mehr.`,
      `Effort: ${z(E.marken)} labels created, ${z(E.abgeschlossen)} of them settled, ${z(E.ms)} ms. ` +
      `For comparison: Dijkstra for ${A.name(E.a)} alone settles ${z(E.dijkstra.knoten)} nodes and takes ${z(E.dijkstra.ms)} ms. ` +
      `Labels that provably cannot improve the destination any more are discarded; otherwise there would be many times as many.`);
    $("#pareto-beschreibung").textContent = w(
      `Streudiagramm mit ${n} Pareto-optimalen Routen: ${achsentext(E.a)} gegen ${achsentext(E.b)}. ` +
      `${mit} Routen liegen auf der unteren konvexen Hülle und werden von einer gewichteten Summe gefunden, ${n - mit} nicht.`,
      `Scatter plot of ${n} Pareto-optimal routes: ${achsentext(E.a)} against ${achsentext(E.b)}. ` +
      `${mit} routes lie on the lower convex hull and are found by a weighted sum, ${n - mit} are not.`);
    diagramm();
    tabellen();
    karte();
  }

  // ------------------------------------------------------------------ Diagramm

  function schritte(min, max, anzahl) {
    const roh = (max - min) / anzahl || 1, potenz = Math.pow(10, Math.floor(Math.log10(roh)));
    const s = [1, 2, 5, 10].map((f) => f * potenz).find((x) => x >= roh);
    const liste = [];
    for (let v = Math.ceil(min / s) * s; v <= max + 1e-9; v += s) liste.push(Math.round(v / s) * s + 0);   // + 0: kein „-0“
    return { liste, stellen: Math.max(0, -Math.floor(Math.log10(s))) };
  }

  function diagramm() {
    const E = P.ergebnis, svg = $("#pareto-diagramm");
    const B = 400, H = 300, l = 54, r = 16, o = 16, u = 42;
    const xs = E.routen.map((z) => achsenwert(E.a, z.a)), ys = E.routen.map((z) => achsenwert(E.b, z.b));
    const bereich = (w) => { const mi = Math.min(...w), ma = Math.max(...w), d = (ma - mi) || Math.max(1, Math.abs(ma) * 0.1); return [mi - d * 0.06, ma + d * 0.06]; };
    const [x0, x1] = bereich(xs), [y0, y1] = bereich(ys);
    const X = (v) => l + (v - x0) / (x1 - x0) * (B - l - r), Y = (v) => H - u - (v - y0) / (y1 - y0) * (H - o - u);
    const tx = schritte(x0, x1, 5), ty = schritte(y0, y1, 5);
    const zahl = (v, t) => A.zahl(v, Math.min(t.stellen, 2));
    let s = `<title id="pareto-titel">${w(`Pareto-Front: ${achsentext(E.a)} gegen ${achsentext(E.b)}`, `Pareto front: ${achsentext(E.a)} against ${achsentext(E.b)}`)}</title><desc id="pareto-beschreibung">${$("#pareto-beschreibung").textContent}</desc>`;
    s += '<g class="gitter">' + tx.liste.map((v) => `<line x1="${X(v)}" x2="${X(v)}" y1="${o}" y2="${H - u}"/>`).join("") +
      ty.liste.map((v) => `<line x1="${l}" x2="${B - r}" y1="${Y(v)}" y2="${Y(v)}"/>`).join("") + "</g>";
    s += `<g class="achse"><path d="M${l} ${o} V${H - u} H${B - r}"/></g>`;
    s += tx.liste.map((v) => `<text x="${X(v)}" y="${H - u + 15}" text-anchor="middle">${zahl(v, tx)}</text>`).join("");
    s += ty.liste.map((v) => `<text x="${l - 6}" y="${Y(v) + 4}" text-anchor="end">${zahl(v, ty)}</text>`).join("");
    s += `<text x="${(l + B - r) / 2}" y="${H - 8}" text-anchor="middle" style="fill:${TINTE}">${achsentext(E.a)}</text>`;
    s += `<text transform="translate(13 ${(o + H - u) / 2}) rotate(-90)" text-anchor="middle" style="fill:${TINTE}">${achsentext(E.b)}</text>`;
    // untere konvexe Hülle: was gewichtete Summen erreichen können
    const ecken = E.routen.map((z, i) => i).filter((i) => E.art[i] === 2);
    if (ecken.length > 1) s += `<polyline points="${ecken.map((i) => `${X(xs[i])},${Y(ys[i])}`).join(" ")}" fill="none" stroke="${BLAU}" stroke-width="1.5" stroke-dasharray="4 3"/>`;
    const relevant = new Set(E.relevant);
    const marke = (i) => {
      const x = X(xs[i]), y = Y(ys[i]), g = relevant.has(i) ? 5 : 3.2;
      return E.art[i] > 0
        ? `<circle cx="${x}" cy="${y}" r="${g}" fill="${BLAU}" stroke="#fff" stroke-width="1.2"/>`
        : `<path d="M${x} ${y - g - 1} L${x + g + 1} ${y} L${x} ${y + g + 1} L${x - g - 1} ${y} Z" fill="#fff" stroke="${ROT}" stroke-width="1.8"/>`;
    };
    // erst die übrigen Punkte, dann die spürbar verschiedenen obenauf
    s += E.routen.map((z, i) => (relevant.has(i) ? "" : marke(i))).join("");
    E.relevant.forEach((i, nr) => {
      const x = X(xs[i]), y = Y(ys[i]), gewaehlt = i === P.auswahl;
      s += `<circle cx="${x}" cy="${y}" r="${gewaehlt ? 10 : 8.5}" fill="${gewaehlt ? "#fff" : "none"}" stroke="${TINTE}" stroke-width="${gewaehlt ? 3 : 1.5}"/>` + marke(i) +
        `<text x="${x + 11}" y="${y - 8}" style="fill:${TINTE};font-weight:650;paint-order:stroke;stroke:#fff;stroke-width:3px">${nr + 1}</text>`;
    });
    if (P.auswahl >= 0 && !relevant.has(P.auswahl)) {
      const i = P.auswahl;
      s += `<circle cx="${X(xs[i])}" cy="${Y(ys[i])}" r="9" fill="#fff" stroke="${TINTE}" stroke-width="3"/>` + marke(i);
    }
    // unsichtbare, größere Trefferflächen für Zeiger und Finger
    s += E.routen.map((z, i) => `<circle class="punkt" data-i="${i}" cx="${X(xs[i])}" cy="${Y(ys[i])}" r="${relevant.has(i) ? 12 : 7}" fill="transparent"/>`).join("");
    svg.innerHTML = s;
  }

  function punkttext(i) {
    const E = P.ergebnis, z = E.routen[i], nr = E.relevant.indexOf(i);
    return `${nr >= 0 ? "Route " + (nr + 1) + ": " : ""}${A.format(E.a, z.a)} · ${A.format(E.b, z.b)}<br>` +
      (E.art[i] > 0 ? w("findet eine gewichtete Summe", "found by a weighted sum") : w("findet keine gewichtete Summe", "not found by any weighted sum"));
  }

  // ------------------------------------------------------------------ Tabellen und Karte

  function tabellen() {
    const E = P.ergebnis;
    const kopf = `<thead><tr><th scope="col">${w("Nr.", "No.")}</th><th scope="col">${A.name(E.a)}</th><th scope="col">${A.name(E.b)}</th><th scope="col">${w("gewichtete Summe", "weighted sum")}</th></tr></thead>`;
    const zeile = (i, nr, klickbar) => `<tr data-i="${i}" ${klickbar ? 'tabindex="0"' : ""} class="${i === P.auswahl && klickbar ? "auswahl" : ""}">
      <th scope="row">${nr}</th><td>${A.format(E.a, E.routen[i].a)}</td><td>${A.format(E.b, E.routen[i].b)}</td><td>${E.art[i] > 0 ? w("findet sie", "finds it") : w("findet sie nicht", "does not find it")}</td></tr>`;
    $("#pareto-tabelle").innerHTML = `<caption>${w("Spürbar verschiedene Routen", "Noticeably different routes")}</caption>` + kopf +
      "<tbody>" + E.relevant.map((i, nr) => zeile(i, nr + 1, true)).join("") + "</tbody>";
    $("#pareto-alle").innerHTML = kopf + "<tbody>" + E.routen.map((z, i) => zeile(i, i + 1, false)).join("") + "</tbody>";
  }

  function karte() {
    const E = P.ergebnis;
    P.ebene.clearLayers();
    if (!E || A.reiter !== "pareto") return;
    for (const i of E.relevant) {
      if (i !== P.auswahl) K.routenlinie(IUN.linie(A.netz, E.routen[i].kanten), BLAU, "8 6", 3).addTo(P.ebene);
    }
    if (P.auswahl >= 0) K.routenlinie(IUN.linie(A.netz, E.routen[P.auswahl].kanten), TINTE, "", 5).addTo(P.ebene);
  }

  function waehlen(i) {
    P.auswahl = i;
    diagramm(); tabellen(); karte();
  }

  function veraltet() {
    if (!P.ergebnis) return;
    P.ergebnis = null;
    P.ebene.clearLayers();
    $("#pareto-ergebnis").hidden = true;
    $("#pareto-status").textContent = w("Start, Ziel oder Auswahl haben sich geändert: bitte neu berechnen.",
      "Start, destination or selection have changed: please compute again.");
  }

  document.addEventListener("iun-bereit", () => {
    P.ebene = L.layerGroup().addTo(A.karte.map);
    $("#pareto-start").addEventListener("click", berechnen);
    $("#pareto-persona").addEventListener("change", (e) => { $("#pareto-b").value = VORSCHLAG[e.target.value] || "hauptstrasse"; veraltet(); });
    $("#pareto-a").addEventListener("change", veraltet);
    $("#pareto-b").addEventListener("change", veraltet);
    $("#spiel-a").addEventListener("input", zeigen);
    $("#spiel-b").addEventListener("input", zeigen);
    const svg = $("#pareto-diagramm"), tipp = $("#tipp");
    svg.addEventListener("pointermove", (e) => {
      const i = e.target.dataset && e.target.dataset.i;
      if (i === undefined) { tipp.hidden = true; return; }
      tipp.innerHTML = punkttext(+i);
      tipp.hidden = false;
      tipp.style.left = Math.min(e.clientX + 14, window.innerWidth - tipp.offsetWidth - 6) + "px";
      tipp.style.top = Math.max(6, e.clientY - tipp.offsetHeight - 10) + "px";
    });
    svg.addEventListener("pointerleave", () => { tipp.hidden = true; });
    svg.addEventListener("click", (e) => { const i = e.target.dataset && e.target.dataset.i; if (i !== undefined) waehlen(+i); });
    const zeilenwahl = (e) => {
      if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
      const tr = e.target.closest("tr[data-i]");
      if (tr) { e.preventDefault(); waehlen(+tr.dataset.i); }
    };
    $("#pareto-tabelle").addEventListener("click", zeilenwahl);
    $("#pareto-tabelle").addEventListener("keydown", zeilenwahl);
    A.beiAenderung.push(veraltet);
    A.beiReiter.push((name) => { if (name === "pareto") { auswahlen(); karte(); } else P.ebene.clearLayers(); });
  });
})();
