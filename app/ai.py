"""Claude API: place suggestions for a trip and place texts written from a given source."""

import json
import os

import anthropic

from geo import KINDS, MEALS

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("CLAUDE_EFFORT", "medium")
SOURCE_CHARS = 12000  # how much of a Wikipedia article is sent as source for a place text


class AIError(Exception):
    pass


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _ask_json(system: str, text: str, schema: dict, effort: str, what: str) -> dict:
    """One Claude call with a JSON-schema answer; API problems become AIError with a German message."""
    # If the model declines, the API re-runs the request on a fallback model. Haiku has no fallback.
    fallback = {} if "haiku" in MODEL else {
        "betas": ["server-side-fallback-2026-07-01"],
        "extra_body": {"fallbacks": "default"},
    }
    client = anthropic.Anthropic()
    try:
        # Streamed so long answers don't hit the HTTP timeout
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=32000,
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            system=system,
            messages=[{"role": "user", "content": text}],
            **fallback,
        ) as stream:
            response = stream.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise AIError("Der API-Schlüssel ist ungültig.") from exc
    except anthropic.RateLimitError as exc:
        raise AIError("Zu viele Anfragen an die Claude API. Versuch es gleich noch mal.") from exc
    except anthropic.APIStatusError as exc:
        raise AIError(f"{what} ist fehlgeschlagen (HTTP {exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise AIError("Keine Verbindung zur Claude API.") from exc

    if response.stop_reason == "refusal":
        raise AIError(f"{what} wurde von Claude abgelehnt.")
    if response.stop_reason == "max_tokens":
        raise AIError("Die Antwort war unvollständig. Versuch es noch einmal.")
    block = next((b for b in response.content if b.type == "text"), None)
    try:
        return json.loads(block.text)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise AIError("Die Antwort konnte nicht gelesen werden.") from exc


SUGGEST_SYSTEM = """Du planst Reisen für eine Freundesgruppe und schlägst Orte samt Tagesrouten vor.

Die App prüft jeden deiner Orte anschließend in OpenStreetMap. Deshalb:
- Nenne nur Orte, von denen du sicher weißt, dass es sie gibt. Lieber weniger Orte als ein erfundener.
- name: so, wie der Ort vor Ort und in OpenStreetMap heißt (Name in Landessprache oder der gängige deutsche Name), ohne Zusätze wie Stadtname oder Erklärungen.
- Bei Restaurants, Cafés und Bars: etablierte Häuser, die es seit Jahren gibt. Kurzlebige Trend-Lokale könnten inzwischen geschlossen sein.
- lat/lon: so genau, wie du sie kennst.
- wikipedia_de: der exakte Titel des deutschen Wikipedia-Artikels über genau diesen Ort, wenn du ihn sicher kennst, sonst "".
- stay_min: wie viele Minuten eine Gruppe dort sinnvoll verbringt, realistisch für diesen Ort: ein Platz oder Aussichtspunkt 15 bis 30, eine Kirche 20 bis 40, ein großes Museum 90 bis 150, Mittagessen 60, Abendessen 90. Die Summe aus Aufenthalten und Wegen soll einen Tag von etwa 9 bis 19 Uhr füllen, ohne ihn zu überladen.
- reason: ein bis zwei Sätze auf Deutsch, warum sich der Ort für diese Gruppe lohnt. Keine Jahreszahlen, Preise oder Öffnungszeiten; die Fakten zeigt die App aus Wikipedia und OpenStreetMap.

Tagesplan:
- day ist der Reisetag (1 = erster Tag), order die Reihenfolge innerhalb des Tages.
- Die Orte eines Tages liegen nah beieinander, und die Reihenfolge ergibt einen sinnvollen Weg ohne Hin und Her.
- Pro vollem Tag vier bis sechs Sehenswürdigkeiten oder Aktivitäten, dazu Essensorte an passender Stelle: Frühstück oder Café am Anfang, Mittagessen in der Mitte, Abendessen am Ende, in der Nähe der jeweils benachbarten Stopps.
- An- und Abreisetag dürfen kürzer sein.
- Ist eine Unterkunft genannt, beginnt und endet jeder Tag dort: Der erste und der letzte Stopp liegen günstig zur Unterkunft. Die Unterkunft selbst schlägst du nicht vor.
- Die App plant Wege über 25 Minuten automatisch mit Bus und Bahn. Weiter auseinanderliegende Stopps an einem Tag sind deshalb in Ordnung, wenn sie zusammenpassen.
- Spaziergänge: Wenn der Fußweg von einem Stopp zum nächsten selbst lohnt (Uferpromenade, Park, Altstadtgassen, Aussichtsweg) und höchstens etwa 45 Minuten dauert, beschreibe ihn beim ersten der beiden Stopps in walk_to_next in wenigen Worten, etwa „am Flussufer entlang“. walk_via nennt dazu einen Ort auf diesem Weg, so wie er in OpenStreetMap heißt, damit die Route dort entlangführt; "" wenn dir keiner sicher einfällt. Ein, zwei solche Spaziergänge pro Tag sind gut, bei den übrigen Stopps bleibt walk_to_next "".
- Liegt eine Wettervorhersage vor, plane danach: Parks, Aussichtspunkte und Spaziergänge auf trockene Tage und Stunden, Museen und andere Orte drinnen in die Regenzeiten.
- day 0 steht für zusätzliche Ideen ohne festen Tag (höchstens sechs), etwa eine gute Bar oder ein Ausweichprogramm bei Regen.

Kategorien:
- kind: sight (Sehenswürdigkeit), museum, nature (Park, Natur, Aussicht), restaurant, cafe, bar, shop (Einkaufen, Markt), activity (Erlebnis), lodging, other.
- meals: nur bei restaurant, cafe und bar, und nur die Mahlzeiten, für die der Ort wirklich taugt (breakfast, lunch, dinner). Ein Café kann zugleich Frühstück sein. Sonst leere Liste.

Halte dich an die Wünsche der Gruppe, und schlage keinen Ort vor, der schon auf der Liste steht."""

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "places": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "meals": {"type": "array", "items": {"type": "string", "enum": list(MEALS)}},
                    "day": {"type": "integer"},
                    "order": {"type": "integer"},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "wikipedia_de": {"type": "string"},
                    "reason": {"type": "string"},
                    "walk_to_next": {"type": "string"},
                    "walk_via": {"type": "string"},
                    "stay_min": {"type": "integer"},
                },
                "required": ["name", "kind", "meals", "day", "order", "lat", "lon", "wikipedia_de", "reason",
                             "walk_to_next", "walk_via", "stay_min"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["places"],
    "additionalProperties": False,
}


