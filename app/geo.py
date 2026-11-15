"""Open geo services: Nominatim (search), FOSSGIS OSRM (routing), Wikipedia/Wikidata (texts).

Every answer is cached in SQLite, so each query leaves the server at most once (per cache lifetime).
Nominatim is limited to one request per second as its usage policy requires.
"""

import hashlib
import json
import math
import os
import re
import threading
import time

import httpx

import db

CONTACT = os.environ.get("APP_CONTACT", "").strip()
USER_AGENT = "Reiseplaner/1.0 (self-hosted trip planner" + (f"; {CONTACT}" if CONTACT else "") + ")"
_http = httpx.Client(timeout=12, headers={"User-Agent": USER_AGENT}, follow_redirects=True)

NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
OSRM_URL = os.environ.get("OSRM_URL", "https://routing.openstreetmap.de")
OSRM_PROFILES = {"foot": "routed-foot", "bike": "routed-bike", "car": "routed-car"}

KINDS = ("sight", "museum", "nature", "restaurant", "cafe", "bar", "shop", "activity", "lodging", "other")
FOOD_KINDS = ("restaurant", "cafe", "bar")
MEALS = ("breakfast", "lunch", "dinner")


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(a))


# ---------- Nominatim ----------

_nom_lock = threading.Lock()
_nom_last = 0.0


def _nominatim(params: dict) -> list:
    global _nom_last
    key = "nom:" + json.dumps(params, sort_keys=True, ensure_ascii=False)
    hit = db.cache_get(key, max_age_days=30)
    if hit is not None:
        return hit
    with _nom_lock:
        wait = 1.1 - (time.monotonic() - _nom_last)
        if wait > 0:
            time.sleep(wait)
        try:
            r = _http.get(f"{NOMINATIM_URL}/search", params=params)
            r.raise_for_status()
            data = r.json()
        finally:
            _nom_last = time.monotonic()
    db.cache_set(key, data)
    return data


def _guess_kind(category: str, typ: str) -> str:
    if typ in ("restaurant", "fast_food", "food_court", "biergarten"):
        return "restaurant"
    if typ in ("cafe", "ice_cream", "bakery", "pastry"):
        return "cafe"
    if typ in ("bar", "pub", "nightclub", "wine_bar"):
        return "bar"
    if typ in ("museum", "gallery", "arts_centre"):
        return "museum"
    if typ in ("park", "garden", "nature_reserve", "beach", "peak", "wood", "water", "viewpoint") or category == "natural":
        return "nature"
    if typ in ("hotel", "hostel", "guest_house", "apartment", "motel"):
        return "lodging"
    if category == "shop" or typ == "marketplace":
        return "shop"
    if typ in ("theatre", "cinema", "zoo", "theme_park", "aquarium", "swimming_pool", "sports_centre", "stadium"):
        return "activity"
    if category in ("tourism", "historic") or typ in ("place_of_worship", "castle", "monument", "memorial", "square", "bridge"):
        return "sight"
    return "other"


def _address(a: dict) -> str:
    street = " ".join(x for x in (a.get("road") or a.get("pedestrian") or a.get("square"), a.get("house_number")) if x)
    city = a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or ""
    town = " ".join(x for x in (a.get("postcode"), city) if x)
    return ", ".join(x for x in (street, town) if x)


def _result(r: dict) -> dict:
    tags = r.get("extratags") or {}
    box = [float(x) for x in r.get("boundingbox", [0, 0, 0, 0])]
    website = tags.get("website") or tags.get("contact:website") or tags.get("url") or ""
    if website and not re.match(r"https?://", website):
        website = "https://" + website
    return {
        "name": r.get("name") or r.get("display_name", "").split(",")[0],
        "display": r.get("display_name", ""),
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "bbox": box,
        "osm_ref": f"{r.get('osm_type', '')}/{r.get('osm_id', '')}",
        "kind": _guess_kind(r.get("category", ""), r.get("type", "")),
        "address": _address(r.get("address") or {}),
        "opening_hours": tags.get("opening_hours", ""),
        "website": website,
        "phone": tags.get("phone") or tags.get("contact:phone") or "",
        "wikidata": tags.get("wikidata", ""),
        "wikipedia": tags.get("wikipedia", ""),
    }


def search(query: str, bbox: list | None = None, bounded: bool = False, limit: int = 6) -> list[dict]:
    """Place search. bbox = [south, north, west, east] prefers (or, with bounded, restricts to) that area."""
    params = {"q": query.strip(), "format": "jsonv2", "addressdetails": 1, "extratags": 1,
              "limit": limit, "accept-language": "de"}
    if bbox:
        s, n, w, e = bbox
        params["viewbox"] = f"{w:.4f},{n:.4f},{e:.4f},{s:.4f}"
        if bounded:
            params["bounded"] = 1
    out, seen = [], set()
    for r in _nominatim(params):
        hit = _result(r)
        if (hit["name"], hit["display"]) not in seen:  # e.g. a city and its municipality with the same label
            seen.add((hit["name"], hit["display"]))
            out.append(hit)
    return out


