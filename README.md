# Reiseplaner

Städtetrips und Reisen gemeinsam planen: Claude schlägt Orte und eine Route für jeden Tag vor, ihr nehmt an, lehnt ab, sortiert um und ergänzt eigene Orte. Unterwegs läuft die App als installierbare Web-App auf dem Handy, die Navigation übernimmt Apple Karten oder Google Maps.

```
Handy / Desktop ──▶ app (FastAPI) ──▶ Claude API           Vorschläge, Ortstexte
                        │        ──▶ Nominatim (OSM)       Ortssuche, Adresse, Öffnungszeiten
                        │        ──▶ FOSSGIS-Routing       Tagesroute entlang echter Wege
                        ▼        ──▶ Wikipedia, Wikidata   Quellen für die Ortstexte
              data/reiseplaner.db (SQLite)
```

## Funktionen

- **Reisen:** Ziel, Zeitraum, Teilnehmer, ein Plan pro Tag und eine Ideenliste für Orte ohne festen Tag.
- **Vorschläge:** Claude schlägt Orte samt Reihenfolge je Tag vor, auf Wunsch mit euren Vorlieben („viel Kunst, vegetarisch“) oder nur für einen Tag. Jeder Vorschlag wird in OpenStreetMap nachgeschlagen; was dort nicht zu finden ist, wird als ungeprüft markiert. Vorschläge lassen sich einzeln oder tageweise annehmen und ablehnen.
- **Karte:** OpenStreetMap mit nummerierten Wegmarken und der Tagesroute entlang echter Wege, wahlweise zu Fuß, mit dem Rad oder dem Auto. Dazu Entfernung und Dauer je Abschnitt.
- **Übergabe:** Jeder Ort und jede Tagesroute öffnet sich mit einem Tipp in Apple Karten oder Google Maps, die Route mit allen Zwischenstopps.
- **Ortsinfos:** Kurzbeschreibung, Geschichte und Wissenswertes aus dem Wikipedia-Artikel des Orts (von Claude zusammengefasst, Quelle verlinkt), dazu Adresse, Öffnungszeiten, Website und Telefon aus OpenStreetMap. Ohne Artikel bleibt die Beschreibung leer.
- **Filter:** Art (Sehenswürdigkeit, Museum, Restaurant, Café, Bar …) und Mahlzeit (Frühstück, Mittagessen, Abendessen) frei kombinierbar; wirkt auf Karte und Liste. „Getrennt“ zeigt eine eigene Liste je Art und Mahlzeit.
- **Gruppe:** Konten mit Name und Passwort, Einladung per Link, „Dafür“-Stimmen und eine gemeinsame Notiz je Ort. Änderungen der anderen erscheinen nach spätestens 20 Sekunden.
- **Offline:** Einmal geöffnete Reisen samt Routen, Ortstexten und gesehenen Kartenausschnitten bleiben ohne Netz lesbar. Ändern geht nur online.
- **Ohne API-Key:** Vorschläge kommen dann ohne KI aus Wikipedia (bekannte Bauwerke, Plätze, Museen in der Nähe, keine Restaurants), und als Beschreibung dient der Anfang des Artikels.

Was bewusst noch fehlt, steht in [ROADMAP.md](ROADMAP.md), die Begründungen der Entscheidungen in [DECISIONS.md](DECISIONS.md).

## Installation auf Unraid

Bei jedem Push auf `main` baut GitHub Actions ein Docker-Image und legt es unter `ghcr.io/qtmo0/reiseplaner` ab. Unraid lädt nur dieses fertige Image. Der Weg ist derselbe wie beim Essen-Tracker.

**1. Einmalig: Unraid bei GitHub anmelden** (falls vom Essen-Tracker noch nicht geschehen). Repo und Image sind privat. Auf GitHub unter *Settings → Developer settings → Personal access tokens → Tokens (classic)* einen Token mit `read:packages` (und `repo` fürs Klonen) erzeugen, dann im Unraid-Terminal:

```bash
docker login ghcr.io -u qtmo0
```

**2. Repo holen:**

```bash
cd /mnt/user/appdata
git clone https://github.com/qtmo0/reiseplaner.git
cd reiseplaner
```

Auf dem Server gebraucht werden nur `docker-compose.yml` und `.env.example`.

**3. Konfiguration anlegen:**

```bash
cp .env.example .env
```

