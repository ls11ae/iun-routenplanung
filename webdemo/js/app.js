/* Webdemo: gemeinsamer Zustand (Netz, Personas, Start und Ziel) und der Reiter
 * „Routen vergleichen“. Der Reiter „Pareto-Front“ steht in pareto.js und benutzt
 * window.APP. Kürzeste Wege rechnet routing.js (Dijkstra), siehe kern.js.
 */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const K = window.IUNKarte;

  const A = (window.APP = {
    netz: null, personas: [], kriterien: [], kennzahlen: [], karte: null, karten: [],
    start: null, ziel: null, setzen: null, reiter: "routen",
    aktiv: new Set(["fuss", "rad"]), eigene: null,
    beiAenderung: [],      // Funktionen, die nach einer Änderung von Start oder Ziel laufen
    beiReiter: [],         // Funktionen, die nach einem Wechsel des Reiters laufen
  });

  // ------------------------------------------------------------------ Hilfen

  const de = (x, stellen = 0) => x.toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen });
  A.de = de;
  A.kriterium = (id) => A.kriterien.find((k) => k.id === id);
  A.name = (id) => (id === "zeit" ? "Zeit" : id === "kosten" ? "Kosten (Zeit + Aufschläge)" : A.kriterium(id).name);

  /** Wert einer Kennzahl als Text mit Einheit. */
  A.format = function (id, wert) {
    if (wert == null || !isFinite(wert)) return "–";
    if (id === "zeit" || id === "kosten") {
      const m = wert / 60;
      return m >= 100 ? `${Math.floor(m / 60)} h ${Math.round(m % 60)} min` : `${de(m, 1)} min`;
    }
    if (id === "laenge") return wert >= 1000 ? `${de(wert / 1000, 2)} km` : `${de(wert)} m`;
    if (A.kriterium(id).einheit === "Stück") return de(Math.round(wert));
    return `${de(wert)} m`;
  };

  A.strichprobe = (p, breite = 46) =>
    `<svg class="strichprobe" width="${breite}" height="12" aria-hidden="true"><line x1="2" y1="6" x2="${breite - 2}" y2="6" stroke="${p.farbe}" stroke-width="4" stroke-linecap="${K.kappe(p.strich)}" ${p.strich ? `stroke-dasharray="${p.strich}"` : ""}/></svg>`;

  A.meldung = function (text, fehler) {
    const m = $("#meldung");
    m.hidden = !text;
    m.innerHTML = text || "";
    m.classList.toggle("fehler", !!fehler);
  };

  A.allePersonas = () => A.personas.concat(A.eigene ? [A.eigene] : []);
  A.persona = (id) => A.allePersonas().find((p) => p.id === id);

  /** Kostenfeld und größte zusammenhängende Komponente einer Persona (zwischengespeichert). */
  const speicher = new Map();
  A.feld = function (p) {
    const schluessel = JSON.stringify([p.tempo, p.tempo_schieben, p.sperren, p.gewichte]);
    let f = speicher.get(schluessel);
    if (!f) {
      const kosten = IUN.kostenFeld(A.netz, p);
      f = { kosten, maske: IUN.groessteKomponente(A.netz, kosten) };
      if (speicher.size >= 24) speicher.delete(speicher.keys().next().value);
      speicher.set(schluessel, f);
    }
    return f;
  };

  function abstand(punkt, knoten) {
    const c = Math.cos(punkt.lat * Math.PI / 180);
    const dy = (A.netz.lat[knoten] - punkt.lat) * 111195, dx = (A.netz.lon[knoten] - punkt.lon) * 111195 * c;
    return Math.hypot(dx, dy);
  }

  /** Start- und Zielknoten einer Persona: nächster Knoten, den sie überhaupt erreichen kann.
   *  (Bahnsteige sind zum Beispiel für den Rollstuhl oft „Inseln“ hinter Treppen.) */
  A.endpunkte = function (p) {
    const f = A.feld(p);
    const s = IUN.naechsterKnoten(A.netz, A.start.lat, A.start.lon, f.maske);
    const z = IUN.naechsterKnoten(A.netz, A.ziel.lat, A.ziel.lon, f.maske);
    return { start: s, ziel: z, versatz: [abstand(A.start, s), abstand(A.ziel, z)] };
  };

  A.route = function (p) {
    const e = A.endpunkte(p);
    const r = IUN.kuerzesterWeg(A.netz, A.feld(p).kosten, e.start, e.ziel);
    if (!r.kanten) return Object.assign(e, { kanten: null });
    return Object.assign(e, { kanten: r.kanten, kennzahlen: IUN.bewerten(A.netz, r.kanten, p, A.kriterien.map((k) => k.id)) });
  };

  // ------------------------------------------------------------------ Start und Ziel

  A.setPunkt = function (art, lat, lon, name) {
    A[art] = { lat, lon, name: name || "" };
    const wahl = $("#wahl-" + art);
    wahl.value = name && [...wahl.options].some((o) => o.value === name) ? name : "frei";
    for (const k of A.karten) k.marken[art].setLatLng([lat, lon]);
    A.beiAenderung.forEach((f) => f());
  };

  function setzenModus(art) {
    A.setzen = art;
    $("#setze-start").setAttribute("aria-pressed", art === "start");
    $("#setze-ziel").setAttribute("aria-pressed", art === "ziel");
    for (const k of A.karten) k.map.getContainer().style.cursor = art ? "crosshair" : "";
    $("#klickhinweis").innerHTML = art
      ? `Klicken Sie auf die Karte, um ${art === "start" ? "den Start" : "das Ziel"} zu setzen.`
      : "Die Marken <b>S</b> und <b>Z</b> lassen sich auch verschieben.";
  }

  /** Bindet eine Karte an Start und Ziel: Marken, Klick zum Setzen. */
  A.karteAnbinden = function (k, ziehbar) {
    k.marken = {};
    for (const art of ["start", "ziel"]) {
      const m = (k.marken[art] = K.marke(art, [A[art].lat, A[art].lon], ziehbar).addTo(k.map));
      if (ziehbar) m.on("dragend", () => { const ll = m.getLatLng(); A.setPunkt(art, ll.lat, ll.lng); });
    }
    k.map.on("click", (e) => {
      if (!A.setzen) return;
      const art = A.setzen;
      setzenModus(null);
      A.setPunkt(art, e.latlng.lat, e.latlng.lng);
    });
    k.setHervorheben($("#hervorheben").value);
    A.karten.push(k);
  };

  // ------------------------------------------------------------------ Reiter

  A.zeigeReiter = function (name) {
    if (!["routen", "pareto"].includes(name)) name = "routen";
    A.reiter = name;
    for (const r of ["routen", "pareto"]) {
      $("#reiter-" + r).setAttribute("aria-selected", r === name);
      $("#feld-" + r).hidden = r !== name;
    }
    if (location.hash.slice(1) !== name) history.replaceState(null, "", "#" + name);
    A.karte.map.invalidateSize();
    A.beiReiter.forEach((f) => f(name));
  };

  // ------------------------------------------------------------------ Routen vergleichen

  let routenEbene = null;

  function personenliste() {
    $("#personas").innerHTML = A.allePersonas().map((p) => `
      <li>
        <input type="checkbox" id="p-${p.id}" value="${p.id}" ${A.aktiv.has(p.id) ? "checked" : ""}>
        ${A.strichprobe(p)}
        <label class="name" for="p-${p.id}">${p.name}</label>
        <span class="beschreibung">${p.beschreibung}</span>
      </li>`).join("");
  }

  function routenNeu() {
    if (A.reiter !== "routen") return;
    routenEbene.clearLayers();
    const ergebnisse = A.allePersonas().filter((p) => A.aktiv.has(p.id)).map((p) => ({ p, r: A.route(p) }));
    // Erst alle weißen Ränder, dann die Linien: So bleibt eine Route auch dort sichtbar,
    // wo eine gestrichelte Route über ihr liegt.
    const linien = ergebnisse.filter(({ r }) => r.kanten).map(({ p, r }) => ({ p, punkte: IUN.linie(A.netz, r.kanten) }));
    for (const { punkte } of linien) K.routenrand(punkte).addTo(routenEbene);
    for (const { p, punkte } of linien) K.routenlinie(punkte, p.farbe, p.strich, 5, false).addTo(routenEbene);
    const zeilen = $("#alle-kriterien").checked ? ["zeit", "kosten"].concat(A.kriterien.map((k) => k.id)) : A.kennzahlen;
    $("#kennzahlen").innerHTML = !ergebnisse.length ? "<caption>Bitte mindestens eine Persona auswählen.</caption>" : `
      <thead><tr><th scope="col"><span class="nur-vorleser">Kennzahl</span></th>${ergebnisse.map(({ p }) =>
        `<th scope="col">${A.strichprobe(p, 40)}${p.name.replace(" (Standard)", "")}</th>`).join("")}</tr></thead>
      <tbody>${zeilen.map((id) => `<tr><th scope="row" title="${id === "zeit" || id === "kosten" ? "" : A.kriterium(id).beschreibung}">${A.name(id)}</th>${
        ergebnisse.map(({ p, r }) => `<td>${r.kanten && (id !== "rad_schieben" || p.tempo_schieben) ? A.format(id, r.kennzahlen[id]) : "–"}</td>`).join("")}</tr>`).join("")}</tbody>`;
    const hinweise = [];
    for (const { p, r } of ergebnisse) {
      if (!r.kanten) { hinweise.push(`<b>${p.name}:</b> keine Route gefunden.`); continue; }
      ["Start", "Ziel"].forEach((wort, i) => {
        if (r.versatz[i] > 60) hinweise.push(`<b>${p.name}:</b> ${wort} um ${de(r.versatz[i])} m verlegt (nächster Punkt, der für diese Persona erreichbar ist).`);
      });
    }
    $("#routenhinweise").innerHTML = hinweise.map((h) => `<p>${h}</p>`).join("");
  }

  // ------------------------------------------------------------------ Eigene Einstellung

  function reglerAufbauen() {
    $("#vorlage").innerHTML = A.personas.map((p) => `<option value="${p.id}">${p.name}</option>`).join("");
    $("#vorlage").value = "rad";
    $("#regler").innerHTML = A.kriterien.map((k) => `
      <div class="regler" title="${k.beschreibung}">
        <label for="g-${k.id}">${k.name}</label>
        <output id="o-${k.id}" for="g-${k.id}"></output>
        ${k.nur_sperre ? "<span></span>" : `<input type="range" id="g-${k.id}" min="0" max="${k.max}" step="${k.schritt}" value="0">`}
        <label class="sperre"><input type="checkbox" id="s-${k.id}"> sperren</label>
      </div>`).join("");
  }

  function reglerZeigen() {
    const p = A.eigene;
    $("#tempo").value = Math.round(p.tempo * 3.6 * 2) / 2;
    for (const k of A.kriterien) {
      const g = p.gewichte[k.id] || 0, regler = $("#g-" + k.id);
      if (regler) regler.value = g;
      $("#s-" + k.id).checked = p.sperren.includes(k.id);
      $("#o-" + k.id).textContent = k.nur_sperre ? "" : `${de(g, k.schritt < 1 ? 1 : 0)} ${k.gewicht_einheit}`;
    }
  }

  function vorlageNehmen() {
    const v = A.persona($("#vorlage").value);
    Object.assign(A.eigene, {
      tempo: v.tempo, tempo_schieben: v.tempo_schieben,
      sperren: v.sperren.slice(), gewichte: Object.assign({}, v.gewichte),
    });
    reglerZeigen();
    eigeneGeaendert();
  }

  let geplant = 0;
  function eigeneGeaendert() {
    A.aktiv.add("eigene");
    const haken = $("#p-eigene");
    if (haken) haken.checked = true;
    cancelAnimationFrame(geplant);
    geplant = requestAnimationFrame(routenNeu);
  }

  function reglerLesen() {
    const p = A.eigene;
    const kmh = parseFloat($("#tempo").value);
    if (kmh > 0) p.tempo = kmh / 3.6;
    p.gewichte = {}; p.sperren = [];
    for (const k of A.kriterien) {
      const regler = $("#g-" + k.id);
      if (regler && +regler.value > 0) p.gewichte[k.id] = +regler.value;
      if ($("#s-" + k.id).checked) p.sperren.push(k.id);
    }
    reglerZeigen();
    eigeneGeaendert();
  }

  // ------------------------------------------------------------------ Karte und Daten ansehen

  const HERVORHEBEN_TEXT = {
    querungen: "Dreieck: Querung ohne Ampel. Ring: Ampel ohne erfasstes akustisches Signal. Gefüllter Kreis: Ampel mit akustischem Signal.",
    querung_ohne_ampel: "Dreieck: Querung ohne Ampel.",
    querung_ampel_stumm: "Ring: Ampel ohne erfasstes akustisches Signal.",
    querung_akustisch: "Gefüllter Kreis: Ampel mit akustischem Signal.",
    querung_ohne_bodenindikator: "Raute: Querung ohne erfasste Bodenindikatoren.",
    bordstein: "Quadrat: hoher Bordstein.",
  };

  function karteneinstellungen() {
    const wahl = $("#hervorheben");
    wahl.innerHTML = '<option value="">nichts</option><option value="querungen">Querungen (alle Arten)</option>' +
      A.kriterien.filter((k) => !["laenge", "anstieg"].includes(k.id)).map((k) => `<option value="${k.id}">${k.name}</option>`).join("");
    wahl.addEventListener("change", () => {
      for (const k of A.karten) k.setHervorheben(wahl.value);
      const k = A.kriterium(wahl.value);
      $("#hervorheben-text").textContent = HERVORHEBEN_TEXT[wahl.value] || (k ? "Orange Linien: " + k.beschreibung : "");
    });
  }

  // ------------------------------------------------------------------ Start

  async function laden() {
    let roh, daten;
    try {
      const hole = (pfad) => fetch(pfad).then((r) => { if (!r.ok) throw new Error(pfad + ": " + r.status); return r.json(); });
      [roh, daten] = await Promise.all([hole("daten/netz.json"), hole("personas.json")]);
    } catch (fehler) {
      const lokal = location.protocol === "file:";
      A.meldung(lokal
        ? "Die Seite wurde direkt als Datei geöffnet. Dann darf der Browser die Daten nicht nachladen. Starten Sie im Ordner <code>webdemo</code> einen kleinen Webserver mit <code>python -m http.server</code> und öffnen Sie <a href=\"http://localhost:8000\">http://localhost:8000</a>."
        : "Die Daten konnten nicht geladen werden (" + fehler.message + ").", true);
      return;
    }
    A.netz = IUN.netzAufbauen(roh);
    K.mercator(A.netz);
    A.personas = daten.personas;
    A.kriterien = daten.kriterien;
    A.kennzahlen = daten.kennzahlen;
    A.eigene = Object.assign(JSON.parse(JSON.stringify(A.persona("rad"))), {
      id: "eigene", name: "Eigene Einstellung", farbe: "#000000", strich: "6 5",
      beschreibung: "Gewichte und Sperren stellen Sie unten selbst ein.",
    });
    if (roh.erzeugt) $("#stand-wege").textContent = ", Export vom " + roh.erzeugt.split("-").reverse().join(".");

    const orte = Object.keys(A.netz.orte);
    for (const art of ["start", "ziel"]) {
      $("#wahl-" + art).innerHTML = orte.map((o) => `<option value="${o}">${o}</option>`).join("") + '<option value="frei">Punkt auf der Karte</option>';
      $("#wahl-" + art).addEventListener("change", (e) => {
        const o = A.netz.orte[e.target.value];
        if (o) A.setPunkt(art, o[0], o[1], e.target.value);
      });
      $("#setze-" + art).addEventListener("click", () => setzenModus(A.setzen === art ? null : art));
    }
    A.start = { lat: A.netz.orte["Hauptbahnhof"][0], lon: A.netz.orte["Hauptbahnhof"][1], name: "Hauptbahnhof" };
    A.ziel = { lat: A.netz.orte["Phoenix-See"][0], lon: A.netz.orte["Phoenix-See"][1], name: "Phoenix-See" };
    $("#wahl-start").value = "Hauptbahnhof"; $("#wahl-ziel").value = "Phoenix-See";

    karteneinstellungen();
    A.karte = K.karte("karte", A.netz);
    A.karteAnbinden(A.karte, true);
    routenEbene = L.layerGroup().addTo(A.karte.map);

    personenliste();
    reglerAufbauen();
    reglerZeigen();
    $("#personas").addEventListener("change", (e) => {
      if (e.target.checked) A.aktiv.add(e.target.value); else A.aktiv.delete(e.target.value);
      routenNeu();
    });
    $("#alle-kriterien").addEventListener("change", routenNeu);
    $("#vorlage-nehmen").addEventListener("click", vorlageNehmen);
    $("#regler").addEventListener("input", reglerLesen);
    $("#tempo").addEventListener("change", reglerLesen);
    A.beiAenderung.push(routenNeu);
    A.beiReiter.push((name) => { if (name === "routen") routenNeu(); else routenEbene.clearLayers(); });

    for (const r of ["routen", "pareto"]) $("#reiter-" + r).addEventListener("click", () => A.zeigeReiter(r));
    window.addEventListener("hashchange", () => A.zeigeReiter(location.hash.slice(1)));
    $("#startziel").hidden = false;
    $("#karteneinstellungen").hidden = false;
    A.meldung("");
    A.bereit = true;
    document.dispatchEvent(new Event("iun-bereit"));
    A.zeigeReiter(location.hash.slice(1) || "routen");
  }

  laden();
})();
