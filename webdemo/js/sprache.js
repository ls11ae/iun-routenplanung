/* Sprache der Webdemo: Deutsch (Voreinstellung) oder Englisch.
 *
 * Deutsch steht im HTML, die englische Fassung direkt daneben: data-en="…" ersetzt den Inhalt
 * eines Elements, data-en-<attribut>="…" ein Attribut (etwa data-en-aria-label). Texte, die
 * erst das JavaScript erzeugt, schreibt man als w("Deutsch", "English").
 *
 * Welche Sprache: ?lang=en oder ?lang=de in der Adresse, sonst die zuletzt gewählte (im Browser
 * gespeichert), sonst Deutsch. Der Knopf oben rechts wechselt die Sprache und lädt die Seite neu,
 * damit auch alle berechneten Texte in der neuen Sprache entstehen.
 *
 * Dieses Skript muss vor den übrigen Skripten der Seite stehen. */
(function () {
  "use strict";
  const S = (window.IUNSprache = {});
  const SPRACHEN = ["de", "en"], SPEICHER = "iun-sprache";

  function gespeichert() { try { return localStorage.getItem(SPEICHER); } catch (e) { return null; } }
  function merken(s) { try { localStorage.setItem(SPEICHER, s); } catch (e) { /* ohne Speicher: nur über die Adresse */ } }

  const ausAdresse = new URLSearchParams(location.search).get("lang");
  S.sprache = SPRACHEN.includes(ausAdresse) ? ausAdresse : SPRACHEN.includes(gespeichert()) ? gespeichert() : "de";
  if (SPRACHEN.includes(ausAdresse)) merken(ausAdresse);
  S.en = S.sprache === "en";
  S.locale = S.en ? "en-US" : "de-DE";

  /** Text in der gewählten Sprache. */
  S.w = (de, en) => (S.en ? en : de);
  /** Zahl mit `stellen` Nachkommastellen im Format der Sprache (2,5 bzw. 2.5). */
  S.zahl = (x, stellen = 0) => x.toLocaleString(S.locale, { minimumFractionDigits: stellen, maximumFractionDigits: stellen });
  /** Feld eines Datensatzes, im Englischen `name_en` statt `name`, falls vorhanden. */
  S.feld = (obj, name) => (S.en && obj[name + "_en"] != null ? obj[name + "_en"] : obj[name]);

  // Ortsnamen, die im Englischen anders heißen (alle übrigen bleiben, wie sie sind)
  const ORTE = { "Campus Nord": "North Campus", "Campus Süd": "South Campus", "Hauptbahnhof": "Main station",
                 "TU Dortmund, Campus Nord": "TU Dortmund, North Campus" };
  S.ort = (name) => (S.en && ORTE[name]) || name;

  /** Adresse `href` mit der Sprache `sprache` (Deutsch ohne Zusatz). */
  function mitSprache(href, sprache) {
    const u = new URL(href, location.href);
    if (sprache === "de") u.searchParams.delete("lang"); else u.searchParams.set("lang", sprache);
    return u.href;
  }

  /** Setzt die englischen Texte aus data-en und data-en-<attribut> ein. */
  S.anwenden = function (wurzel = document) {
    document.documentElement.lang = S.sprache;
    if (!S.en) return;                         // Deutsch steht schon im HTML
    for (const el of wurzel.querySelectorAll("*")) {
      for (const a of [...el.attributes]) {
        if (a.name === "data-en") el.innerHTML = a.value;
        else if (a.name.startsWith("data-en-")) el.setAttribute(a.name.slice(8), a.value);
      }
    }
    // Verweise auf die anderen Seiten der Demo behalten die Sprache
    for (const a of wurzel.querySelectorAll("a[href]")) {
      const ziel = a.getAttribute("href");
      if (/^[\w-]+\.html(#.*)?$/.test(ziel)) a.setAttribute("href", mitSprache(ziel, "en"));
    }
  };

  /** Knopf in der Kopfzeile, der zur anderen Sprache wechselt. */
  function knopf() {
    const nav = document.querySelector(".seitenkopf nav");
    if (!nav) return;
    const andere = S.en ? "de" : "en", b = document.createElement("button");
    b.type = "button";
    b.className = "reiter sprachwahl";
    b.lang = andere;
    b.textContent = S.en ? "Deutsch" : "English";
    b.title = S.en ? "Seite auf Deutsch anzeigen" : "Show this page in English";
    b.addEventListener("click", () => { merken(andere); location.href = mitSprache(location.href, andere); });
    nav.appendChild(b);
  }

  S.anwenden();
  knopf();
})();
