/* Kartenhilfen für die Webdemo: Leaflet-Karte mit der eigenen Grundkarte (grundkarte.js) und
 * eine Zeichenebene (Canvas), auf der das Wegenetz gezeichnet wird. Es werden keine
 * Kartenkacheln von fremden Servern geladen.
 */
(function () {
  "use strict";
  const K = (window.IUNKarte = {});

  /** Ergänzt Web-Mercator-Koordinaten (0..1) für Knoten und Zwischenpunkte. */
  K.mercator = function (netz) {
    const mx = (lon) => (lon + 180) / 360;
    const my = (lat) => { const s = Math.sin(lat * Math.PI / 180); return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI); };
    netz.mx = new Float64Array(netz.n); netz.my = new Float64Array(netz.n);
    for (let i = 0; i < netz.n; i++) { netz.mx[i] = mx(netz.lon[i]); netz.my[i] = my(netz.lat[i]); }
    const g = netz.geo;
    netz.gx = new Float64Array(g.length / 2); netz.gy = new Float64Array(g.length / 2);
    for (let k = 0; k < netz.m; k++) {
      let x = netz.lon[netz.U[k]], y = netz.lat[netz.U[k]];
      for (let j = netz.geoStart[k]; j < netz.geoStart[k + 1]; j += 2) {
        x += g[j] / 1e6; y += g[j + 1] / 1e6;
        netz.gx[j / 2] = mx(x); netz.gy[j / 2] = my(y);
      }
    }
    let w = Infinity, s = Infinity, o = -Infinity, nd = -Infinity;
    for (let i = 0; i < netz.n; i++) {
      w = Math.min(w, netz.lon[i]); o = Math.max(o, netz.lon[i]);
      s = Math.min(s, netz.lat[i]); nd = Math.max(nd, netz.lat[i]);
    }
    netz.grenzen = [[s, w], [nd, o]];
  };

  /** Zeichenebene: ruft `zeichne(ctx, p)` nach jedem Verschieben oder Zoomen auf.
   *  p.x(mx) und p.y(my) rechnen Mercator-Koordinaten in Bildpunkte der Ebene um. */
  K.Leinwand = L.Layer.extend({
    initialize: function (zeichne, opt) { L.setOptions(this, opt); this._zeichne = zeichne; },
    onAdd: function (map) {
      this._canvas = L.DomUtil.create("canvas", "leinwand leaflet-zoom-hide");
      this.getPane().appendChild(this._canvas);
      map.on("moveend zoomend resize", this.neu, this);
      this.neu();
    },
    onRemove: function (map) {
      map.off("moveend zoomend resize", this.neu, this);
      L.DomUtil.remove(this._canvas);
    },
    /** Maße und Umrechnung der Ebene für den aktuellen Kartenausschnitt. */
    lage: function () {
      const map = this._map, g = map.getSize(), rand = 0.3;
      const rx = Math.round(g.x * rand), ry = Math.round(g.y * rand);
      const ecke = map.containerPointToLayerPoint([-rx, -ry]);
      const ursprung = map.getPixelOrigin(), s = 256 * Math.pow(2, map.getZoom());
      const ox = ursprung.x + ecke.x, oy = ursprung.y + ecke.y;
      return { ecke, w: g.x + 2 * rx, h: g.y + 2 * ry, zoom: map.getZoom(), x: (mx) => mx * s - ox, y: (my) => my * s - oy };
    },
    neu: function () {
      if (!this._map) return;
      const p = (this._p = this.lage()), c = this._canvas, dpr = window.devicePixelRatio || 1;
      L.DomUtil.setPosition(c, p.ecke);
      c.width = Math.round(p.w * dpr); c.height = Math.round(p.h * dpr);
      c.style.width = p.w + "px"; c.style.height = p.h + "px";
      const ctx = c.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this._zeichne(ctx, p);
    },
    /** Zeichnet etwas zusätzlich, ohne die Ebene zu leeren (für die Animation). */
    dazu: function (zeichne) {
      if (!this._map || !this._p) return;
      zeichne(this._canvas.getContext("2d"), this._p);
    },
  });

  /** Legt eine Karte an: eigene Grundkarte, darüber das Wegenetz aus den Daten. */
  K.karte = function (element, netz) {
    const grenzen = L.latLngBounds(netz.grenzen);
    const map = L.map(element, { minZoom: 12, maxZoom: 19, maxBounds: grenzen.pad(0.5), zoomSnap: 0.5 });
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    // Anfangs der Ausschnitt mit den vier voreingestellten Orten (das Netz reicht weiter)
    map.fitBounds(L.latLngBounds(Object.values(netz.orte)).pad(0.25));
    const zustand = { map, hervorheben: "" };
    map.createPane("netz").style.zIndex = 250;        // über der Grundkarte, unter den Routen
    const netzEbene = new K.Leinwand((ctx, p) => K.netzZeichnen(ctx, p, netz, zustand), { pane: "netz" });
    zustand.netzEbene = netzEbene;
    netzEbene.addTo(map);
    IUNGrundkarte.laden().then((daten) => IUNGrundkarte.zeichnen(map, daten))
      .catch(() => map.attributionControl.addAttribution(IUNGrundkarte.NENNUNG));
    zustand.setHervorheben = function (id) { zustand.hervorheben = id; netzEbene.neu(); };
    return zustand;
  };

  const SYMBOL = {
    querung_ohne_ampel: { form: "dreieck", farbe: "#D55E00" },
    querung_ampel_stumm: { form: "ring", farbe: "#0072B2" },
    querung_akustisch: { form: "kreis", farbe: "#0072B2" },
    querung_ohne_bodenindikator: { form: "raute", farbe: "#CC79A7" },
    bordstein: { form: "quadrat", farbe: "#D55E00" },
  };
  K.SYMBOL = SYMBOL;

  K.symbol = function (ctx, form, x, y, r) {
    ctx.beginPath();
    if (form === "dreieck") { ctx.moveTo(x, y - r * 1.2); ctx.lineTo(x + r * 1.1, y + r * 0.8); ctx.lineTo(x - r * 1.1, y + r * 0.8); ctx.closePath(); }
    else if (form === "quadrat") ctx.rect(x - r, y - r, 2 * r, 2 * r);
    else if (form === "raute") { ctx.moveTo(x, y - r * 1.3); ctx.lineTo(x + r * 1.3, y); ctx.lineTo(x, y + r * 1.3); ctx.lineTo(x - r * 1.3, y); ctx.closePath(); }
    else ctx.arc(x, y, r, 0, 2 * Math.PI);
    if (form === "ring") { ctx.fillStyle = "#fff"; ctx.fill(); ctx.lineWidth = 2; ctx.stroke(); }
    else { ctx.fill(); ctx.lineWidth = 1; ctx.strokeStyle = "#fff"; ctx.stroke(); }
  };

  /** Zeichnet das Wegenetz und hebt auf Wunsch ein Kriterium hervor. */
  K.netzZeichnen = function (ctx, p, netz, zustand) {
    ctx.clearRect(0, 0, p.w, p.h);
    const { U, V, mx, my, gx, gy, geoStart, art, F } = netz;
    const sichtbar = (k) => {
      const x1 = p.x(mx[U[k]]), x2 = p.x(mx[V[k]]), y1 = p.y(my[U[k]]), y2 = p.y(my[V[k]]);
      return !((x1 < -40 && x2 < -40) || (x1 > p.w + 40 && x2 > p.w + 40) || (y1 < -40 && y2 < -40) || (y1 > p.h + 40 && y2 > p.h + 40));
    };
    const pfad = (k) => {
      ctx.moveTo(p.x(mx[U[k]]), p.y(my[U[k]]));
      for (let j = geoStart[k] >> 1; j < geoStart[k + 1] >> 1; j++) ctx.lineTo(p.x(gx[j]), p.y(gy[j]));
      ctx.lineTo(p.x(mx[V[k]]), p.y(my[V[k]]));
    };
    const treppe = netz.flaggen.indexOf("treppe");
    ctx.lineCap = "round"; ctx.lineJoin = "round";

    {
      const z = p.zoom, basis = z >= 17 ? 2 : z >= 15 ? 1.3 : z >= 14 ? 0.9 : 0.6;
      const stile = [
        { test: (k) => art[k] === 0 && !(F[k] >> treppe & 1), farbe: "#b9b9b4", breite: basis * 0.8 },
        { test: (k) => (F[k] >> treppe & 1) === 1, farbe: "#8a6d3b", breite: basis * 1.3, strich: [2, 3] },
        { test: (k) => art[k] === 1, farbe: "#8f8f8a", breite: basis * 1.5 },
        { test: (k) => art[k] === 2, farbe: "#55555a", breite: basis * 2.6 },
      ];
      for (const s of stile) {
        ctx.beginPath();
        for (let k = 0; k < netz.m; k++) if (s.test(k) && sichtbar(k)) pfad(k);
        ctx.strokeStyle = s.farbe; ctx.lineWidth = s.breite; ctx.setLineDash(s.strich || []);
        ctx.stroke();
      }
      ctx.setLineDash([]);
    }

    const id = zustand.hervorheben;
    if (!id) return;
    const bit = netz.flaggen.indexOf(id);
    if (bit >= 0) {
      ctx.beginPath();
      for (let k = 0; k < netz.m; k++) if ((F[k] >> bit & 1) && sichtbar(k)) pfad(k);
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 6; ctx.globalAlpha = 0.7; ctx.stroke();
      ctx.strokeStyle = "#D55E00"; ctx.lineWidth = 3; ctx.globalAlpha = 1; ctx.stroke();
      return;
    }
    const arten = id === "querungen" ? ["querung_ohne_ampel", "querung_ampel_stumm", "querung_akustisch"] : [id];
    const r = p.zoom >= 16 ? 5 : p.zoom >= 14 ? 3.5 : 2.2;
    for (const a of arten) {
      const w = IUN.werte(netz, a), s = SYMBOL[a], gezeichnet = new Uint8Array(netz.n);
      ctx.fillStyle = s.farbe; ctx.strokeStyle = s.farbe;
      for (let e = 0; e < netz.M; e++) {
        const v = netz.nach[e];
        if (!w[e] || gezeichnet[v]) continue;
        const x = p.x(mx[v]), y = p.y(my[v]);
        if (x < 0 || y < 0 || x > p.w || y > p.h) continue;
        gezeichnet[v] = 1;
        ctx.strokeStyle = s.farbe;
        K.symbol(ctx, s.form, x, y, r);
      }
    }
  };

  /** Marke für Start ("S", rund) und Ziel ("Z", eckig): Buchstabe und Form, nicht nur Farbe. */
  K.marke = function (art, latlng, ziehbar) {
    const start = art === "start";
    return L.marker(latlng, {
      draggable: !!ziehbar, keyboard: true, zIndexOffset: 1000,
      title: start ? "Start" : "Ziel", alt: start ? "Start" : "Ziel",
      icon: L.divIcon({ className: "", html: `<div class="marke ${start ? "marke-start" : "marke-ziel"}">${start ? "S" : "Z"}</div>`, iconSize: [28, 28], iconAnchor: [14, 14] }),
    });
  };

  /** Route als Linie mit weißem Rand; Strichart unterscheidet die Personas zusätzlich zur Farbe. */
  K.routenlinie = function (punkte, farbe, strich, breite = 5, mitRand = true) {
    const linie = L.polyline(punkte, { color: farbe, weight: breite, opacity: 1, dashArray: strich || null, lineCap: K.kappe(strich), interactive: false });
    return mitRand ? L.layerGroup([K.routenrand(punkte, breite), linie]) : linie;
  };
  K.routenrand = (punkte, breite = 5) => L.polyline(punkte, { color: "#fff", weight: breite + 4, opacity: 0.85, interactive: false });
  /** Gepunktete Linien (erster Wert des Strichmusters höchstens 2) bekommen runde Enden. */
  K.kappe = (strich) => (!strich || parseFloat(strich) <= 2 ? "round" : "butt");
})();