def suggest(destination: str, days: list[str], existing: list[str], wishes: str, only_day: int | None,
            hotel: str | None = None, weather: list[str] | None = None) -> list[dict]:
    """days: one label per trip day, e.g. 'Freitag, 12.06.2026'. Returns the suggested places."""
    lines = [f"Reiseziel: {destination}", f"Reisetage ({len(days)}):"]
    lines += [f"- Tag {i}: {label}" for i, label in enumerate(days, start=1)]
    if hotel:
        lines.append(f"Unterkunft: {hotel}")
    if weather:
        lines.append("Wettervorhersage:")
        lines += [f"- {w}" for w in weather]
    if wishes:
        lines.append(f"Wünsche der Gruppe: {wishes}")
    if existing:
        lines.append("Schon auf der Liste (nicht noch einmal vorschlagen, aber bei der Route berücksichtigen):")
        lines += [f"- {e}" for e in existing]
    if only_day:
        lines.append(f"Schlage nur weitere Orte für Tag {only_day} vor (drei bis sechs), die zu den dort schon geplanten passen.")
    elif existing:
        lines.append("Ergänze den Plan um weitere Orte, vor allem für Tage, die noch dünn besetzt sind.")
    else:
        lines.append("Erstelle einen Plan für alle Reisetage.")
    return _ask_json(SUGGEST_SYSTEM, "\n".join(lines), SUGGEST_SCHEMA, EFFORT, "Die Planung")["places"]


REPLAN_SYSTEM = """Du passt den Plan einer Reise an die Wettervorhersage an.

Du bekommst die Orte jedes Tages in ihrer Reihenfolge und die Vorhersage je Tag. Verteile die vorhandenen Orte neu:
- Orte im Freien (Parks, Aussichtspunkte, Plätze, Spaziergänge durch Viertel) auf trockene Tage oder die trockenen Stunden eines Tages, Orte drinnen (Museen, Kirchen, Markthallen, Cafés) in die Regenzeiten.
- Die Orte eines Tages sollen weiter nah beieinanderliegen und eine sinnvolle Reihenfolge ergeben. Tausche lieber ganze Tage oder Tageshälften, als einzelne Orte quer durch die Stadt zu schieben.
- Essensorte bleiben an einer passenden Stelle im Tag: Frühstück am Anfang, Mittagessen in der Mitte, Abendessen am Ende.
- Ändere so wenig wie nötig. Passt der Plan schon zum Wetter, gib ihn unverändert zurück.

Gib jeden Ort genau einmal zurück, mit seiner id, dem Tag und der Position im Tag (order, ab 1). Füge keine Orte hinzu und lass keinen weg.
summary: ein bis zwei Sätze auf Deutsch, was du geändert hast und warum, oder dass nichts zu ändern war."""

REPLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "day": {"type": "integer"}, "order": {"type": "integer"}},
                "required": ["id", "day", "order"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "plan"],
    "additionalProperties": False,
}


def replan(destination: str, days: int, weather: list[str], places: list[dict]) -> dict:
    """places: id, name, kind, meals (JSON text), day, pos of every planned place. Returns {summary, plan}."""
    lines = [f"Reiseziel: {destination}, {days} Tage", "Wettervorhersage:"] + [f"- {w}" for w in weather]
    lines.append("Tage ohne Vorhersage: Wetter unbekannt, dort möglichst nichts ändern.")
    for day in range(1, days + 1):
        lines.append(f"Tag {day}:")
        lines += [f"- id {p['id']}: {p['name']} ({p['kind']}{', ' + ', '.join(json.loads(p['meals'])) if p['meals'] != '[]' else ''})"
                  for p in places if p["day"] == day]
    return _ask_json(REPLAN_SYSTEM, "\n".join(lines), REPLAN_SCHEMA, EFFORT, "Das Umplanen")


STAYS_SYSTEM = """Du schätzt für eine Reise-App, wie viele Minuten eine Freundesgruppe an jedem Ort sinnvoll verbringt.

Richte dich nach dem konkreten Ort, nicht nur nach seiner Art: Ein Platz oder Aussichtspunkt braucht 15 bis 30 Minuten, eine Kirche 20 bis 40, ein kleines Museum 45 bis 60, ein großes 90 bis 150, ein Markt 30 bis 60, Frühstück oder Café 30 bis 45, Mittagessen 60, Abendessen 90, eine Bar 60. Kennst du den Ort nicht, nimm einen üblichen Wert für seine Art.

Gib jeden Ort genau einmal zurück, mit seiner id und den Minuten, auf 5 gerundet."""

STAYS_SCHEMA = {
    "type": "object",
    "properties": {
        "stays": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "minutes": {"type": "integer"}},
                "required": ["id", "minutes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["stays"],
    "additionalProperties": False,
}


def stays(destination: str, places: list[dict]) -> list[dict]:
    """places: id, name, kind, meals (JSON text). Returns [{id, minutes}]."""
    lines = [f"Reiseziel: {destination}", "Orte:"]
    lines += [f"- id {p['id']}: {p['name']} ({p['kind']}{', ' + ', '.join(json.loads(p['meals'])) if p['meals'] != '[]' else ''})" for p in places]
    return _ask_json(STAYS_SYSTEM, "\n".join(lines), STAYS_SCHEMA, "low", "Die Schätzung")["stays"]


INFO_SYSTEM = """Du schreibst kurze Ortsinfos für eine Reise-App, auf Deutsch, auch wenn der Quelltext englisch ist.

Verwende ausschließlich, was im Quelltext steht. Ergänze nichts aus eigenem Wissen, auch wenn du es für richtig hältst: Die App zeigt den Text mit dem Quelltext als Beleg. Gibt der Quelltext zu einem Feld nichts her, bleibt es leer.

- summary: zwei bis drei Sätze: was der Ort ist und was ihn besonders macht.
- history: drei bis fünf Sätze zum historischen Hintergrund. Leer, wenn der Quelltext keine Geschichte enthält.
- facts: zwei bis vier interessante Einzelheiten, je ein Satz, die nicht schon in summary oder history stehen. Leere Liste, wenn es keine gibt.

Schreibe für jemanden, der gleich davorsteht: konkret und ohne Werbesprache."""

INFO_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "history": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "history", "facts"],
    "additionalProperties": False,
}


def place_info(name: str, source_title: str, source_text: str) -> dict:
    cut = len(source_text) > SOURCE_CHARS
    text = (f"Ort: {name}\nQuelle: Wikipedia-Artikel „{source_title}“"
            + (" (Anfang des Artikels, der Rest fehlt)" if cut else "")
            + f"\n\n<quelltext>\n{source_text[:SOURCE_CHARS]}\n</quelltext>")
    return _ask_json(INFO_SYSTEM, text, INFO_SCHEMA, "low", "Die Ortsinfo")