In `.env` eintragen:

- `APP_TOKEN`: Zugangscode für das allererste Konto, z. B. erzeugt mit `openssl rand -hex 24`.
- `ANTHROPIC_API_KEY`: API-Key von [platform.claude.com](https://platform.claude.com).
- `APP_PORT`: Standard ist 33055.

**4. Starten:**

```bash
docker compose up -d
```

Mit dem Plugin **Docker Compose Manager**: neuen Stack anlegen, als Ordner `/mnt/user/appdata/reiseplaner` angeben, dann **Compose Up**.

**5. Öffnen:** `http://SERVER-IP:33055` aufrufen, „Konto anlegen“ wählen und als Code den `APP_TOKEN` eingeben. Danach eine Reise anlegen und über das Personen-Symbol den Einladungslink an die Freunde schicken. Wer ihn öffnet, legt sich ein eigenes Konto an und ist in der Reise.

Die Daten liegen in `./data/reiseplaner.db`. Für ein Backup reicht dieser Ordner, am sichersten bei gestopptem Container.

## Updates

Nach einem Push auf `main` dauert der Build zwei bis drei Minuten (Fortschritt im Repo unter *Actions*). Dann auf Unraid:

```bash
cd /mnt/user/appdata/reiseplaner
docker compose pull && docker compose up -d
```

Im Compose Manager: **Update Stack**. Vollautomatisch geht es mit Watchtower; für das private Image braucht er die Anmeldedaten aus Schritt 1 (`/root/.docker/config.json` einbinden). Eine feste Version läuft mit `IMAGE_TAG=1.0.0` in der `.env`; solche Versionen entstehen durch Git-Tags wie `v1.0.0`. Schemaänderungen der Datenbank laufen beim Start automatisch (`MIGRATIONS` in `app/db.py`).

## HTTPS und Zugriff von unterwegs

Für „Zum Home-Bildschirm“ als richtige App, für den Offline-Modus, für den eigenen Standort auf der Karte und für den Zugriff von unterwegs braucht die App HTTPS. Am einfachsten mit Tailscale auf dem Server:

```bash
tailscale serve --bg 33055
```

Deine Freunde brauchen dann Zugang zum Tailnet. Sollen sie ohne Tailscale mitplanen, braucht es einen Reverse Proxy mit eigener Domain (Nginx Proxy Manager, SWAG) oder Tailscale Funnel.

Auf dem iPhone in Safari: **Teilen → Zum Home-Bildschirm**.

## Kosten und fremde Dienste

- **Claude:** ein Aufruf je Vorschlagsrunde (einige Cent) und einer je Ortstext beim Annehmen oder ersten Öffnen eines Orts (grob 2–3 Cent mit `claude-opus-5-5`). Eine Reise mit 30 Orten kostet damit etwa einen Euro. Alles wird gespeichert und nie doppelt abgefragt. Günstiger: `CLAUDE_MODEL=claude-sonnet-5-5`.
- **OpenStreetMap-Dienste** sind kostenlos, aber für sparsame Nutzung gedacht. Die App fragt Nominatim höchstens einmal pro Sekunde, speichert jede Antwort und jede Route in der Datenbank und nennt die Quellen auf der Karte. `APP_CONTACT` in der `.env` setzt eine Kontaktadresse in die Abfragen, wie es die Betreiber wünschen.

## Lokal ohne Docker starten

```bash
cd app
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
APP_TOKEN=test .venv/bin/uvicorn main:app --reload --port 33055
```

Die Datenbank liegt dann in `app/data/`. Das Image lokal bauen:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

## Aufbau

| Datei | Inhalt |
|---|---|
| `docker-compose.yml` | Container `app` (Image von ghcr.io), Datenbank in `data/` |
| `.github/workflows/docker.yml` | Baut bei jedem Push das Image und lädt es nach ghcr.io |
| `app/main.py` | REST-API: Konten, Reisen, Orte, Vorschlags-Job, Ortstexte |
| `app/ai.py` | Aufrufe der Claude API mit festem JSON-Schema |
| `app/geo.py` | Nominatim, Routing, Wikipedia und Wikidata, jeweils mit Cache |
| `app/db.py` | SQLite-Schema und Migrationen |
| `app/static/` | Frontend als PWA (HTML, CSS, JS ohne Build-Schritt, Leaflet liegt bei) |
