/* Algorithmen-Ansicht: Dijkstra, bidirektionaler Dijkstra, A*, ALT und Contraction Hierarchies
 * auf dem Radnetz von Dortmund, mit Animation, Statistik je Lauf und Vergleich.
 * Übernommen aus der Demo zur Vorlesung „Algorithms and Sustainability“ (Kevin Buchin, TU Dortmund),
 * übersetzt und um Statistik und Vergleich erweitert. Kartendaten © OpenStreetMap-Mitwirkende (ODbL).
 *
 * URL-Parameter (für Folien): algo=dijkstra|bidir|astar|alt|ch|compare  metric=fast|quiet
 * s=, t= (Ort oder Knotennummer)  state=final|start|anim  ui=full|legend|compact|none
 * speed=<Faktor>  view=x0,y0,x1,y1 (Meter)  algos=<Liste> (nur diese Algorithmen anbieten) */
(async function () {
  'use strict';
  const R = self.Routing;
  const P = new URLSearchParams(location.search);
  const COL = { blau: '#0072B2', rot: '#D55E00', gruen: '#009E73', rosa: '#CC79A7', tinte: '#1b1b1b' };
  const S = self.IUNSprache, w = S.w, zahl = S.zahl;
  const NAMEN = { dijkstra: 'Dijkstra', bidir: w('Bidirektionaler Dijkstra', 'Bidirectional Dijkstra'), astar: w('A* (Luftlinie)', 'A* (straight line)'),
                  alt: w('ALT (A* mit Landmarken)', 'ALT (A* with landmarks)'), ch: w('Contraction Hierarchies', 'Contraction hierarchies'),
                  compare: w('Schnell und ruhig', 'Fast vs. quiet') };
  const KURZ = { dijkstra: 'Dijkstra', bidir: w('Bidirektional', 'Bidirectional'), astar: 'A*', alt: 'ALT', ch: 'CH', compare: w('schnell/ruhig', 'fast/quiet') };
  const ALGOS = ['dijkstra', 'bidir', 'astar', 'alt', 'ch'];
  const RATE = { dijkstra: 140, bidir: 140, astar: 140, alt: 140, ch: 1.5 };   // Knoten je Bild
  const ui = P.get('ui') || 'full';
  if (ui !== 'full') document.body.classList.add('eingebettet', 'ui-' + ui);
  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------ Daten
  async function ladeGz(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(url + ': HTTP ' + r.status);
    const buf = new Uint8Array(await r.arrayBuffer());
    if (buf[0] !== 0x1f || buf[1] !== 0x8b) return JSON.parse(new TextDecoder().decode(buf));   // schon entpackt
    if (typeof DecompressionStream === 'undefined') throw new Error('dieser Browser kann gzip-Daten nicht entpacken');
    return JSON.parse(await new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'))).text());
  }
  let D, C, STAT;
  try {
    [D, C, STAT] = await Promise.all([ladeGz('daten/dortmund-graph.json.gz'), ladeGz('daten/dortmund-ch.json.gz'),
                                      fetch('daten/radnetz-stats.json').then((r) => r.json())]);
  } catch (e) {
    $('laden').innerHTML = location.protocol === 'file:'
      ? w('Die Seite wurde direkt als Datei geöffnet.<br>Bitte im Ordner webdemo <code>python -m http.server</code> starten.',
          'The page was opened directly as a file.<br>Please start <code>python -m http.server</code> in the folder webdemo.')
      : w('Die Daten konnten nicht geladen werden (', 'The data could not be loaded (') + e.message + ').';
    return;
  }
  const G = R.makeGraph(D);
  const CH = R.loadCH(C, G);
  const n = G.n, segOff = Int32Array.from(D.segOff), segXY = Int32Array.from(D.segXY), segCls = Uint8Array.from(D.segCls);
  const nSeg = segCls.length;
  const segLen = new Float64Array(nSeg);
  for (let s = 0; s < nSeg; s++) {
    let L = 0;
    for (let k = segOff[s] + 1; k < segOff[s + 1]; k++)
      L += Math.hypot(segXY[2 * k] - segXY[2 * k - 2], segXY[2 * k + 1] - segXY[2 * k - 1]);
    segLen[s] = L;
  }
  const byCls = [[], [], [], []];
  for (let s = 0; s < nSeg; s++) byCls[segCls[s]].push(s);
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < n; i++) {
    if (G.x[i] < x0) x0 = G.x[i]; if (G.x[i] > x1) x1 = G.x[i];
    if (G.y[i] < y0) y0 = G.y[i]; if (G.y[i] > y1) y1 = G.y[i];
  }
  // Gitter für „nächster Knoten“
  const CELL = 150, gw = Math.ceil((x1 - x0) / CELL) + 1, gh = Math.ceil((y1 - y0) / CELL) + 1;
  const cellOf = (x, y) => Math.min(gh - 1, Math.max(0, Math.floor((y - y0) / CELL))) * gw +
                           Math.min(gw - 1, Math.max(0, Math.floor((x - x0) / CELL)));
  const cellStart = new Int32Array(gw * gh + 1), cellNodes = new Int32Array(n);
  for (let i = 0; i < n; i++) cellStart[cellOf(G.x[i], G.y[i]) + 1]++;
  for (let c = 0; c < gw * gh; c++) cellStart[c + 1] += cellStart[c];
  { const f = cellStart.slice(0, gw * gh); for (let i = 0; i < n; i++) cellNodes[f[cellOf(G.x[i], G.y[i])]++] = i; }
  function nearest(x, y) {
    const cx = Math.floor((x - x0) / CELL), cy = Math.floor((y - y0) / CELL);
    let best = -1, bd = Infinity;
    for (let r = 0; r < 60 && (best < 0 || (r - 1) * CELL < Math.sqrt(bd)); r++) {
      for (let j = cy - r; j <= cy + r; j++) for (let i = cx - r; i <= cx + r; i++) {
        if (i < 0 || j < 0 || i >= gw || j >= gh) continue;
        if (Math.max(Math.abs(i - cx), Math.abs(j - cy)) !== r) continue;
        const c = j * gw + i;
        for (let k = cellStart[c]; k < cellStart[c + 1]; k++) {
          const v = cellNodes[k], d = (G.x[v] - x) ** 2 + (G.y[v] - y) ** 2;
          if (d < bd) { bd = d; best = v; }
        }
      }
    }
    return best;
  }

  // ------------------------------------------------------------ Ausschnitt und Zeichenflächen
  const feld = $('karten');
  const cv = { base: $('grund'), search: $('suche'), top: $('oben') };
  const ctx = { base: cv.base.getContext('2d'), search: cv.search.getContext('2d'), top: cv.top.getContext('2d') };
  let W = 0, H = 0, dpr = 1;
  const view = { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, scale: 1 };
  function fit(bx0, by0, bx1, by1) {
    view.cx = (bx0 + bx1) / 2; view.cy = (by0 + by1) / 2;
    view.scale = Math.min(W / (bx1 - bx0), H / (by1 - by0)) * 0.97;
  }
  const SX = (x) => (x - view.cx) * view.scale + W / 2;
  const SY = (y) => H / 2 - (y - view.cy) * view.scale;
  function resize(refit) {
    dpr = window.devicePixelRatio || 1;
    W = feld.clientWidth; H = feld.clientHeight;
    for (const k of Object.keys(cv)) {
      cv[k].width = Math.round(W * dpr); cv[k].height = Math.round(H * dpr);
      ctx[k].setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    if (refit) {
      const v = (P.get('view') || '').split(',').map(Number);
      if (v.length === 4 && v.every(isFinite)) fit(v[0], v[1], v[2], v[3]); else fit(x0, y0, x1, y1);
    }
  }
  const lineScale = () => Math.max(0.6, Math.min(2.5, view.scale * 40));   // dickere Linien beim Hineinzoomen

  function addPiece(c, s) {
    const a = segOff[s], b = segOff[s + 1];
    c.moveTo(SX(segXY[2 * a]), SY(segXY[2 * a + 1]));
    for (let k = a + 1; k < b; k++) c.lineTo(SX(segXY[2 * k]), SY(segXY[2 * k + 1]));
  }
  function pieceOf(e) { const s = G.sg[e]; return s >= 0 ? s : -s - 1; }

  function drawBase() {
    const c = ctx.base, ls = lineScale();
    c.fillStyle = '#ffffff'; c.fillRect(0, 0, W, H);
    c.lineCap = 'round'; c.lineJoin = 'round';
    const styles = [[3, '#e1e3e5', 0.55], [0, '#cfd2d6', 0.7], [2, '#bcd8be', 0.9], [1, '#aeb2b8', 1.5]];
    for (const [cls, col, lw] of styles) {
      c.beginPath();
      for (const s of byCls[cls]) addPiece(c, s);
      c.strokeStyle = col; c.lineWidth = lw * ls; c.stroke();
    }
  }

  // ------------------------------------------------------------ Zustand und Rechnen
  const st = {
    algo: P.get('algo') || 'dijkstra', metric: P.get('metric') || 'fast',
    s: -1, t: -1, res: null, shown: 0, anim: false, speed: parseFloat(P.get('speed') || '1'),
    tables: {}, tabellenMs: {}, zeit: null,
  };
  const placeNode = (v) => (D.places[v] ? D.places[v].node : (v !== null && v !== '' && isFinite(+v) ? +v : -1));
  st.s = placeNode(P.get('s') || 'tu');
  st.t = placeNode(P.get('t') || 'phoenix');

  function tablesFor(metric) {          // Landmarken-Tabellen: 2 Dijkstra-Läufe je Landmarke, im Browser
    if (!st.tables[metric]) {
      const t0 = performance.now();
      st.tables[metric] = R.landmarkTables(G, CH.landmarks, metric);
      st.tabellenMs[metric] = performance.now() - t0;
    }
    return st.tables[metric];
  }
  function edgesOfPath(path, metric) {
    const w = G.w[metric], es = [];
    for (let i = 0; i + 1 < path.length; i++) {
      const u = path[i], v = path[i + 1];
      let best = -1;
      for (let e = G.off[u]; e < G.off[u + 1]; e++) if (G.to[e] === v && (best < 0 || w[e] < w[best])) best = e;
      es.push(best);
    }
    return es;
  }
  function routeInfo(edges) {
    let len = 0, busy = 0, time = 0;
    for (const e of edges) {
      const L = segLen[pieceOf(e)];
      len += L; time += G.w.fast[e];
      if (G.w.quiet[e] >= 1.5 * G.w.fast[e]) busy += L;
    }
    return { km: len / 1000, busyKm: busy / 1000, min: time / 600 };
  }
  /** Ein Lauf eines Algorithmus (ohne Zeichnen). */
  function lauf(algo, metric, s, t) {
    if (algo === 'dijkstra') return R.dijkstra(G, s, t, metric);
    if (algo === 'bidir') return R.bidirectional(G, s, t, metric);
    if (algo === 'astar') return R.astar(G, s, t, metric);
    if (algo === 'alt') return R.alt(G, s, t, metric, tablesFor(metric));
    if (algo === 'ch') return metric === 'fast' ? R.chQuery(CH, s, t) : null;
    return null;
  }
  /** Median der Laufzeit in Millisekunden. Kurze Läufe werden mehrfach am Stück gemessen,
   *  weil die Uhr des Browsers nur auf Bruchteile von Millisekunden genau ist. */
  function messen(f) {
    let a = performance.now(); f();
    const einzel = performance.now() - a;
    const reps = Math.max(1, Math.min(200, Math.ceil(15 / Math.max(einzel, 0.05))));
    const zeiten = [];
    for (let b = 0; b < 5; b++) {
      a = performance.now();
      for (let i = 0; i < reps; i++) f();
      zeiten.push((performance.now() - a) / reps);
    }
    zeiten.sort((x, y) => x - y);
    return { ms: zeiten[2], laeufe: 5 * reps };
  }
  const NOTIZ_CH = w('Die Contraction Hierarchy wurde nur für die Reisezeit vorberechnet. Ein anderes Gewicht braucht eine neue Vorberechnung (oder eine anpassbare CH).',
    'The contraction hierarchy was precomputed for travel time only. Another weight needs a new preprocessing (or a customizable CH).');
  function compute() {
    const { algo, metric, s, t } = st;
    st.zeit = null;
    if (s < 0 || t < 0) { st.res = null; return; }
    if (algo === 'compare') {
      const f = R.dijkstra(G, s, t, 'fast'), q = R.dijkstra(G, s, t, 'quiet');
      const fe = edgesOfPath(f.path, 'fast'), qe = edgesOfPath(q.path, 'quiet');
      st.res = { compare: true, fast: { edges: fe, info: routeInfo(fe) }, quiet: { edges: qe, info: routeInfo(qe) },
                 settled: 0, order: new Int32Array(0), side: new Uint8Array(0) };
      return;
    }
    const r = lauf(algo, metric, s, t);
    if (!r) { st.res = { note: NOTIZ_CH }; return; }
    r.edges = algo === 'ch' ? r.origEdges : edgesOfPath(r.path, metric);
    r.info = routeInfo(r.edges);
    st.res = r;
  }
  function vorberechnung(algo, metric) {
    if (algo === 'alt') {
      tablesFor(metric);
      return w(`${CH.landmarks.length} Landmarken, ${2 * CH.landmarks.length} Dijkstra-Läufe, ${zahl(st.tabellenMs[metric] / 1000, 2)} s (in diesem Browser)`,
               `${CH.landmarks.length} landmarks, ${2 * CH.landmarks.length} Dijkstra runs, ${zahl(st.tabellenMs[metric] / 1000, 2)} s (in this browser)`);
    }
    if (algo === 'ch') return w(`${zahl(STAT.ch.shortcuts)} Shortcuts, ${zahl(STAT.ch.seconds, 1)} s (vorab berechnet)`,
                                `${zahl(STAT.ch.shortcuts)} shortcuts, ${zahl(STAT.ch.seconds, 1)} s (precomputed)`);
    return w('keine', 'none');
  }

  // ------------------------------------------------------------ Suche zeichnen
  function drawSearch(k0, k1) {
    const r = st.res;
    if (!r || !r.order) return;
    const c = ctx.search, ls = lineScale();
    c.lineCap = 'round'; c.lineJoin = 'round';
    for (const side of [0, 1]) {
      c.beginPath();
      const sc = new Path2D();
      let anySc = false;
      for (let i = k0; i < k1; i++) {
        if (r.side[i] !== side) continue;
        const u = r.order[i];
        if (st.algo === 'ch') {                  // die beiden Suchbäume „bergauf“
          const e = side === 0 ? r.pF[u] : r.pB[u];
          if (e >= 0) {
            if (e < G.m) addPiece(c, pieceOf(e));
            else { sc.moveTo(SX(G.x[CH.eFrom[e]]), SY(G.y[CH.eFrom[e]])); sc.lineTo(SX(G.x[CH.eTo[e]]), SY(G.y[CH.eTo[e]])); anySc = true; }
          }
        } else if (side === 0) {
          for (let e = G.off[u]; e < G.off[u + 1]; e++) addPiece(c, pieceOf(e));
        } else {
          for (let j = G.roff[u]; j < G.roff[u + 1]; j++) addPiece(c, pieceOf(G.redge[j]));
        }
      }
      const col = side === 0 ? COL.blau : COL.rot;
      c.strokeStyle = col; c.globalAlpha = st.algo === 'ch' ? 0.95 : 0.7;
      c.lineWidth = (st.algo === 'ch' ? 2.2 : 1.25) * ls; c.stroke();
      if (anySc) {
        c.setLineDash([6, 4]); c.lineWidth = 1.6 * Math.min(1.5, ls); c.globalAlpha = 0.9; c.stroke(sc); c.setLineDash([]);
      }
      c.globalAlpha = 1;
      if (st.algo === 'ch') {               // abgearbeitete Knoten als Punkte
        c.fillStyle = col;
        for (let i = k0; i < k1; i++) {
          if (r.side[i] !== side) continue;
          const u = r.order[i];
          c.beginPath(); c.arc(SX(G.x[u]), SY(G.y[u]), 2.6 * Math.min(1.6, ls), 0, 2 * Math.PI); c.fill();
        }
      }
    }
  }
  function drawRoute(c, edges, col, lw, strich) {
    const ls = Math.min(1.6, lineScale());
    c.lineCap = 'round'; c.lineJoin = 'round';
    c.beginPath();
    for (const e of edges) addPiece(c, pieceOf(e));
    c.strokeStyle = '#ffffff'; c.lineWidth = (lw + 3) * ls; c.stroke();
    c.setLineDash(strich || []);
    c.strokeStyle = col; c.lineWidth = lw * ls; c.stroke();
    c.setLineDash([]);
  }
  const SCHRIFT = 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif';
  function label(c, text, x, y, opts) {
    opts = opts || {};
    c.font = `${opts.bold ? '700 ' : ''}${opts.size || 13}px ${SCHRIFT}`;
    c.textAlign = opts.align || 'left'; c.textBaseline = 'middle';
    c.lineWidth = 4; c.strokeStyle = 'rgba(255,255,255,0.95)'; c.strokeText(text, x, y);
    c.fillStyle = opts.color || COL.tinte; c.fillText(text, x, y);
  }
  function marker(c, v, txt, eckig) {
    const x = SX(G.x[v]), y = SY(G.y[v]);
    c.beginPath();
    if (eckig) c.rect(x - 8, y - 8, 16, 16); else c.arc(x, y, 9, 0, 2 * Math.PI);
    c.fillStyle = eckig ? '#ffffff' : COL.tinte; c.fill(); c.lineWidth = 2.5; c.strokeStyle = eckig ? COL.tinte : '#ffffff'; c.stroke();
    c.font = `700 11px ${SCHRIFT}`;
    c.fillStyle = eckig ? COL.tinte : '#ffffff'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(txt, x, y + 0.5);
  }
  const nameOf = (v) => { for (const p of Object.values(D.places)) if (p.node === v) return S.ort(p.label); return null; };
  function drawTop() {
    const c = ctx.top;
    c.clearRect(0, 0, W, H);
    const r = st.res, done = r && !st.anim;
    if (done && r.compare) {
      drawRoute(c, r.quiet.edges, COL.gruen, 4.5, [10, 6]);
      drawRoute(c, r.fast.edges, COL.blau, 3);
    } else if (done && r.edges && r.edges.length) {
      drawRoute(c, r.edges, COL.tinte, 3.5);
    }
    if (st.algo === 'alt' && CH.landmarks) {
      for (const L of CH.landmarks) {
        const x = SX(G.x[L]), y = SY(G.y[L]);
        c.beginPath(); c.moveTo(x, y - 8); c.lineTo(x + 8, y); c.lineTo(x, y + 8); c.lineTo(x - 8, y); c.closePath();
        c.fillStyle = COL.rosa; c.fill(); c.lineWidth = 2; c.strokeStyle = COL.tinte; c.stroke();
      }
    }
    for (const [key, p] of Object.entries(D.places)) {
      if (key === 'city' || key === 'stadium') continue;
      const v = p.node;
      if (v === st.s || v === st.t) continue;
      const x = SX(G.x[v]), y = SY(G.y[v]);
      c.beginPath(); c.arc(x, y, 3, 0, 2 * Math.PI); c.fillStyle = COL.tinte; c.fill();
      label(c, S.ort(p.label), x + 6, y - 9, { size: ui === 'compact' ? 14 : 12, color: '#4d4f53' });
    }
    if (st.s >= 0) marker(c, st.s, 'S', false);
    if (st.t >= 0) marker(c, st.t, w('Z', 'D'), true);
    const fs = ui === 'compact' ? 15 : 13;
    if (st.s >= 0 && nameOf(st.s)) label(c, nameOf(st.s), SX(G.x[st.s]) - 13, SY(G.y[st.s]) + 17, { bold: true, align: 'right', size: fs });
    if (st.t >= 0 && nameOf(st.t)) label(c, nameOf(st.t), SX(G.x[st.t]) + 13, SY(G.y[st.t]) + 17, { bold: true, size: fs });
  }
  function redrawAll() {
    drawBase();
    ctx.search.clearRect(0, 0, W, H);
    if (st.res && st.res.order) drawSearch(0, Math.floor(st.shown));
    drawTop();
    updateStats();
  }

  // ------------------------------------------------------------ Texte
  const strich = (col, gestrichelt) => `<span class="strich" style="background:${gestrichelt ? `repeating-linear-gradient(90deg, ${col} 0 6px, transparent 6px 10px)` : col}"></span>`;
  function updateStats() {
    const r = st.res, ort = (v) => nameOf(v) || w('Knoten ', 'node ') + v;
    let html = '', leg = '', zeichen = [];
    if (r && r.note) html = `<p>${r.note}</p>`;
    else if (r && r.compare) {
      const zeile = (col, name, i, gestr) => `${strich(col, gestr)}${name}: <b>${zahl(i.min, 1)} min</b>, ${zahl(i.km, 1)} km, ` +
        w(`davon ${zahl(i.busyKm, 1)} km auf Hauptstraßen`, `${zahl(i.busyKm, 1)} km of it on main roads`);
      const beide = `${zeile(COL.blau, w('am schnellsten', 'fastest'), r.fast.info)}<br>${zeile(COL.gruen, w('ruhiger', 'quieter'), r.quiet.info, true)}`;
      html = `<p><b>${NAMEN.compare}</b> ${w('(jeweils Dijkstra)', '(Dijkstra in both cases)')}<br>${beide}</p>`;
      leg = `<b>${ort(st.s)} → ${ort(st.t)} ${w('mit dem Rad', 'by bike')}</b><br>${beide}`;
    } else if (r) {
      const k = Math.floor(st.shown), fertig = !st.anim;
      const zeit = st.zeit ? `${zahl(st.zeit.ms, st.zeit.ms < 10 ? 2 : 1)} ms <span class="leise">(${w('Median', 'median')}, ${st.zeit.laeufe} ${w('Läufe', 'runs')})</span>`
        : (fertig ? `<span class="leise">${w('wird gemessen …', 'measuring …')}</span>` : '–');
      const von = w('von', 'of');
      html = `<dl class="statistik">
        <dt>${w('Algorithmus', 'Algorithm')}</dt><dd>${NAMEN[st.algo]}</dd>
        <dt>${w('Gewicht', 'Weight')}</dt><dd>${st.metric === 'fast' ? w('schnell (Reisezeit)', 'fast (travel time)') : w('ruhig', 'quiet')}</dd>
        <dt>${w('abgearbeitete Knoten', 'settled nodes')}</dt><dd>${zahl(k)}${fertig ? ` <span class="leise">${von} ${zahl(G.n)}</span>` : ''}</dd>
        <dt>${w('relaxierte Kanten', 'relaxed edges')}</dt><dd>${fertig ? zahl(r.relaxed) : '–'}</dd>
        <dt>${w('Laufzeit', 'Running time')}</dt><dd>${zeit}</dd>
        <dt>Route</dt><dd>${fertig && r.info ? `${zahl(r.info.min, 1)} min · ${zahl(r.info.km, 2)} km` : '–'}</dd>
        <dt>${w('Vorberechnung', 'Preprocessing')}</dt><dd>${vorberechnung(st.algo, st.metric)}</dd></dl>`;
      const zwei = st.algo === 'bidir' || st.algo === 'ch';
      zeichen = zwei ? [`${strich(COL.blau)} ${w('vom Start aus', 'from the start')}`, `${strich(COL.rot)} ${w('vom Ziel aus', 'from the destination')}`]
        : [`${strich(COL.blau)} ${w('durchsuchte Straßen', 'searched streets')}`];
      if (st.algo === 'ch') zeichen.push(`${strich(COL.blau, true)} ${w('Shortcuts in den beiden Suchbäumen', 'shortcuts in the two search trees')}`);
      if (st.algo === 'alt') zeichen.push(`<span style="color:${COL.rosa}">◆</span> ${w('Landmarken (weit auseinander gewählt)', 'landmarks (chosen far apart)')}`);
      zeichen.push(`${strich(COL.tinte)} ${w('gefundener Weg', 'path found')}`);
      leg = `<b>${NAMEN[st.algo]}</b><br>${w('abgearbeitete Knoten', 'settled nodes')}: <b>${zahl(k)}</b> ${von} ${zahl(G.n)}<br>${zeichen.slice(0, -1).join(' &nbsp;')}`;
    } else html = `<p class="leise">${w('Bitte Start und Ziel wählen.', 'Please choose start and destination.')}</p>`;
    $('statistik').innerHTML = html;
    $('zeichen').innerHTML = zeichen.map((z) => `<li>${z}</li>`).join('');
    $('legende').innerHTML = leg;
    $('mini-text').innerHTML = leg;
    for (const b of document.querySelectorAll('[data-algo]')) b.setAttribute('aria-pressed', b.dataset.algo === st.algo);
    for (const b of document.querySelectorAll('[data-gewicht]')) b.setAttribute('aria-pressed', b.dataset.gewicht === st.metric);
    for (const b of document.querySelectorAll('[data-tempo]')) b.setAttribute('aria-pressed', +b.dataset.tempo === st.speed);
    $('wahl-start').value = nameOf(st.s) ? st.s : 'frei';
    $('wahl-ziel').value = nameOf(st.t) ? st.t : 'frei';
  }

  // ------------------------------------------------------------ Laufen lassen
  let raf = 0, messung = 0;
  function zeitNehmen() {            // nach dem Zeichnen, damit die Seite nicht stockt
    clearTimeout(messung);
    const { algo, metric, s, t } = st;
    if (!st.res || !st.res.order || st.res.compare) return;
    messung = setTimeout(() => {
      if (st.algo !== algo || st.s !== s || st.t !== t || st.metric !== metric) return;
      st.zeit = messen(() => lauf(algo, metric, s, t));
      updateStats();
    }, 60);
  }
  function run(animated) {
    cancelAnimationFrame(raf);
    compute();
    ctx.search.clearRect(0, 0, W, H);
    const r = st.res;
    if (!r || !r.order || !animated || r.settled === 0) {
      st.anim = false; st.shown = r && r.order ? r.settled : 0;
      if (r && r.order) drawSearch(0, r.settled);
      drawTop(); updateStats(); zeitNehmen(); return;
    }
    st.anim = true; st.shown = 0; drawTop();
    const rate = (RATE[st.algo] || 100) * st.speed;
    const step = () => {
      const k0 = Math.floor(st.shown);
      st.shown = Math.min(r.settled, st.shown + rate);
      const k1 = Math.floor(st.shown);
      drawSearch(k0, k1);
      if (k1 >= r.settled) { st.anim = false; drawTop(); zeitNehmen(); }
      updateStats();
      if (st.anim) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  }
  function clearSearch() {
    cancelAnimationFrame(raf); st.anim = false; st.res = null; st.shown = 0;
    ctx.search.clearRect(0, 0, W, H); drawTop(); updateStats();
  }

  // ------------------------------------------------------------ Vergleich
  const mal = (x) => w(`${zahl(x, 1)}-mal`, `${zahl(x, 1)}×`);
  const gewicht = (metric) => (metric === 'fast' ? w('schnell', 'fast') : w('ruhig', 'quiet'));
  const SPALTEN = [w('Algorithmus', 'Algorithm'), w('abgearbeitete Knoten', 'settled nodes'), w('relaxierte Kanten', 'relaxed edges'),
    w('weniger Knoten als Dijkstra', 'fewer nodes than Dijkstra'), w('Laufzeit (ms)', 'running time (ms)'),
    w('schneller als Dijkstra (Laufzeit)', 'faster than Dijkstra (running time)')];
  const NUR_REISEZEIT = w('nur für die Reisezeit vorberechnet', 'precomputed for travel time only');
  const kopf = (spalten) => `<thead><tr>${spalten.map((s, i) => `<th scope="col"${i ? '' : ' style="text-align:left"'}>${s}</th>`).join('')}</tr></thead>`;
  function alleVergleichen() {
    const { metric, s, t } = st;
    if (s < 0 || t < 0) return;
    $('vergleich').innerHTML = `<p>${w('Rechnet …', 'Computing …')}</p>`;
    setTimeout(() => {
      const zeilen = [];
      let basis = null;
      for (const algo of ALGOS) {
        const r = lauf(algo, metric, s, t);
        if (!r) { zeilen.push(`<tr><th scope="row">${KURZ[algo]}</th><td colspan="5" style="text-align:left">${NUR_REISEZEIT}</td></tr>`); continue; }
        const z = messen(() => lauf(algo, metric, s, t));
        if (!basis) basis = { dist: r.dist, ms: z.ms, settled: r.settled };
        zeilen.push(`<tr><th scope="row" title="${vorberechnung(algo, metric)}">${KURZ[algo]}</th><td>${zahl(r.settled)}</td><td>${zahl(r.relaxed)}</td>` +
          `<td>${mal(basis.settled / r.settled)}</td><td>${zahl(z.ms, z.ms < 10 ? 2 : 1)}</td><td>${mal(basis.ms / z.ms)}</td><td>${r.dist === basis.dist ? w('✓ gleich', '✓ same') : '✗ ' + r.dist}</td></tr>`);
      }
      const ort = (v) => nameOf(v) || w('Knoten ', 'node ') + v;
      $('vergleich').innerHTML = `<div class="tabellenrahmen"><table class="kennzahlen">
        <caption>${ort(s)} → ${ort(t)}, ${w('Gewicht', 'weight')} ${gewicht(metric)}: ${w('Reisezeit', 'travel time')} ${zahl(basis.dist / 600, 1)} min</caption>
        ${kopf([...SPALTEN, w('Distanz', 'distance')])}
        <tbody>${zeilen.join('')}</tbody></table></div>
        <p class="leise">${w('Vorberechnung', 'Preprocessing')}: ALT ${vorberechnung('alt', metric)}; CH ${vorberechnung('ch', metric)}.</p>`;
    }, 30);
  }

  // Zufallszahlen wie im Skript zu den Folien (gleicher Startwert, also dieselben Paare)
  let seed = 12345;
  const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  let zufallLaeuft = false;
  function zufaelligePaare() {
    if (zufallLaeuft) return;
    zufallLaeuft = true;
    const anzahl = +$('zufall-anzahl').value, metric = st.metric;
    const algos = ALGOS.filter((a) => a !== 'ch' || metric === 'fast');
    if (algos.includes('alt')) tablesFor(metric);
    const summe = Object.fromEntries(algos.map((a) => [a, { settled: 0, relaxed: 0, ms: 0 }]));
    let fertig = 0, abweichungen = 0;
    const block = () => {
      const bis = Math.min(anzahl, fertig + 4);
      for (; fertig < bis; fertig++) {
        const s = Math.floor(rnd() * G.n), t = Math.floor(rnd() * G.n);
        let dist = null;
        for (const a of algos) {
          const t0 = performance.now(), r = lauf(a, metric, s, t), ms = performance.now() - t0;
          summe[a].settled += r.settled; summe[a].relaxed += r.relaxed; summe[a].ms += ms;
          if (dist === null) dist = r.dist; else if (r.dist !== dist) abweichungen++;
        }
      }
      if (fertig < anzahl) { $('zufall-ergebnis').innerHTML = `<p>${w(`Rechnet … ${fertig} von ${anzahl} Paaren`, `Computing … ${fertig} of ${anzahl} pairs`)}</p>`; setTimeout(block, 0); return; }
      zufallLaeuft = false;
      const d = summe.dijkstra;
      $('zufall-ergebnis').innerHTML = `<div class="tabellenrahmen"><table class="kennzahlen">
        <caption>${w(`${zahl(anzahl)} zufällige Paare, Gewicht ${gewicht(metric)}: Mittelwerte je Anfrage`,
                     `${zahl(anzahl)} random pairs, weight ${gewicht(metric)}: averages per query`)}</caption>
        ${kopf(SPALTEN)}
        <tbody>${algos.map((a) => `<tr><th scope="row">${KURZ[a]}</th><td>${zahl(summe[a].settled / anzahl)}</td><td>${zahl(summe[a].relaxed / anzahl)}</td>` +
          `<td>${mal(d.settled / summe[a].settled)}</td><td>${zahl(summe[a].ms / anzahl, 2)}</td><td>${mal(d.ms / summe[a].ms)}</td></tr>`).join('')}</tbody></table></div>
        <p>${abweichungen === 0
          ? w(`<b>✓ Prüfung bestanden:</b> Alle ${algos.length} Algorithmen liefern für alle ${zahl(anzahl)} Paare dieselbe Distanz.`,
              `<b>✓ Check passed:</b> all ${algos.length} algorithms return the same distance for all ${zahl(anzahl)} pairs.`)
          : w(`<b>✗ ${abweichungen} Abweichungen</b> zwischen den Algorithmen. Das dürfte nicht vorkommen.`,
              `<b>✗ ${abweichungen} differences</b> between the algorithms. This should not happen.`)}</p>
        ${metric === 'fast' ? '' : `<p class="leise">${w('CH fehlt', 'CH missing')}: ${NUR_REISEZEIT}.</p>`}`;
    };
    $('zufall-ergebnis').innerHTML = `<p>${w('Rechnet …', 'Computing …')}</p>`;
    setTimeout(block, 30);
  }

  // ------------------------------------------------------------ Bedienung
  const keep = P.get('algos') ? P.get('algos').split(',') : null;
  const knoepfe = [...ALGOS, 'compare'].filter((a) => !keep || keep.includes(a))
    .map((a) => `<button class="knopf" data-algo="${a}" aria-pressed="false" title="${NAMEN[a]}">${KURZ[a]}</button>`).join('');
  $('algos').innerHTML = knoepfe; $('mini-algos').innerHTML = knoepfe;
  for (const b of document.querySelectorAll('[data-algo]')) b.onclick = () => { st.algo = b.dataset.algo; run(st.algo !== 'compare'); };
  for (const b of document.querySelectorAll('[data-gewicht]')) b.onclick = () => { st.metric = b.dataset.gewicht; run(false); };
  for (const b of document.querySelectorAll('[data-tempo]')) b.onclick = () => { st.speed = +b.dataset.tempo; updateStats(); };
  for (const b of document.querySelectorAll('[data-tat]')) {
    b.onclick = () => { if (b.dataset.tat === 'lauf') run(true); else if (b.dataset.tat === 'ergebnis') run(false); else clearSearch(); };
  }
  $('alle').onclick = alleVergleichen;
  $('zufall').onclick = zufaelligePaare;
  for (const art of ['start', 'ziel']) {
    const wahl = $('wahl-' + art);
    wahl.innerHTML = Object.values(D.places).map((p) => `<option value="${p.node}">${S.ort(p.label)}</option>`).join('') +
      `<option value="frei">${w('Punkt auf der Karte', 'point on the map')}</option>`;
    wahl.onchange = () => { if (wahl.value === 'frei') return; st[art === 'start' ? 's' : 't'] = +wahl.value; run(false); };
  }
  const osm = D.meta.osm_base;
  $('stand').textContent = w(`, Stand ${osm.slice(8, 10)}.${osm.slice(5, 7)}.${osm.slice(0, 4)}: ${zahl(G.n)} Knoten, ${zahl(G.m)} gerichtete Kanten, ${zahl(D.meta.km)} km`,
                             `, as of ${osm.slice(0, 10)}: ${zahl(G.n)} nodes, ${zahl(G.m)} directed edges, ${zahl(D.meta.km)} km`);

  function zoom(f, px, py) {          // um den Bildpunkt (px, py) zoomen
    const mx = (px - W / 2) / view.scale + view.cx, my = view.cy - (py - H / 2) / view.scale;
    view.scale *= f;
    view.cx = mx - (px - W / 2) / view.scale; view.cy = my + (py - H / 2) / view.scale;
    redrawAll();
  }
  $('zoom-rein').onclick = () => zoom(1.5, W / 2, H / 2);
  $('zoom-raus').onclick = () => zoom(1 / 1.5, W / 2, H / 2);
  $('zoom-alles').onclick = () => { resize(true); redrawAll(); };

  const finger = new Map();
  let down = null, dragged = false, nextIsT = false, kniff = 0;
  const ort = (ev) => { const r = cv.top.getBoundingClientRect(); return { x: ev.clientX - r.left, y: ev.clientY - r.top }; };
  cv.top.addEventListener('pointerdown', (ev) => {
    finger.set(ev.pointerId, ort(ev));
    cv.top.setPointerCapture(ev.pointerId);
    if (finger.size === 1) { const p = ort(ev); down = { x: p.x, y: p.y, cx: view.cx, cy: view.cy }; dragged = false; }
    else { const [a, b] = [...finger.values()]; kniff = Math.hypot(a.x - b.x, a.y - b.y); dragged = true; down = null; }
  });
  cv.top.addEventListener('pointermove', (ev) => {
    if (!finger.has(ev.pointerId)) return;
    finger.set(ev.pointerId, ort(ev));
    if (finger.size >= 2) {           // zwei Finger: zoomen
      const [a, b] = [...finger.values()], d = Math.hypot(a.x - b.x, a.y - b.y);
      if (kniff > 0 && d > 0) zoom(d / kniff, (a.x + b.x) / 2, (a.y + b.y) / 2);
      kniff = d;
      return;
    }
    if (!down) return;
    const p = ort(ev), dx = p.x - down.x, dy = p.y - down.y;
    if (!dragged && Math.hypot(dx, dy) < 6) return;
    dragged = true;
    view.cx = down.cx - dx / view.scale; view.cy = down.cy + dy / view.scale;
    redrawAll();
  });
  const los = (ev) => {
    const p = ort(ev);
    if (finger.size === 1 && down && !dragged && ev.type === 'pointerup') {
      const v = nearest((p.x - W / 2) / view.scale + view.cx, view.cy - (p.y - H / 2) / view.scale);
      if (ev.shiftKey || nextIsT) { st.t = v; nextIsT = false; run(st.algo !== 'compare'); }
      else { st.s = v; st.t = -1; nextIsT = true; clearSearch(); }
    }
    finger.delete(ev.pointerId);
    down = null; kniff = 0;
  };
  cv.top.addEventListener('pointerup', los);
  cv.top.addEventListener('pointercancel', los);
  cv.top.addEventListener('wheel', (ev) => { ev.preventDefault(); const p = ort(ev); zoom(Math.exp(-ev.deltaY * 0.0015), p.x, p.y); }, { passive: false });
  window.addEventListener('keydown', (ev) => {
    // in Folien eingebettet: Pfeiltasten an reveal.js weitergeben
    const nav = { ArrowRight: 'next', PageDown: 'next', ' ': 'next', ArrowLeft: 'prev', PageUp: 'prev' };
    if (nav[ev.key] && window.parent !== window) {
      ev.preventDefault();
      window.parent.postMessage(JSON.stringify({ method: nav[ev.key], args: [] }), '*');
      return;
    }
    if (['INPUT', 'SELECT', 'BUTTON', 'TEXTAREA'].includes(ev.target.tagName)) return;
    if (ev.key === 'r' || ev.key === 'Enter') run(true);
    if (ev.key === '0') { resize(true); redrawAll(); }
  });
  let rt = 0;
  new ResizeObserver(() => { clearTimeout(rt); rt = setTimeout(() => { if (feld.clientWidth !== W || feld.clientHeight !== H) { resize(true); redrawAll(); } }, 120); }).observe(feld);

  // ------------------------------------------------------------ Start
  $('laden').remove();
  resize(true);
  drawBase();
  const state = P.get('state') || 'final';
  if (state === 'start') { drawTop(); updateStats(); }
  else run(state === 'anim');
  window.demoReady = true;
})();
