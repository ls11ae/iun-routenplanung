/* Kern der Persona-Ansicht: Netz lesen, Kosten je Persona, Pareto-Front.
 *
 * Kürzeste Wege rechnet die Bibliothek routing.js (dieselbe wie in der Algorithmen-Ansicht);
 * hier wird das Wegenetz in deren Form gebracht und das Kostenfeld einer Persona gebildet.
 * Läuft im Browser (window.IUN, routing.js vorher laden) und in Node.js (require).
 * Die Kriterien selbst werden in Python berechnet (wegenetz/routen_hilfen.py) und mit
 * wegenetz/export_webdemo.py exportiert; hier werden sie nur gelesen. Der Aufbau der
 * Datei netz.json ist dort beschrieben.
 */
(function (root, factory) {
  const knoten = typeof module === "object" && module.exports;
  const api = factory(knoten ? require("./routing.js") : root.Routing);
  if (knoten) module.exports = api;
  else root.IUN = api;
})(typeof self !== "undefined" ? self : this, function (R) {
  "use strict";

  const ERDRADIUS = 6371009; // Meter, wie in OSMnx
  const QUERUNG = { querung_ohne_ampel: 1, querung_ampel_stumm: 2, querung_akustisch: 3 };

  // ------------------------------------------------------------------ Netz

  /** Baut aus dem Inhalt von netz.json Felder für die Suche (gerichtete Kanten). */
  function netzAufbauen(roh) {
    const n = roh.knoten.x.length, m = roh.kanten.u.length;
    const lon = new Float64Array(n), lat = new Float64Array(n), hoehe = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      lon[i] = roh.ursprung[0] + roh.knoten.x[i] / 1e6;
      lat[i] = roh.ursprung[1] + roh.knoten.y[i] / 1e6;
      hoehe[i] = roh.knoten.h[i] / 10;
    }
    const K = roh.kanten;
    const geoStart = new Int32Array(m + 1);
    for (let i = 0; i < m; i++) geoStart[i + 1] = geoStart[i] + 2 * K.gn[i];

    // Gerichtete Kanten, sortiert nach Anfangsknoten (start[u] .. start[u+1])
    const grad = new Int32Array(n + 1);
    let M = 0;
    for (let i = 0; i < m; i++) {
      grad[K.u[i]]++; M++;
      if (K.rueck[i] >= 0) { grad[K.v[i]]++; M++; }
    }
    const start = new Int32Array(n + 1);
    for (let i = 0; i < n; i++) start[i + 1] = start[i] + grad[i];
    const frei = start.slice(0, n);
    const von = new Int32Array(M), nach = new Int32Array(M), kante = new Int32Array(M);
    const gegen = new Uint8Array(M), code = new Uint8Array(M);
    for (let i = 0; i < m; i++) {
      let e = frei[K.u[i]]++;
      von[e] = K.u[i]; nach[e] = K.v[i]; kante[e] = i; code[e] = K.hin[i];
      if (K.rueck[i] >= 0) {
        e = frei[K.v[i]]++;
        von[e] = K.v[i]; nach[e] = K.u[i]; kante[e] = i; gegen[e] = 1; code[e] = K.rueck[i];
      }
    }
    // Eingehende Kanten je Knoten (für die Rückwärtssuche)
    const einStart = new Int32Array(n + 1);
    for (let e = 0; e < M; e++) einStart[nach[e] + 1]++;
    for (let i = 0; i < n; i++) einStart[i + 1] += einStart[i];
    const einFrei = einStart.slice(0, n), ein = new Int32Array(M);
    for (let e = 0; e < M; e++) ein[einFrei[nach[e]]++] = e;

    const laenge = new Float64Array(M);
    for (let e = 0; e < M; e++) laenge[e] = K.l[kante[e]] / 10;

    // Dasselbe Netz in der Form, die routing.js erwartet (Kanten nach Anfangsknoten sortiert,
    // eingehende Kanten als Liste, Koordinaten in Metern); Gewichte kommen je Anfrage dazu.
    const lat0 = roh.ursprung[1], kx = Math.cos(lat0 * Math.PI / 180) * 111319.49;
    const G = {
      n, m: M, off: start, to: nach, from: von, roff: einStart, redge: ein, w: {},
      x: Float64Array.from(lon, (l) => (l - roh.ursprung[0]) * kx),
      y: Float64Array.from(lat, (b) => (b - lat0) * 111132.95),
    };

    return {
      G, n, m, M, lon, lat, hoehe, start, von, nach, kante, gegen, code, einStart, ein, laenge,
      flaggen: roh.flaggen, F: K.f, art: K.art, U: K.u, V: K.v, geo: roh.geo, geoStart,
      orte: roh.orte, quellen: roh.quellen, erzeugt: roh.erzeugt, _werte: { laenge },
    };
  }

  /** Werte eines Kriteriums für alle gerichteten Kanten (Meter oder Stück). */
  function werte(netz, id) {
    if (netz._werte[id]) return netz._werte[id];
    const { M, kante, code, laenge } = netz, w = new Float64Array(M);
    const bit = netz.flaggen.indexOf(id);
    if (bit >= 0) {
      for (let e = 0; e < M; e++) if (netz.F[kante[e]] >> bit & 1) w[e] = laenge[e];
    } else if (id in QUERUNG) {
      for (let e = 0; e < M; e++) if ((code[e] & 3) === QUERUNG[id]) w[e] = 1;
    } else if (id === "querung_ohne_bodenindikator") {
      for (let e = 0; e < M; e++) if (code[e] & 4) w[e] = 1;
    } else if (id === "bordstein") {
      for (let e = 0; e < M; e++) if (code[e] & 8) w[e] = 1;
    } else if (id === "anstieg") {
      for (let e = 0; e < M; e++) w[e] = Math.max(0, netz.hoehe[netz.nach[e]] - netz.hoehe[netz.von[e]]);
    } else {
      throw new Error("Unbekanntes Kriterium: " + id);
    }
    return (netz._werte[id] = w);
  }

  /** Sekunden je gerichteter Kante mit dem Tempo der Persona. */
  function zeitFeld(netz, persona) {
    const { M, laenge } = netz, t = new Float64Array(M);
    const schieben = persona.tempo_schieben ? werte(netz, "rad_schieben") : null;
    for (let e = 0; e < M; e++) {
      const s = schieben ? schieben[e] : 0;
      t[e] = (laenge[e] - s) / persona.tempo;
      if (s) t[e] += s / persona.tempo_schieben;
    }
    return t;
  }

  /** Markiert gesperrte Kanten der Persona in `feld` mit Infinity. */
  function sperren(netz, persona, feld) {
    for (const id of persona.sperren || []) {
      const w = werte(netz, id);
      for (let e = 0; e < netz.M; e++) if (w[e] > 0) feld[e] = Infinity;
    }
    return feld;
  }

  /** Kosten je gerichteter Kante: Zeit + Summe (Gewicht mal Kriterium); Infinity = gesperrt. */
  function kostenFeld(netz, persona) {
    const k = zeitFeld(netz, persona);
    for (const id of Object.keys(persona.gewichte || {})) {
      const g = persona.gewichte[id];
      if (!g) continue;
      const w = werte(netz, id);
      for (let e = 0; e < netz.M; e++) k[e] += g * w[e];
    }
    return sperren(netz, persona, k);
  }

  /** Feld für ein einzelnes Kriterium ("zeit" oder eine Kriterien-ID), mit den Sperren der Persona. */
  function kriteriumFeld(netz, persona, id) {
    const feld = id === "zeit" ? zeitFeld(netz, persona) : Float64Array.from(werte(netz, id));
    return sperren(netz, persona, feld);
  }

  function luftlinie(netz, a, b) {
    const p1 = netz.lat[a] * Math.PI / 180, p2 = netz.lat[b] * Math.PI / 180;
    const dl = (netz.lon[b] - netz.lon[a]) * Math.PI / 180;
    const x = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
    return 2 * ERDRADIUS * Math.asin(Math.sqrt(x));
  }

  /** Knoten des größten stark zusammenhängenden Teils, der mit `kosten` benutzbar ist (Tarjan). */
  function groessteKomponente(netz, kosten) {
    const { n, start, nach } = netz;
    const index = new Int32Array(n).fill(-1), tief = new Int32Array(n), komp = new Int32Array(n).fill(-1);
    const stapel = new Int32Array(n), aufStapel = new Uint8Array(n);
    const aufruf = new Int32Array(n), zeiger = new Int32Array(n);
    let zaehler = 0, sp = 0, nKomp = 0, besteGroesse = 0, beste = -1;
    for (let wurzel = 0; wurzel < n; wurzel++) {
      if (index[wurzel] >= 0) continue;
      let ap = 0;
      aufruf[ap++] = wurzel; zeiger[wurzel] = start[wurzel];
      index[wurzel] = tief[wurzel] = zaehler++; stapel[sp++] = wurzel; aufStapel[wurzel] = 1;
      while (ap > 0) {
        const u = aufruf[ap - 1];
        if (zeiger[u] < start[u + 1]) {
          const e = zeiger[u]++;
          if (kosten[e] === Infinity) continue;
          const v = nach[e];
          if (index[v] < 0) {
            index[v] = tief[v] = zaehler++; stapel[sp++] = v; aufStapel[v] = 1;
            zeiger[v] = start[v]; aufruf[ap++] = v;
          } else if (aufStapel[v] && index[v] < tief[u]) tief[u] = index[v];
        } else {
          ap--;
          if (ap > 0 && tief[u] < tief[aufruf[ap - 1]]) tief[aufruf[ap - 1]] = tief[u];
          if (tief[u] === index[u]) {
            let groesse = 0, w;
            do { w = stapel[--sp]; aufStapel[w] = 0; komp[w] = nKomp; groesse++; } while (w !== u);
            if (groesse > besteGroesse) { besteGroesse = groesse; beste = nKomp; }
            nKomp++;
          }
        }
      }
    }
    const maske = new Uint8Array(n);
    for (let i = 0; i < n; i++) if (komp[i] === beste) maske[i] = 1;
    return maske;
  }

  /** Nächster Knoten zu (lat, lon); mit `maske` nur unter den dort markierten Knoten. */
  function naechsterKnoten(netz, lat, lon, maske) {
    const c = Math.cos(lat * Math.PI / 180);
    let beste = -1, d2 = Infinity;
    for (let i = 0; i < netz.n; i++) {
      if (maske && !maske[i]) continue;
      const dy = netz.lat[i] - lat, dx = (netz.lon[i] - lon) * c, d = dy * dy + dx * dx;
      if (d < d2) { d2 = d; beste = i; }
    }
    return beste;
  }

  // ------------------------------------------------------------------ Dijkstra und A*

  /**
   * Kürzester Weg von `start` nach `ziel` (Knotennummern) für das Kostenfeld `kosten`
   * (ein Wert je gerichteter Kante, Infinity = gesperrt). Gerechnet wird mit routing.js.
   * opt.astern: A* mit der Luftlinie als Schätzung; opt.untergrenze = Kosten je Meter,
   *   die jede Kante mindestens hat (z. B. 1 / Tempo), damit die Schätzung nie zu groß ist.
   * Ergebnis: Kosten, Kanten der Route, abgearbeitete Knoten und relaxierte Kanten.
   */
  function kuerzesterWeg(netz, kosten, start, ziel, opt = {}) {
    let schaetzung = null;
    if (opt.astern) {
      const faktor = (opt.untergrenze || 0) * 0.999;   // Längen sind auf Dezimeter gerundet
      const cache = new Float64Array(netz.n).fill(-1);
      schaetzung = (v) => (cache[v] >= 0 ? cache[v] : (cache[v] = faktor * luftlinie(netz, v, ziel)));
    }
    const r = R.search(netz.G, start, ziel, kosten, schaetzung);
    return {
      kosten: r.dist, kanten: r.dist < Infinity ? pfadKanten(netz, r.parent, start, ziel) : null,
      abgeschlossen: r.settled, relaxiert: r.relaxed, reihenfolge: r.order,
    };
  }

  function pfadKanten(netz, vor, start, ziel) {
    const kanten = [];
    for (let v = ziel; v !== start;) { const e = vor[v]; kanten.push(e); v = netz.von[e]; }
    return Int32Array.from(kanten.reverse());
  }

  /** Summe eines Feldes entlang einer Route (Liste gerichteter Kanten). */
  function summe(feld, kanten) {
    let s = 0;
    for (let i = 0; i < kanten.length; i++) s += feld[kanten[i]];
    return s;
  }

  /** Kennzahlen einer Route für eine Persona: Zeit, Kosten und alle Kriterien. */
  function bewerten(netz, kanten, persona, kriterien) {
    const k = { zeit: summe(zeitFeld(netz, persona), kanten), kosten: summe(kostenFeld(netz, persona), kanten) };
    for (const id of kriterien) k[id] = summe(werte(netz, id), kanten);
    return k;
  }

  /** Verlauf einer Route als Liste [lat, lon] mit den Zwischenpunkten der Kanten. */
  function linie(netz, kanten) {
    if (!kanten.length) return [];
    const punkte = [[netz.lat[netz.von[kanten[0]]], netz.lon[netz.von[kanten[0]]]]];
    const geo = netz.geo;
    for (let i = 0; i < kanten.length; i++) {
      const e = kanten[i], k = netz.kante[e], u = netz.U[k];
      const a = netz.geoStart[k], b = netz.geoStart[k + 1];
      if (b > a) {
        const teil = [];
        let x = netz.lon[u], y = netz.lat[u];
        for (let j = a; j < b; j += 2) {
          x += geo[j] / 1e6; y += geo[j + 1] / 1e6;
          teil.push([y, x]);
        }
        if (netz.gegen[e]) teil.reverse();
        for (const p of teil) punkte.push(p);
      }
      punkte.push([netz.lat[netz.nach[e]], netz.lon[netz.nach[e]]]);
    }
    return punkte;
  }

  // ------------------------------------------------------------------ Pareto-Front

  /**
   * Alle Pareto-optimalen Routen für zwei Kriterien A und B (Felder je gerichteter Kante,
   * Infinity = gesperrt): zweikriterieller Label-Setting-Algorithmus (Martins 1984).
   *
   * Marken (a, b) werden lexikografisch geordnet abgearbeitet. Dann ist eine Marke an
   * einem Knoten genau dann nicht dominiert, wenn ihr b kleiner ist als jedes b, das an
   * diesem Knoten schon abgeschlossen wurde. Zusätzlich werden Marken verworfen, die das
   * Ziel nachweislich nicht mehr unterbieten können (untere Schranken aus zwei
   * Rückwärtssuchen). Mit toleranz = 0 ist das Ergebnis exakt.
   *
   * Ergebnis: { routen: [{a, b, kanten}], marken, abgeschlossen, abgebrochen }
   */
  function paretoFront(netz, A, B, start, ziel, opt = {}) {
    const tol = opt.toleranz || 0, maxMarken = opt.maxMarken || 20e6;
    const { n, nach } = netz;
    const offen = new Float64Array(netz.M);      // gemeinsame Sperren beider Kriterien
    for (let e = 0; e < netz.M; e++) offen[e] = (A[e] === Infinity || B[e] === Infinity) ? Infinity : 0;
    const mitSperre = (X) => { const f = Float64Array.from(X); for (let e = 0; e < netz.M; e++) if (offen[e]) f[e] = Infinity; return f; };
    A = mitSperre(A); B = mitSperre(B);
    const uA = R.allDistances(netz.G, ziel, A, true);      // untere Schranken bis zum Ziel
    const uB = R.allDistances(netz.G, ziel, B, true);
    if (uA[start] === Infinity) return { routen: [], marken: 0, abgeschlossen: 0, abgebrochen: false };

    // Größtes sinnvolles a: das kleinste a unter allen Wegen mit kleinstem b
    const eps = 1e-9 * (1 + uB[start]);
    const eng = new Float64Array(netz.M);
    for (let e = 0; e < netz.M; e++) {
      eng[e] = (B[e] < Infinity && Math.abs(uB[nach[e]] + B[e] - uB[netz.von[e]]) <= eps) ? A[e] : Infinity;
    }
    const aMax = kuerzesterWeg(netz, eng, start, ziel).kosten * (1 + 1e-9) + 1e-9;

    let platz = 1 << 16, anzahl = 0;
    let LA = new Float64Array(platz), LB = new Float64Array(platz);
    let LK = new Int32Array(platz), LV = new Int32Array(platz), LE = new Int32Array(platz);
    const neu = (a, b, knoten, vorMarke, kante) => {
      if (anzahl === platz) {
        platz *= 2;
        const w = (alt, Typ) => { const f = new Typ(platz); f.set(alt); return f; };
        LA = w(LA, Float64Array); LB = w(LB, Float64Array);
        LK = w(LK, Int32Array); LV = w(LV, Int32Array); LE = w(LE, Int32Array);
      }
      LA[anzahl] = a; LB[anzahl] = b; LK[anzahl] = knoten; LV[anzahl] = vorMarke; LE[anzahl] = kante;
      return anzahl++;
    };
    // Halde über Markennummern, geordnet nach (a, b)
    let H = new Int32Array(1 << 16), hn = 0;
    const kleiner = (i, j) => LA[i] < LA[j] || (LA[i] === LA[j] && LB[i] < LB[j]);
    const hPush = (m) => {
      if (hn === H.length) { const g = new Int32Array(2 * hn); g.set(H); H = g; }
      let i = hn++;
      while (i > 0) { const p = (i - 1) >> 1; if (!kleiner(m, H[p])) break; H[i] = H[p]; i = p; }
      H[i] = m;
    };
    const hPop = () => {
      const oben = H[0], letzte = H[--hn];
      let i = 0;
      for (;;) {
        let c = 2 * i + 1;
        if (c >= hn) break;
        if (c + 1 < hn && kleiner(H[c + 1], H[c])) c++;
        if (!kleiner(H[c], letzte)) break;
        H[i] = H[c]; i = c;
      }
      if (hn > 0) H[i] = letzte;
      return oben;
    };

    const minB = new Float64Array(n).fill(Infinity);   // kleinstes abgeschlossenes b je Knoten
    const routen = [];
    let abgeschlossen = 0, abgebrochen = false;
    hPush(neu(0, 0, start, -1, -1));
    while (hn > 0) {
      const m = hPop(), a = LA[m], b = LB[m], u = LK[m];
      if (minB[u] <= b + tol) continue;                       // am Knoten dominiert
      if (u !== ziel && minB[ziel] <= b + uB[u] + tol) continue; // kann das Ziel nicht mehr verbessern
      minB[u] = b; abgeschlossen++;
      if (u === ziel) {
        const kanten = [];
        for (let x = m; LV[x] >= 0; x = LV[x]) kanten.push(LE[x]);
        routen.push({ a, b, kanten: Int32Array.from(kanten.reverse()) });
        continue;
      }
      for (let e = netz.start[u]; e < netz.start[u + 1]; e++) {
        if (A[e] === Infinity) continue;
        const v = nach[e], na = a + A[e], nb = b + B[e];
        if (na + uA[v] > aMax) continue;
        if (minB[v] <= nb + tol) continue;
        if (minB[ziel] <= nb + uB[v] + tol) continue;
        hPush(neu(na, nb, v, m, e));
      }
      if (anzahl > maxMarken) { abgebrochen = true; break; }
    }
    return { routen, marken: anzahl, abgeschlossen, abgebrochen };
  }

  /**
   * Welche Punkte der Pareto-Front findet eine gewichtete Summe? Genau die auf der
   * unteren konvexen Hülle. Erwartet Punkte sortiert nach a aufsteigend (b absteigend).
   * Ergebnis je Punkt: 2 = Ecke der Hülle, 1 = auf einer Hüllenkante, 0 = nicht gefunden.
   */
  function gestuetzt(punkte) {
    const kreuz = (o, p, q) => (p.a - o.a) * (q.b - o.b) - (p.b - o.b) * (q.a - o.a);
    const huelle = [];
    for (let i = 0; i < punkte.length; i++) {
      while (huelle.length >= 2 &&
             kreuz(punkte[huelle[huelle.length - 2]], punkte[huelle[huelle.length - 1]], punkte[i]) <= 0) huelle.pop();
      huelle.push(i);
    }
    const art = new Array(punkte.length).fill(0);
    for (const i of huelle) art[i] = 2;
    for (let h = 0; h + 1 < huelle.length; h++) {
      const p = punkte[huelle[h]], q = punkte[huelle[h + 1]];
      const mass = Math.abs(q.a - p.a) * Math.abs(q.b - p.b) || 1;
      for (let i = huelle[h] + 1; i < huelle[h + 1]; i++) {
        if (Math.abs(kreuz(p, q, punkte[i])) <= 1e-9 * mass) art[i] = 1;
      }
    }
    return art;
  }

  /**
   * Dünnt die Pareto-Menge aus, damit nur spürbar verschiedene Routen bleiben.
   * 1. Entfernt Routen, zu denen es eine fast ebenso gute im ersten Kriterium gibt
   *    (höchstens ta schlechter), die im zweiten mindestens tb spart.
   * 2. Behält dann, nach dem ersten Kriterium sortiert, nur Routen, die gegenüber der
   *    zuletzt behaltenen mindestens tb sparen.
   * Hintergrund: Parallele Wege (Straße und daneben eigens erfasster Radweg) erzeugen
   * viele Pareto-optimale Routen, die sich praktisch nicht unterscheiden.
   * Ergebnis: Positionen der behaltenen Routen.
   */
  function relevante(routen, ta, tb) {
    const rest = [];
    for (let i = 0; i < routen.length; i++) {
      const z = routen[i];
      if (!routen.some((o) => o.a <= z.a + ta && o.b <= z.b - tb && tb > 0)) rest.push(i);
    }
    rest.sort((i, j) => routen[i].a - routen[j].a || routen[i].b - routen[j].b);
    const behalten = [];
    for (const i of rest) {
      if (!behalten.length || tb <= 0 || routen[i].b <= routen[behalten[behalten.length - 1]].b - tb) behalten.push(i);
    }
    return behalten;
  }

  return {
    netzAufbauen, werte, zeitFeld, kostenFeld, kriteriumFeld, sperren, luftlinie,
    groessteKomponente, naechsterKnoten, kuerzesterWeg, summe, bewerten, linie,
    paretoFront, gestuetzt, relevante,
  };
});
