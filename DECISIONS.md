# Entscheidungen

Jede Entscheidung mit einem Satz Begründung. Stand: Version 1, November 2026.

## Umfang

- **In Version 1 über den Pflichtkern hinaus: „Dafür“-Stimmen und eine gemeinsame Notiz je Ort.** Beides ist klein, und ohne sie müsste die Gruppe jeden Vorschlag im Chat ausdiskutieren.
- **Fortbewegung je Reise wählbar (zu Fuß, Rad, Auto).** Die Route und die Übergabe an die Karten-App hängen davon ab, und der Routing-Dienst bietet alle drei.
- **Eigener Standort auf der Karte.** Unterwegs ist das die erste Frage, und es kostet nur einen Knopf.
- **Nicht in Version 1: Packlisten, Ausgaben-Splitter, Fotoalbum, richtige Abstimmungen mit Terminen.** Jedes davon ist ein eigenes kleines Produkt und hätte den Kern halbfertig gelassen; sie stehen in der ROADMAP.
- **Bearbeiten nur online.** Offline-Änderungen brauchen Konfliktlösung zwischen mehreren Leuten; Lesen ohne Netz deckt den Fall „unterwegs im Funkloch“ ab.

## Vorschläge und Fakten

- **Claude schlägt vor, OpenStreetMap bestätigt.** Jeder vorgeschlagene Ort wird per Nominatim gesucht; Position, Adresse, Öffnungszeiten und Website kommen von dort, nicht vom Modell, weil Modelle Lokale erfinden oder geschlossene nennen können.
- **Nicht gefundene Orte bleiben, aber mit Warnhinweis.** OSM ist lückenhaft, ein echter Ort soll deshalb nicht stillschweigend verschwinden; liegt ein Treffer mehr als 3 km von Claudes Angabe entfernt, gilt er als Namensvetter und zählt nicht.
- **Ortstexte nur aus dem Wikipedia-Artikel.** Claude bekommt den Artikeltext und darf nichts aus eigenem Wissen ergänzen; ohne Artikel bleibt die Beschreibung leer, wie gewünscht.
- **Welcher Artikel zu einem Ort gehört, bestimmt OSM (Tags `wikipedia`/`wikidata`).** Ein von Claude geratener Artikeltitel zählt nur, wenn die Koordinaten des Artikels höchstens 1,5 km vom Ort liegen, damit kein falscher Artikel als Beleg erscheint.
- **Claudes „Warum hierhin?“ ist als unbelegte Einschätzung gekennzeichnet.** Es ist eine Empfehlung, kein Fakt, und der Prompt verbietet darin Jahreszahlen, Preise und Öffnungszeiten.
- **Ortstexte entstehen erst beim Annehmen oder ersten Öffnen eines Orts.** So kostet ein abgelehnter Vorschlag keinen Claude-Aufruf, angenommene Orte sind trotzdem vorab geladen und damit offline lesbar.
- **Als Quelle gehen höchstens 12.000 Zeichen des Artikels an Claude.** Das deckt Einleitung und Geschichte fast immer ab und hält die Kosten pro Ort bei wenigen Cent; Claude erfährt, wenn der Text gekürzt ist.
- **Ohne API-Key gibt es Vorschläge aus Wikipedia statt einer Fehlermeldung.** So bleibt die App benutzbar und testbar; der Unterschied ist in der Oberfläche benannt.
- **Modell `claude-opus-5-5`, einstellbar über `CLAUDE_MODEL`.** Gleiches Standardmodell wie im Essen-Tracker; die Vorschläge hängen an gutem Weltwissen. Bei einer Ablehnung springt serverseitig ein Ersatzmodell ein (`fallbacks`), wie im Essen-Tracker.

## Karte, Suche, Routing

- **Leaflet mit den Standard-Kacheln von OpenStreetMap.** Kein Schlüssel, kein Konto, für eine kleine private Gruppe von der Kachel-Richtlinie gedeckt; Leaflet liegt im Repo, damit die App ohne CDN und offline startet.
- **Dunkle Karte per Farbfilter auf denselben Kacheln.** Ein zweiter Kachel-Anbieter für den Dunkelmodus hätte einen Schlüssel oder eine weitere Abhängigkeit bedeutet.
- **Routing über den OSRM-Dienst des FOSSGIS (routing.openstreetmap.de).** Frei, ohne Schlüssel, mit Profilen für Fuß, Rad und Auto; Städtetrips laufen vor allem zu Fuß. Adresse per `OSRM_URL` austauschbar.
- **Ortssuche über Nominatim, nur auf Knopfdruck.** Die Nutzungsregeln verbieten Suche bei jedem Tastendruck; die App hält außerdem höchstens eine Anfrage pro Sekunde ein.
- **Alle Antworten fremder Dienste liegen in der Tabelle `cache`.** Suchtreffer 30 Tage, Wikipedia 90 Tage, Routen unbegrenzt (gleiche Stopps, gleiche Route).
- **Die Route läuft durch angenommene und noch offene Vorschläge.** So sieht man die vorgeschlagene Tagesroute sofort; offene Vorschläge sind auf Karte und Liste hohl gezeichnet, abgelehnte fallen heraus.
- **Übergabe mit Koordinaten, Start ist der eigene Standort.** Koordinaten treffen sicher den richtigen Ort; wer navigiert, steht selten schon am ersten Stopp.
- **Apple Karten über die „Unified Map URLs“ (`/directions` mit `waypoint`, `/place`).** Das ist Apples dokumentierter Weg für Zwischenstopps und setzt iOS 18.4 voraus. Google Maps über die Maps-URLs mit `waypoints`.
- **Mehr als zehn Stopps werden in mehrere Links geteilt.** Google nimmt höchstens neun Zwischenstopps; Apple nennt keine Grenze, bekommt aber dieselbe Teilung, damit sich beide gleich verhalten.

