# Ausbaustufen

Was Version 1 bewusst nicht enthält, grob nach Nutzen für die Gruppe sortiert.

## Als Nächstes

- **Uhrzeiten und Dauer je Stopp (Variante C).** Aus Aufenthaltsdauer und Wegzeit entsteht ein Zeitplan mit Abfahrten; mit den Öffnungszeiten aus OSM kann die App warnen („montags geschlossen“).
- **Ort per langem Druck auf die Karte hinzufügen** und Orte per Ziehen zwischen Tagen verschieben (bisher über die Auswahl „Tag“ in den Details).
- **Passwort zurücksetzen und Nutzerverwaltung** für den Admin.

## Gruppe

- **Abstimmungen:** Fragen mit Optionen („Fado-Abend oder Rooftop-Bar?“), nicht nur „Dafür“ je Ort.
- **Ausgaben-Splitter:** wer hat was bezahlt, wer schuldet wem wie viel.
- **Packlisten:** gemeinsame und persönliche Listen zum Abhaken, auf Wunsch von Claude nach Ziel und Jahreszeit vorgeschlagen.
- **Kommentare je Ort** statt einer einzigen Notiz, und ein Verlauf, wer was geändert hat.
- **Sofortiger Abgleich** (Server-Sent Events) statt Abfrage alle 20 Sekunden.

## Unterwegs

- **Offline bearbeiten** mit Abgleich, sobald wieder Netz da ist.
- **Kartenausschnitt der Reise gezielt offline speichern.** Die öffentlichen OSM-Kacheln erlauben kein Laden auf Vorrat; dafür bräuchte es einen eigenen Kachel-Server oder einen Anbieter, der es gestattet.
- **Fotoalbum je Reise**, Fotos den Orten zugeordnet.
- **„Was ist in der Nähe?“:** offene Cafés oder Restaurants rund um den aktuellen Standort.
- **Wetter je Stunde am Tagesplan** (kommt sinnvoll mit den Uhrzeiten).
- **Wechselnde Unterkünfte** für Rundreisen: ein Hotel je Tag statt je Reise.
- **Spaziergänge mit eigener Strecke:** mehrere Wegpunkte, auf der Karte von Hand anpassbar.

## Inhalte

- **Bildnachweis mit Urheber und Lizenz je Foto** direkt in der App (bisher Link zur Bildseite bei Wikimedia Commons).
- **Weitere Quellen für Orte ohne Wikipedia-Artikel**, etwa Wikivoyage oder die Website des Orts, weiterhin mit Quellenlink.
- **Reise als PDF oder Kalender (ICS) exportieren.**
- **Mehrere Ziele in einer Reise** (Rundreise mit Etappen).

## Technik

- **Automatische Tests** für API und die wichtigsten Wege im Browser.
- **Vektor-Karte (MapLibre)** mit echtem Dunkelmodus statt Farbfilter.