def search_area(lat: float, lon: float, bbox: list) -> list:
    """Search window around a destination: its bounding box, but at least ~9 km around the centre."""
    s, n, w, e = bbox
    pad_lat, pad_lon = 0.08, 0.08 / max(0.2, math.cos(math.radians(lat)))
    return [min(s, lat - pad_lat) - 0.02, max(n, lat + pad_lat) + 0.02,
            min(w, lon - pad_lon) - 0.02, max(e, lon + pad_lon) + 0.02]


# ---------- Routing ----------

_osrm_down_until = 0.0


def route(coords: list[tuple[float, float]], mode: str) -> dict | None:
    """Route along real ways through all (lat, lon) stops in order. None if routing is unavailable."""
    global _osrm_down_until
    if len(coords) < 2:
        return None
    pts = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in coords)
    key = f"route:{mode}:{hashlib.sha1(pts.encode()).hexdigest()}"
    hit = db.cache_get(key)
    if hit is not None:
        return hit
    if time.monotonic() < _osrm_down_until:
        return None
    try:
        r = _http.get(f"{OSRM_URL}/{OSRM_PROFILES.get(mode, 'routed-foot')}/route/v1/driving/{pts}",
                      params={"overview": "full", "geometries": "polyline", "steps": "false"}, timeout=8)
        r.raise_for_status()
        data = r.json()
        best = data["routes"][0]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        _osrm_down_until = time.monotonic() + 60  # don't hammer a failing service
        return None
    out = {
        "geometry": best["geometry"],
        "distance": round(best["distance"]),
        "duration": round(best["duration"]),
        "legs": [{"distance": round(leg["distance"]), "duration": round(leg["duration"])} for leg in best["legs"]],
    }
    db.cache_set(key, out)
    return out


# ---------- Public transport (Transitous) ----------

TRANSITOUS_URL = os.environ.get("TRANSITOUS_URL", "https://api.transitous.org")
# Transitous asks every client to name itself with a way of contact
TRANSIT_AGENT = f"Reiseplaner/1.0 ({CONTACT or 'https://github.com/qtmo0/reiseplaner'})"
TRANSIT_MODES = {"BUS": "Bus", "TRAM": "Tram", "SUBWAY": "U-Bahn", "METRO": "U-Bahn", "SUBURBAN": "S-Bahn", "RAIL": "Bahn",
                 "REGIONAL_RAIL": "Regionalbahn", "REGIONAL_FAST_RAIL": "Regionalbahn", "LONG_DISTANCE": "Fernzug",
                 "HIGHSPEED_RAIL": "Fernzug", "FERRY": "Fähre", "FUNICULAR": "Standseilbahn", "CABLE_CAR": "Seilbahn",
                 "AERIAL_LIFT": "Seilbahn", "COACH": "Fernbus"}
_transit_calls: list[float] = []


def transit(a: tuple, b: tuple, day, hour: int) -> dict | None:
    """Fastest public transport connection from a to b (lat, lon) leaving around hour:30 local time on `day`.
    None if there is none or the service is unreachable. Answers are cached per weekday and hour for two weeks."""
    key = f"transit:{a[0]:.4f},{a[1]:.4f}:{b[0]:.4f},{b[1]:.4f}:{day.weekday()}:{hour}"
    hit = db.cache_get(key, max_age_days=14)
    if hit is not None:
        return hit or None
    now = time.time()
    _transit_calls[:] = [t for t in _transit_calls if now - t < 86400]
    if len(_transit_calls) >= 300:  # stay far below the 720 requests a day the service allows without asking
        return None
    _transit_calls.append(now)
    # Local time from the longitude: close enough to pick a typical connection for that time of day
    utc_hour = hour - round(a[1] / 15)
    when = f"{day.isoformat()}T{utc_hour % 24:02d}:30:00Z"
    try:
        r = _http.get(f"{TRANSITOUS_URL}/api/v5/plan", headers={"User-Agent": TRANSIT_AGENT}, timeout=15, params={
            "fromPlace": f"{a[0]:.5f},{a[1]:.5f}", "toPlace": f"{b[0]:.5f},{b[1]:.5f}", "time": when, "numItineraries": 3})
        r.raise_for_status()
        options = [it for it in r.json().get("itineraries", []) if any(leg["mode"] != "WALK" for leg in it["legs"])]
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    if not options:
        db.cache_set(key, {})
        return None
    best = min(options, key=lambda it: it["duration"])
    rides = [leg for leg in best["legs"] if leg["mode"] != "WALK"]
    out = {
        "duration": best["duration"],
        "transfers": max(0, len(rides) - 1),
        "walk": sum(leg["duration"] for leg in best["legs"] if leg["mode"] == "WALK"),
        "lines": [{"kind": TRANSIT_MODES.get(leg["mode"], "Linie"),
                   "name": leg.get("displayName") or leg.get("routeShortName") or leg.get("routeLongName") or "",
                   "headsign": leg.get("headsign") or "", "from": leg["from"]["name"], "to": leg["to"]["name"],
                   "duration": leg["duration"]} for leg in rides],
        "segs": [{"m": "w" if leg["mode"] == "WALK" else "t", "g": leg["legGeometry"]["points"],
                  "p": leg["legGeometry"].get("precision", 6)} for leg in best["legs"] if leg.get("legGeometry")],
    }
    db.cache_set(key, out)
    return out


