/* Rechnet Routen mit dem JavaScript-Kern der Webdemo (für den Vergleich mit Python).
 *
 * Aufruf:  node tests/js/routen.js < anfragen.json
 * Eingabe: [{"persona": "rad", "von": [lat, lon], "nach": [lat, lon]}, ...]
 * Ausgabe: {"routen": [...], "summen": {...}}; je Anfrage Start- und Zielknoten
 *          (Positionen in netz.json), Kosten, Kennzahlen und die Zahl der abgeschlossenen
 *          Knoten für Dijkstra und A*; dazu die Summe jedes Kriteriums über alle Kanten.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const IUN = require("../../webdemo/js/kern.js");

const web = path.join(__dirname, "..", "..", "webdemo");
const netz = IUN.netzAufbauen(JSON.parse(fs.readFileSync(path.join(web, "daten", "netz.json"), "utf8")));
const daten = JSON.parse(fs.readFileSync(path.join(web, "personas.json"), "utf8"));
const personas = Object.fromEntries(daten.personas.map((p) => [p.id, p]));
const kriterien = daten.kriterien.map((k) => k.id);
const anfragen = JSON.parse(fs.readFileSync(0, "utf8"));

const masken = {};
const ergebnis = anfragen.map((q) => {
  const p = personas[q.persona];
  const kosten = IUN.kostenFeld(netz, p);
  const maske = masken[p.id] || (masken[p.id] = IUN.groessteKomponente(netz, kosten));
  const start = IUN.naechsterKnoten(netz, q.von[0], q.von[1], maske);
  const ziel = IUN.naechsterKnoten(netz, q.nach[0], q.nach[1], maske);
  const d = IUN.kuerzesterWeg(netz, kosten, start, ziel);
  const a = IUN.kuerzesterWeg(netz, kosten, start, ziel,
    { astern: true, untergrenze: 1 / p.tempo + ((p.gewichte || {}).laenge || 0) });
  return {
    start, ziel, kosten: d.kosten, kosten_astern: a.kosten,
    abgeschlossen: d.abgeschlossen, abgeschlossen_astern: a.abgeschlossen,
    komponente: maske.reduce((s, x) => s + x, 0),
    kennzahlen: IUN.bewerten(netz, d.kanten, p, kriterien),
  };
});
const summen = { kanten: netz.M };
for (const id of kriterien) summen[id] = IUN.werte(netz, id).reduce((a, b) => a + b, 0);
process.stdout.write(JSON.stringify({ routen: ergebnis, summen }));