## Unterkunft, Öffis, Spaziergänge, Wetter (November 2026, „Variante B“)

- **Eine Unterkunft je Reise, nicht je Tag.** Das deckt Städtetrips ab; Rundreisen mit wechselnden Hotels stehen in der ROADMAP.
- **Jeder Abschnitt zwischen zwei Stopps wird einzeln geplant.** Nur so können Fußweg, Spaziergang und Öffis an einem Tag gemischt werden; nebenbei bleiben beim Umsortieren alle unveränderten Abschnitte im Cache.
- **Bis 25 Minuten zu Fuß, darüber Öffis, wenn die Verbindung mindestens 15 % schneller ist.** Kürzere Wege lohnen den Gang zur Haltestelle selten; die Grenze steht als `WALK_LIMIT` in `app/main.py`, und jeder Abschnitt lässt sich von Hand umstellen.
- **Fahrplandaten von Transitous.** Der einzige freie Dienst ohne Schlüssel mit europaweiter Abdeckung; seine Bedingungen (quelloffen, nicht kommerziell, wenige Anfragen, Kontaktangabe) sind der Grund, warum das Repo öffentlich und MIT-lizenziert ist.
- **Verbindungen gelten für einen „typischen Wochentag“.** Fahrpläne reichen nur wenige Wochen voraus; für spätere Reisen fragt die App denselben Wochentag der kommenden Woche ab und sagt das dazu. Abfahrtszeiten zeigt sie deshalb nicht, die liefert die Karten-App.
- **Ohne Fahrplandaten bleibt ein Abschnitt als „Öffis“ markiert,** mit gerader gepunkteter Linie und Übergabe an die Karten-App, statt eine Verbindung zu erfinden.
- **Spaziergänge sind eine Eigenschaft des Abschnitts, kein eigener Stopp.** Claude beschreibt den Weg in wenigen Worten und nennt einen Ort darauf; nur wenn OpenStreetMap diesen Ort in der Nähe kennt, führt die Route darüber. Die App sagt dazu, dass die eingezeichnete Strecke vom beschriebenen Weg abweichen kann.
- **Wetter von Open-Meteo, Regenwarnung ab 60 % Wahrscheinlichkeit.** Frei, ohne Schlüssel, 16 Tage Vorhersage. Ohne Vorhersage zeigt die App die Werte derselben Kalendertage aus den letzten drei Jahren und nennt sie auch so, nicht „Vorhersage“.
- **„Tage umplanen“ verschiebt nur vorhandene Orte und lässt sich rückgängig machen.** Claude fügt nichts hinzu und entfernt nichts; der Stand davor wird gespeichert, bis jemand „Behalten“ oder „Rückgängig“ wählt.
- **Die Übergabe der ganzen Tagesroute bleibt ein Fußweg.** Apple Karten und Google Maps planen Öffis nicht über mehrere Stopps; ein Öffi-Abschnitt wird deshalb einzeln übergeben.

## Verschieben und Öffnungszeiten

- **Der Plan hängt an Tagesnummern, nicht an Kalenderdaten.** Ein neues Startdatum verschiebt deshalb alles, ohne dass ein Ort angefasst wird; im Dialog wandert das Enddatum mit, damit die Länge gleich bleibt.
- **Öffnungszeiten werden geprüft und markiert, nicht automatisch umgeplant.** Die App erkennt aus den OSM-Angaben geschlossene Wochentage (auch saisonale Regeln wie „Oct-Apr“) und Essensorte, die zur geplanten Mahlzeit nicht offen haben. Die Entscheidung, wohin der Ort wandert, bleibt bei euch, weil die Angaben veraltet sein können.
- **Die Prüfung läuft immer, nicht nur beim Verschieben.** So fallen auch Orte auf, die Claude oder ihr von vornherein auf einen Ruhetag gelegt habt.
- **Was die App nicht lesen kann, markiert sie nicht.** Feiertage, einzelne Kalendertage, „sunrise-sunset“ und Orte ohne Angabe gelten als unbekannt, damit keine falschen Warnungen entstehen.
- **Richtungspfeile nur auf Abschnitten, die auf dem Bildschirm mindestens 70 Pixel lang sind,** höchstens vier je Abschnitt und nur in der Tagesansicht. Bei dicht liegenden Stopps zeigen schon die Nummern die Richtung.