# ---------- Weather (Open-Meteo) ----------

def weather(lat: float, lon: float) -> dict:
    """Forecast per date for the next 16 days: {date: {tmax, tmin, pop, code, rain_from}}. Empty if unreachable."""
    key = f"weather:{lat:.2f},{lon:.2f}"
    hit = db.cache_get(key, max_age_days=0.125)  # three hours
    if hit is not None:
        return hit
    try:
        r = _http.get("https://api.open-meteo.com/v1/forecast", timeout=8, params={
            "latitude": f"{lat:.3f}", "longitude": f"{lon:.3f}", "timezone": "auto", "forecast_days": 16,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "hourly": "precipitation_probability"})
        r.raise_for_status()
        data = r.json()
        daily, hourly = data["daily"], data["hourly"]
    except (httpx.HTTPError, KeyError, ValueError):
        return {}
    out = {}
    for i, day in enumerate(daily["time"]):
        if daily["temperature_2m_max"][i] is None:
            continue
        # First hour between 8 and 21 o'clock with rain more likely than not
        wet = [int(t[11:13]) for t, p in zip(hourly["time"], hourly["precipitation_probability"])
               if t.startswith(day) and p is not None and p >= 50 and 8 <= int(t[11:13]) <= 21]
        out[day] = {"tmax": round(daily["temperature_2m_max"][i]), "tmin": round(daily["temperature_2m_min"][i]),
                    "pop": daily["precipitation_probability_max"][i], "code": daily["weather_code"][i],
                    "rain_from": wet[0] if wet else None}
    db.cache_set(key, out)
    return out


