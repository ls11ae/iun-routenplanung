/* Eigene Grundkarte für die Webdemo: Gewässer, Grünflächen, Bahnstrecken, Hauptstraßen und
 * Ortsteilnamen aus daten/grundkarte.json (erzeugt mit werkzeuge/grundkarte.py aus
 * OpenStreetMap-Daten). So lädt die Seite keine Kartenkacheln von fremden Servern.
 * Daten: © OpenStreetMap-Mitwirkende, ODbL. */
(function () {
  "use strict";
  const G = (window.IUNGrundkarte = {});
  const w = window.IUNSprache ? window.IUNSprache.w : (de) => de;
  G.NENNUNG = `© <a href="https://www.openstreetmap.org/copyright">${w("OpenStreetMap-Mitwirkende", "OpenStreetMap contributors")}</a> (ODbL)`;

  const STIL = {
    gruen: { stroke: false, fill: true, fillColor: "#dcead0", fillOpacity: 1 },
    wasser: { stroke: false, fill: true, fillColor: "#b9d5ec", fillOpacity: 1 },
    fluss: { color: "#8fb9de", weight: 2, fill: false },
    nebenstrasse: { color: "#d9d3c6", weight: 1.5, fill: false },
    hauptstrasse: { color: "#cdc3ae", weight: 2.5, fill: false },
    bundesstrasse: { color: "#c2b597", weight: 3, fill: false },
    autobahn: { color: "#b3a484", weight: 4, fill: false },
    bahn: { color: "#6f6f6f", weight: 1.6, dashArray: "7 4", fill: false },
  };

  let ladung = null;
  /** Lädt die Grundkarte einmal (Promise mit dem GeoJSON). */
  G.laden = () => ladung || (ladung = fetch("daten/grundkarte.json").then((r) => {
    if (!r.ok) throw new Error("daten/grundkarte.json: " + r.status);
    return r.json();
  }));

  function scheibe(map, name, zIndex) {
    if (!map.getPane(name)) {
      map.createPane(name).style.zIndex = zIndex;
      map.getPane(name).style.pointerEvents = "none";
    }
    return name;
  }

  /** Zeichnet die Klassen `klassen` in eine eigene Ebene (pane) mit `zIndex`.
   *  `ueber` überschreibt den Stil, z. B. für dünne Linien über einer Rasterkarte. */
  G.ebene = function (map, daten, klassen, name, zIndex, ueber = {}) {
    const pane = scheibe(map, name, zIndex);
    return L.geoJSON(daten, {
      pane, interactive: false, renderer: L.canvas({ pane, padding: 0.3 }),
      filter: (f) => klassen.includes(f.properties.k),
      style: (f) => Object.assign({}, STIL[f.properties.k], ueber[f.properties.k] || ueber.alle || {}),
    }).addTo(map);
  };

  /** Ortsnamen: Nachbarstädte und die Namen in `auswahl` immer, alle Stadtteile ab Zoomstufe
   *  `ab.gross`, kleinere Ortsteile ab `ab.klein`. Der Name „Dortmund“ selbst entfällt. */
  G.ortsnamen = function (map, daten, name = "ortsnamen", zIndex = 640, ab = { gross: 11.5, klein: 14 }, auswahl = []) {
    const pane = scheibe(map, name, zIndex);
    const gruppe = L.layerGroup().addTo(map);
    for (const f of daten.features) {
      if (f.properties.k !== "ort") continue;
      const [lon, lat] = f.geometry.coordinates;
      const klasse = "ortsname ortsname-" + f.properties.art + (auswahl.includes(f.properties.n) ? " ortsname-auswahl" : "");
      L.marker([lat, lon], {
        pane, interactive: false, keyboard: false,
        icon: L.divIcon({ className: klasse, html: f.properties.n, iconSize: null }),
      }).addTo(gruppe);
    }
    map.getContainer().classList.add("orte-start");
    const zeigen = () => {
      const z = map.getZoom(), c = map.getContainer().classList;
      c.toggle("orte-gross", z >= ab.gross);
      c.toggle("orte-klein", z >= ab.klein);
    };
    map.on("zoomend", zeigen);
    zeigen();
    return gruppe;
  };

  /** Die übliche Grundkarte: Flächen und Linien unter den eigenen Daten, Namen darüber. */
  G.zeichnen = function (map, daten, opt = {}) {
    map.attributionControl.addAttribution(G.NENNUNG);
    G.ebene(map, daten, ["gruen", "wasser", "fluss", "nebenstrasse", "hauptstrasse", "bundesstrasse", "autobahn", "bahn"],
      "grundkarte", opt.zIndex || 200);
    if (opt.namen !== false) G.ortsnamen(map, daten);
  };
})();
