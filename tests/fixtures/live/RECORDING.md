# Aufgezeichnete Antworten von swissreg.ch (IGE/IPI)

Aufgenommen am **2026-10-04** mit `scripts/record_live_fixtures.py`
aus den Abfragen der Live-Suite (`page_size=3`, `<Any>`-Wrapper):
`Zürich*` (Marken), `Roche*` (Patente), `Novartis*` (SPC), sowie das
Kontingent.

## Was hier echt ist

Elementnamen, Namespaces, Verschachtelung, Reihenfolge und Anzahl;
Attributnamen und -werte; die Zaehler in `Meta` (`TotalItemCount`,
`ItemCount`, `ItemCountOffset`).

## Was ersetzt ist

Jeder uebrige Textknoten durch einen synthetischen Wert derselben
Zeichenklasse und Laenge, der Continuation-Token durch einen
gleichlangen Platzhalter, und `requestUuid`/`timestamp`/`uuid` am
Wurzelelement.

**Diese Dateien belegen die Form der Antwort, nicht ihren Inhalt.**
Ein Test darf aus ihnen ableiten, wie die Felder heissen und wie viele
Saetze eine Seite traegt — nicht, dass ein bestimmter Datensatz so
aussieht. Wer sie fuer eine woertliche Aufzeichnung nimmt, zieht
Schluesse, die sie nicht tragen.

Geschrieben: patent-publication-search, patent-search, quota, spc-search, trademark-by-number, trademark-search, trademark-search-seite2
