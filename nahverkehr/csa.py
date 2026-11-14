"""Connection Scan Algorithm (CSA) für die früheste Ankunft.

Dieselbe Funktion steht ausführlich erklärt im Notebook fahrplan_selbst_rechnen.ipynb;
diese Datei dient dazu, sie aus eigenen Notebooks oder Skripten zu benutzen.

Idee (Dibbelt, Pajor, Strasser, Wagner 2013): Alle Verbindungen in der Reihenfolge ihrer
Abfahrt durchgehen. Eine Verbindung ist benutzbar, wenn man schon in ihrer Fahrt sitzt
oder rechtzeitig an ihrem Abfahrtshalt ist.
"""

from collections import defaultdict

import gtfs_hilfen as h

UNENDLICH = float("inf")


def frueheste_ankunft(c, fuss, zugang, abgang, startzeit, direkt=UNENDLICH):
    """Früheste Ankunft am Ziel.

    c: Verbindungen (DataFrame, nach Abfahrt sortiert); fuss: Fußwege zwischen Halten;
    zugang/abgang: dict halt -> Sekunden vom Start bzw. zum Ziel; startzeit in Sekunden
    seit Mitternacht; direkt: Sekunden für den direkten Fußweg (ohne Bus und Bahn).
    Gibt (ankunft, abschnitte) zurück; abschnitte ist eine Liste von dicts, leer, wenn
    der direkte Fußweg am schnellsten ist oder es keine Verbindung gibt.
    """
    bereit = defaultdict(lambda: UNENDLICH)   # frühester Zeitpunkt zum Einsteigen je Halt
    fahrten_bis = defaultdict(int)            # benutzte Fahrzeuge bis dahin
    vorgaenger = {}                           # halt -> (einstieg, ausstieg, umstiegshalt)
    for halt, sekunden in zugang.items():
        bereit[halt] = startzeit + sekunden
    eingestiegen = {}                         # fahrt -> (Nummer der Einstiegsverbindung, Fahrzeuge)
    beste, ziel_vorg, ziel_fahrten = startzeit + direkt, None, 0

    # Python-Listen sind in einer Schleife schneller als pandas-Spalten
    ab_halt, an_halt = c.ab_halt.tolist(), c.an_halt.tolist()
    ab, an, fahrt = c.ab.tolist(), c.an.tolist(), c.fahrt.tolist()
    ein_ok, aus_ok = c.einstieg_ok.tolist(), c.ausstieg_ok.tolist()

    for i in range(len(c)):
        if ab[i] > beste:
            break                             # später abfahren lohnt nicht mehr
        f, s0 = fahrt[i], ab_halt[i]
        hier_moeglich = ein_ok[i] and bereit[s0] <= ab[i]
        if f not in eingestiegen:
            if not hier_moeglich:
                continue                      # Fahrt (noch) nicht erreichbar
            eingestiegen[f] = (i, fahrten_bis[s0] + 1)
        elif hier_moeglich and fahrten_bis[s0] + 1 < eingestiegen[f][1]:
            # Gleichstandsregel: lieber hier einsteigen, wenn das Umstiege spart
            eingestiegen[f] = (i, fahrten_bis[s0] + 1)
        if not aus_ok[i]:
            continue
        e, k = eingestiegen[f]
        s = an_halt[i]
        for nachbar, sekunden in fuss.get(s, [(s, h.UMSTIEGSZEIT)]):
            t = an[i] + sekunden
            if t < bereit[nachbar] or (t == bereit[nachbar] and k < fahrten_bis[nachbar]):
                bereit[nachbar], fahrten_bis[nachbar] = t, k
                vorgaenger[nachbar] = (e, i, s)
        if s in abgang:
            t = an[i] + abgang[s]
            if t < beste or (t == beste and k < ziel_fahrten):
                beste, ziel_vorg, ziel_fahrten = t, (e, i), k

    return beste, rekonstruieren(c, vorgaenger, ziel_vorg)


def rekonstruieren(c, vorgaenger, ziel_vorg):
    """Setzt die Reise rückwärts aus den gemerkten Ein- und Ausstiegen zusammen."""
    abschnitte = []
    while ziel_vorg is not None:
        e, a = ziel_vorg
        abschnitte.append(abschnitt(c, e, a))
        ziel_vorg = vorgaenger.get(c.ab_halt.iat[e])
        if ziel_vorg is not None:
            ziel_vorg = ziel_vorg[:2]
    return abschnitte[::-1]


def abschnitt(c, e, a):
    """Fahrtabschnitt von Verbindung e bis Verbindung a (gleiche Fahrt)."""
    teil = c.iloc[e:a + 1]
    teil = teil[teil.fahrt == c.fahrt.iat[e]]
    typ = int(c.typ.iat[e])
    return {
        "linie": c.linie.iat[e],
        "verkehrsmittel": h.VERKEHRSMITTEL.get(typ, str(typ)),
        "von": c.ab_halt.iat[e], "nach": c.an_halt.iat[a],
        "ab": int(c.ab.iat[e]), "an": int(c.an.iat[a]),
        "halte": [c.ab_halt.iat[e]] + list(teil.an_halt),
    }


def reisezeit(g, c, fuss, start, ziel, startzeit, zugang_meter=800, zugang_tempo=None):
    """Reisezeit von Tür zu Tür in Sekunden: früheste Ankunft minus Startzeit.

    start, ziel: (lat, lon). Der direkte Fußweg zählt als Alternative.
    zugang_tempo: Tempo zum ersten Halt (m/s); z. B. 4.2 für das Rad als Zubringer.
    Gibt (sekunden, abschnitte) zurück.
    """
    zugang = h.halte_in_der_naehe(g, *start, max_meter=zugang_meter,
                                  tempo=zugang_tempo or h.GEHGESCHWINDIGKEIT)
    abgang = h.halte_in_der_naehe(g, *ziel)
    ankunft, reise = frueheste_ankunft(c, fuss, zugang, abgang, startzeit,
                                       direkt=h.gehzeit(start, ziel))
    return ankunft - startzeit, reise
