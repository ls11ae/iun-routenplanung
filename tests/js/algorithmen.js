/* Prüft die Routing-Bibliothek auf dem Radnetz: Dijkstra, bidirektionaler Dijkstra, A*, ALT
 * und CH müssen für zufällige Paare dieselbe Distanz liefern (wie „Zufällige Paare“ in der
 * Algorithmen-Ansicht). Aufruf: node tests/js/algorithmen.js [Anzahl]; Ausgabe als JSON. */
"use strict";
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const R = require("../../webdemo/js/routing.js");

const daten = path.join(__dirname, "..", "..", "webdemo", "daten");
const lies = (name) => JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(daten, name))).toString("utf8"));
const D = lies("dortmund-graph.json.gz"), G = R.makeGraph(D), CH = R.loadCH(lies("dortmund-ch.json.gz"), G);
const tabellen = { fast: R.landmarkTables(G, CH.landmarks, "fast"), quiet: R.landmarkTables(G, CH.landmarks, "quiet") };

let seed = 12345;
const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
const anzahl = +process.argv[2] || 40;
let abweichungen = 0;
const summe = { dijkstra: 0, bidir: 0, astar: 0, alt: 0, ch: 0 };
for (let i = 0; i < anzahl; i++) {
  const s = Math.floor(rnd() * G.n), t = Math.floor(rnd() * G.n);
  for (const metrik of ["fast", "quiet"]) {
    const d = R.dijkstra(G, s, t, metrik);
    const andere = { bidir: R.bidirectional(G, s, t, metrik), astar: R.astar(G, s, t, metrik), alt: R.alt(G, s, t, metrik, tabellen[metrik]) };
    if (metrik === "fast") andere.ch = R.chQuery(CH, s, t);
    for (const [name, r] of Object.entries(andere)) {
      if (r.dist !== d.dist) abweichungen++;
      if (metrik === "fast") summe[name] += r.settled;
      if (!(r.relaxed > 0) && s !== t) abweichungen++;          // der Kantenzähler muss mitlaufen
    }
    if (metrik === "fast") summe.dijkstra += d.settled;
  }
}
const tu = D.places.tu.node, phoenix = D.places.phoenix.node;
process.stdout.write(JSON.stringify({
  paare: anzahl, abweichungen,
  mittel: Object.fromEntries(Object.entries(summe).map(([k, v]) => [k, Math.round(v / anzahl)])),
  tuPhoenix: {
    dijkstra: R.dijkstra(G, tu, phoenix, "fast").settled, bidir: R.bidirectional(G, tu, phoenix, "fast").settled,
    astar: R.astar(G, tu, phoenix, "fast").settled, alt: R.alt(G, tu, phoenix, "fast", tabellen.fast).settled,
    ch: R.chQuery(CH, tu, phoenix).settled,
  },
}));