def climate(lat: float, lon: float, start: str, end: str) -> dict | None:
    """What the same dates were like in the last three years: {tmax, tmin, wet (share of days with rain), years}."""
    from datetime import date, timedelta
    key = f"climate:{lat:.2f},{lon:.2f}:{start[5:]}:{end[5:]}"
    hit = db.cache_get(key, max_age_days=120)
    if hit is not None:
        return hit or None
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    highs, lows, rain = [], [], []
    try:
        for back in (1, 2, 3):
            ya = a.replace(year=a.year - back, day=min(a.day, 28))
            while ya > date.today() - timedelta(7):  # the archive ends a few days before today
                ya = ya.replace(year=ya.year - 1)
            yb = ya + (b - a)
            r = _http.get("https://archive-api.open-meteo.com/v1/archive", timeout=10, params={
                "latitude": f"{lat:.3f}", "longitude": f"{lon:.3f}", "start_date": ya.isoformat(), "end_date": yb.isoformat(),
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum", "timezone": "auto"})
            r.raise_for_status()
            d = r.json()["daily"]
            highs += [v for v in d["temperature_2m_max"] if v is not None]
            lows += [v for v in d["temperature_2m_min"] if v is not None]
            rain += [v >= 1 for v in d["precipitation_sum"] if v is not None]
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    if not highs or not rain:
        return None
    out = {"tmax": round(sum(highs) / len(highs)), "tmin": round(sum(lows) / len(lows)),
           "wet": round(sum(rain) / len(rain), 2), "years": 3}
    db.cache_set(key, out)
    return out


# ---------- Wikipedia / Wikidata ----------

def _wiki_api(lang: str, params: dict) -> dict:
    r = _http.get(f"https://{lang}.wikipedia.org/w/api.php", params={"format": "json", "formatversion": 2, **params})
    r.raise_for_status()
    return r.json()


def wiki_page(lang: str, title: str) -> dict | None:
    """Plain text, link, coordinates and lead image of one article; None if it does not exist."""
    key = f"wiki:{lang}:{title}"
    hit = db.cache_get(key, max_age_days=90)
    if hit is not None:
        return hit or None
    try:
        data = _wiki_api(lang, {
            "action": "query", "titles": title, "redirects": 1,
            "prop": "extracts|coordinates|pageimages|info", "explaintext": 1, "exsectionformat": "plain",
            "inprop": "url", "piprop": "thumbnail|name", "pithumbsize": 800,
        })
        page = (data.get("query", {}).get("pages") or [{}])[0]
    except (httpx.HTTPError, ValueError):
        return None
    if page.get("missing") or not page.get("extract"):
        db.cache_set(key, {})
        return None
    coords = (page.get("coordinates") or [{}])[0]
    out = {
        "lang": lang,
        "title": page["title"],
        "url": page.get("fullurl", f"https://{lang}.wikipedia.org/wiki/{page['title'].replace(' ', '_')}"),
        "extract": page["extract"][:30000],
        "lat": coords.get("lat"),
        "lon": coords.get("lon"),
        "image": (page.get("thumbnail") or {}).get("source", ""),
        "image_page": f"https://commons.wikimedia.org/wiki/File:{page['pageimage']}" if page.get("pageimage") else "",
    }
    db.cache_set(key, out)
    return out


def wikidata_articles(qid: str) -> dict:
    """{'de': title, 'en': title} for a Wikidata item (only those that exist)."""
    key = f"wd:{qid}"
    hit = db.cache_get(key, max_age_days=90)
    if hit is not None:
        return hit
    try:
        r = _http.get("https://www.wikidata.org/w/api.php", params={
            "action": "wbgetentities", "ids": qid, "props": "sitelinks", "sitefilter": "dewiki|enwiki", "format": "json"})
        r.raise_for_status()
        links = r.json()["entities"][qid].get("sitelinks", {})
    except (httpx.HTTPError, KeyError, ValueError):
        return {}
    out = {k[:2]: v["title"] for k, v in links.items()}
    db.cache_set(key, out)
    return out


def find_article(place: dict) -> dict | None:
    """The Wikipedia article about a place, German preferred. Uses the links stored in OSM;
    an article title guessed by the AI only counts if the article's coordinates match the place."""
    candidates: list[tuple[str, str]] = []
    tag = place.get("wikipedia") or ""
    if ":" in tag:
        lang, title = tag.split(":", 1)
        candidates.append((lang, title))
    if place.get("wikidata"):
        links = wikidata_articles(place["wikidata"])
        candidates = ([("de", links["de"])] if "de" in links else []) + candidates + ([("en", links["en"])] if "en" in links else [])
    for lang, title in candidates:
        page = wiki_page(lang, title)
        if page:
            return page
    if place.get("wiki_hint"):
        page = wiki_page("de", place["wiki_hint"])
        if page and page["lat"] is not None and distance_m(page["lat"], page["lon"], place["lat"], place["lon"]) < 1500:
            return page
    return None


_NOTABLE = re.compile(r"kirche|kathedrale|basilika|kloster|dom\b|burg\b|schloss|palast|palais|festung|museum|galerie|"
                      r"platz|turm|denkmal|monument|park\b|garten|brücke|aussicht|theater|oper|markt|bauwerk|brunnen|"
                      r"aufzug|seilbahn|friedhof|bibliothek|buchhandlung|café|kaffeehaus|tempel|moschee|synagoge|"
                      r"triumphbogen|stadttor|rathaus|ruine|welterbe|sehenswürdigkeit", re.I)


def notable_nearby(lat: float, lon: float, limit: int) -> list[dict]:
    """Fallback without AI: Wikipedia articles about buildings, squares, museums and parks near a point,
    the most detailed articles first."""
    pages: dict[int, dict] = {}
    params = {"action": "query", "generator": "geosearch", "ggscoord": f"{lat}|{lon}", "ggsradius": 6000, "ggslimit": 200,
              "prop": "coordinates|info|description", "colimit": 200}
    cont: dict = {}
    try:
        for _ in range(6):  # results arrive in batches
            data = _wiki_api("de", {**params, **cont})
            for page in data.get("query", {}).get("pages", []):
                pages.setdefault(page["pageid"], {}).update(page)
            cont = data.get("continue") or {}
            if not cont:
                break
    except (httpx.HTTPError, ValueError):
        return []
    out = []
    for page in pages.values():
        desc = page.get("description", "")
        if not page.get("coordinates") or not _NOTABLE.search(desc) or re.search(r"unfall|unglück|anschlag", desc, re.I):
            continue
        low = desc.lower()
        kind = ("museum" if re.search(r"museum|galerie", low) else "cafe" if re.search(r"café|kaffeehaus", low)
                else "nature" if re.search(r"park\b|garten", low) else "sight")
        c = page["coordinates"][0]
        out.append({"name": re.sub(r"\s*\(.*\)$", "", page["title"]), "title": page["title"], "kind": kind,
                    "lat": c["lat"], "lon": c["lon"], "reason": desc[:1].upper() + desc[1:], "length": page.get("length", 0)})
    out.sort(key=lambda p: -p["length"])
    return out[:limit]