## Zeitplan und Live-Ansicht

- **Aufenthaltsdauer je Stopp, Startzeit je Tag; alle Uhrzeiten werden daraus berechnet, nicht gespeichert.** So stimmt der Plan nach jedem Umsortieren von selbst.
- **Ohne eigene Angabe gilt ein üblicher Wert je Art** (Sehenswürdigkeit 30, Museum 90, Mittagessen 60, Abendessen 90 Minuten), gekennzeichnet als „Vorschlag“. Claude schätzt die Dauer bei neuen Vorschlägen mit und auf Knopfdruck für vorhandene Orte.
- **Öffi-Abschnitte zählen mit ihrer Fahrtdauer, ohne Wartezeit und ohne Abfahrtszeit.** Die App kennt nur die Verbindung eines typischen Wochentags; ein Abschnitt ohne Fahrplandaten zählt mit 20 Minuten.
- **Fortschritt per Knopf, nicht per Standort.** Eine Web-App kann den Standort auf dem iPhone nicht im Hintergrund verfolgen; ein Tipp auf „Weiter“ ist verlässlich und gilt für die ganze Gruppe.
- **Die Ankunft am nächsten Stopp wird aus Abgangszeit und Wegdauer geschätzt.** Einen zweiten Knopf „Angekommen“ gibt es nicht; wer länger bleibt als geplant, schiebt alles Folgende nach hinten.
- **Wer zu spät kommt, hat bis zur Schließzeit weniger Zeit.** Die Live-Ansicht kürzt den Aufenthalt auf die Schließzeit aus OpenStreetMap und sagt das, statt einen Plan zu zeigen, der nicht mehr aufgeht.
- **Live gilt nur am Kalendertag des Reisetags nach der Uhr des Geräts.** Unterwegs steht das Handy auf Ortszeit; eine Zeitzonen-Umrechnung wäre nur für Zuschauer zu Hause nötig.

## Konten und Zusammenarbeit

- **Konto = Name + Passwort, Einladung = Link je Reise.** Für eine Freundesgruppe reicht das; kein E-Mail-Versand, kein fremder Login-Dienst. Wer den Link öffnet, legt ein Konto an und ist in der Reise.
- **Das erste Konto braucht den `APP_TOKEN` aus der `.env`.** Sonst könnte sich jeder, der die Adresse kennt, als Erster registrieren (gleiches Prinzip wie im Essen-Tracker).
- **Kein Passwort-Zurücksetzen in Version 1.** Dafür bräuchte es E-Mail oder eine Admin-Oberfläche; steht in der ROADMAP.
- **Jedes Mitglied darf alles an der Reise ändern, nur löschen darf sie, wer sie angelegt hat.** Unter Freunden ist ein Rechtesystem mehr Hindernis als Schutz.
- **Abgleich per Abfrage alle 20 Sekunden (2 Sekunden, solange Vorschläge oder Ortstexte entstehen).** WebSockets wären für vier Leute mehr Technik als Nutzen.

## Technik und Betrieb

- **Gleicher Aufbau wie der Essen-Tracker:** FastAPI, Frontend ohne Build-Schritt in `app/static`, Dockerfile, GitHub-Workflow nach ghcr.io und `docker-compose.yml` sind von dort übernommen, damit beide Apps gleich gebaut, eingespielt und gesichert werden.
- **SQLite direkt über `sqlite3` statt SQLAlchemy.** Die App hat sechs Tabellen und braucht nie eine andere Datenbank; das spart eine Abhängigkeit. Migrationen laufen über `PRAGMA user_version`.
- **Port 33055 als Standard.** Von dir so festgelegt.
- **Vorschläge laufen als Hintergrund-Job mit Fortschrittsanzeige.** Claude plus eine Nominatim-Anfrage pro Sekunde und Ort dauern bis zu einer Minute, zu lang für eine einzelne Anfrage.
- **Service Worker hält App, zuletzt geladene Reisen und gesehene Kartenkacheln vor (höchstens 1.500 Kacheln).** Das erfüllt „bei schlechtem Netz lesbar“, ohne Kacheln auf Vorrat zu laden, was die OSM-Richtlinie untersagt.
- **Abfragen an fremde Dienste nennen die App neutral („Reiseplaner“), eine Kontaktadresse nur über `APP_CONTACT`.** Die Betreiber wünschen eine Kontaktangabe, aber deine Adresse soll nicht ungefragt im Code stehen.

- **Satellitenbild von Esri World Imagery, Street View als Link.** Esri stellt die Kacheln mit Quellenangabe frei zur Verfügung und sie reichen bis auf Straßenebene; Sentinel-2 wäre offen lizenziert, mit 10 m pro Pixel aber für eine Stadt zu grob. Street View lässt sich ohne kostenpflichtigen API-Key nicht einbetten, deshalb öffnet ein Link Google Maps direkt im Panorama (`map_action=pano`). Für Apple „Umsehen“ gibt es keinen dokumentierten Link.
