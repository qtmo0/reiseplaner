"""Reiseplaner: REST API (trips, places, suggestions, accounts) and static frontend."""

import hashlib
import hmac
import json
import logging
import os
import queue
import secrets
import threading
import time
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import ai
import db
import geo
import hours

log = logging.getLogger("reiseplaner")
APP_TOKEN = os.environ.get("APP_TOKEN", "")
APP_VERSION = os.environ.get("APP_VERSION", "dev")
STATIC_DIR = Path(__file__).parent / "static"
COOKIE = "rp_session"
MAX_DAYS = 30
MAX_SUGGESTIONS = 60
WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


# ---------- Accounts ----------

def hash_pw(password: str) -> str:
    salt = secrets.token_hex(16)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def check_pw(password: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex(), digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(user_id: int, request: Request, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    db.run("INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?,?,?)", (_token_hash(token), user_id, time.time()))
    response.set_cookie(COOKIE, token, max_age=365 * 86400, httponly=True, samesite="lax",
                        secure=request.url.scheme == "https")


def current_user(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    return db.one("SELECT u.id, u.name, u.is_admin FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
                  (_token_hash(token),))


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Bitte melde dich an.")
    return user


_failed: dict[str, list[float]] = {}


def _throttle(request: Request) -> str:
    """At most 10 failed logins or registrations per address in 10 minutes."""
    ip = request.client.host if request.client else "?"
    recent = [t for t in _failed.get(ip, []) if time.time() - t < 600]
    _failed[ip] = recent
    if len(recent) >= 10:
        raise HTTPException(429, "Zu viele Versuche. Warte ein paar Minuten.")
    return ip


class LoginIn(BaseModel):
    name: str
    password: str


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=30)
    password: str = Field(min_length=8, max_length=200)
    code: str


@app.get("/api/health/ping")
def ping():
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    return {"user": current_user(request), "ai": ai.enabled(), "version": APP_VERSION}


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    ip = _throttle(request)
    user = db.one("SELECT * FROM users WHERE name=?", (body.name.strip(),))
    if not user or not check_pw(body.password, user["pw_hash"]):
        _failed[ip].append(time.time())
        raise HTTPException(403, "Name oder Passwort stimmt nicht.")
    start_session(user["id"], request, response)
    return {"user": {"id": user["id"], "name": user["name"], "is_admin": user["is_admin"]}}


@app.post("/api/auth/register")
def register(body: RegisterIn, request: Request, response: Response):
    """New account. The code is either the setup code from the server config or a trip's invite code."""
    ip = _throttle(request)
    code, name = body.code.strip(), body.name.strip()
    trip = db.one("SELECT id FROM trips WHERE invite_code=?", (code,))
    is_setup = bool(APP_TOKEN) and hmac.compare_digest(code, APP_TOKEN)
    if not trip and not is_setup:
        _failed[ip].append(time.time())
        raise HTTPException(403, "Der Code ist ungültig.")
    if len(name) < 2:
        raise HTTPException(422, "Der Name ist zu kurz.")
    if db.one("SELECT 1 FROM users WHERE name=?", (name,)):
        raise HTTPException(409, "Diesen Namen gibt es schon. Melde dich an oder wähle einen anderen.")
    first = not db.one("SELECT 1 FROM users")
    uid = db.run("INSERT INTO users (name, pw_hash, is_admin, created_at) VALUES (?,?,?,?)",
                 (name, hash_pw(body.password), int(is_setup and first), time.time()))
    if trip:
        db.run("INSERT OR IGNORE INTO trip_members (trip_id, user_id) VALUES (?,?)", (trip["id"], uid))
        touch(trip["id"])
    start_session(uid, request, response)
    return {"user": {"id": uid, "name": name, "is_admin": int(is_setup and first)}, "trip_id": trip["id"] if trip else None}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        db.run("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/invite/{code}")
def invite_info(code: str, request: Request):
    _throttle(request)
    trip = db.one("SELECT t.title, t.destination, t.start_date, t.end_date, u.name AS inviter "
                  "FROM trips t JOIN users u ON u.id=t.created_by WHERE t.invite_code=?", (code,))
    if not trip:
        raise HTTPException(404, "Diese Einladung gibt es nicht mehr.")
    return trip


@app.post("/api/invite/{code}/join")
def invite_join(code: str, user: dict = Depends(require_user)):
    trip = db.one("SELECT id FROM trips WHERE invite_code=?", (code,))
    if not trip:
        raise HTTPException(404, "Diese Einladung gibt es nicht mehr.")
    db.run("INSERT OR IGNORE INTO trip_members (trip_id, user_id) VALUES (?,?)", (trip["id"], user["id"]))
    touch(trip["id"])
    return {"trip_id": trip["id"]}


# ---------- Trips ----------

def touch(trip_id: int) -> None:
    db.run("UPDATE trips SET updated_at=? WHERE id=?", (time.time(), trip_id))


def member_trip(trip_id: int, user: dict) -> dict:
    trip = db.one("SELECT t.* FROM trips t JOIN trip_members m ON m.trip_id=t.id WHERE t.id=? AND m.user_id=?",
                  (trip_id, user["id"]))
    if not trip:
        raise HTTPException(404, "Reise nicht gefunden.")
    return trip


def member_place(place_id: int, user: dict) -> dict:
    place = db.one("SELECT p.* FROM places p JOIN trip_members m ON m.trip_id=p.trip_id WHERE p.id=? AND m.user_id=?",
                   (place_id, user["id"]))
    if not place:
        raise HTTPException(404, "Ort nicht gefunden.")
    return place


def day_count(trip: dict) -> int:
    return (date.fromisoformat(trip["end_date"]) - date.fromisoformat(trip["start_date"])).days + 1


def check_dates(start: str, end: str) -> None:
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except ValueError:
        raise HTTPException(422, "Das Datum ist ungültig.")
    if days < 1:
        raise HTTPException(422, "Das Ende liegt vor dem Anfang.")
    if days > MAX_DAYS:
        raise HTTPException(422, f"Eine Reise kann höchstens {MAX_DAYS} Tage dauern.")


WALK_LIMIT = 25 * 60  # a longer walk becomes public transport if a clearly faster connection exists


def _timetable_slot(trip: dict, day: int, leg: int) -> tuple[date, int]:
    """Date and hour to look up connections for. Timetables only reach a few weeks ahead, so a trip further
    away uses the same weekday of the coming week as a typical day."""
    d = date.fromisoformat(trip["start_date"]) + timedelta(day - 1)
    today = date.today()
    if not today <= d <= today + timedelta(6):
        d = today + timedelta((d.weekday() - today.weekday()) % 7 or 7)
    return d, min(21, 9 + leg * 3 // 2)


def _leg(trip: dict, a: dict, b: dict, origin: dict | None, day: int, index: int) -> dict:
    """How to get from place a to place b. origin is a when it is a stop (it carries the preference for
    this leg), None when the leg starts at the hotel."""
    pa, pb = (a["lat"], a["lon"]), (b["lat"], b["lon"])
    straight = [{"m": "t", "pts": [pa, pb]}]
    if trip["mode"] != "foot":
        r = geo.route([pa, pb], trip["mode"])
        return {"mode": trip["mode"], "distance": r and r["distance"], "duration": r and r["duration"],
                "segs": [{"m": "w", "g": r["geometry"], "p": 5}] if r else straight}
    pref = origin["leg_mode"] if origin else "auto"
    label = origin["walk_label"] if origin and pref == "walk" else ""
    via = json.loads(origin["walk_via"]) if label and origin["walk_via"] else None
    walk = geo.route([pa] + ([tuple(via)] if via else []) + [pb], "foot")
    if pref == "transit" or (pref == "auto" and (walk is None or walk["duration"] > WALK_LIMIT)):
        slot, hour = _timetable_slot(trip, day, index)
        t = geo.transit(pa, pb, slot, hour)
        if t and (pref == "transit" or walk is None or t["duration"] < walk["duration"] * 0.85):
            return {"mode": "transit", "distance": None, "duration": t["duration"], "segs": t["segs"], "weekday": slot.weekday(),
                    "transit": {k: t[k] for k in ("transfers", "walk", "lines")}}
        if pref == "transit" or walk is None:
            # No timetable data here: the leg stays marked as public transport, details come from the maps app
            return {"mode": "transit", "fallback": True, "distance": None, "duration": None, "segs": straight}
    return {"mode": "walk", "scenic": bool(label), "label": label, "distance": walk["distance"], "duration": walk["duration"],
            "segs": [{"m": "w", "g": walk["geometry"], "p": 5}]}


def day_routes(trip: dict, places: list[dict]) -> dict:
    """Per day: the legs from the hotel through all stops that are not rejected and back to the hotel."""
    hotel = next((p for p in places if p["id"] == trip["hotel_id"]), None)
    routes = {}
    for day in range(1, day_count(trip) + 1):
        stops = [p for p in places if p["day"] == day and p["status"] != "rejected" and p is not hotel]
        points = [hotel, *stops, hotel] if hotel and stops else stops
        if len(points) < 2:
            continue
        legs = [_leg(trip, a, b, None if a is hotel else a, day, i) for i, (a, b) in enumerate(zip(points, points[1:]))]
        routes[str(day)] = {
            "legs": legs,
            "distance": sum(leg["distance"] or 0 for leg in legs),
            "duration": sum(leg["duration"] or 0 for leg in legs),
            "open": sum(1 for leg in legs if leg["duration"] is None),  # legs without a known duration
        }
    return routes


def trip_weather(trip: dict) -> dict:
    """Forecast per trip day where one exists yet, plus what the dates were like in past years."""
    forecast = geo.weather(trip["lat"], trip["lon"])
    start = date.fromisoformat(trip["start_date"])
    days = {str(d + 1): forecast[(start + timedelta(d)).isoformat()] for d in range(day_count(trip))
            if (start + timedelta(d)).isoformat() in forecast}
    out = {"days": days}
    if len(days) < day_count(trip):
        out["usual"] = geo.climate(trip["lat"], trip["lon"], trip["start_date"], trip["end_date"])
    return out


def trip_payload(trip_id: int, user: dict) -> dict:
    trip = member_trip(trip_id, user)
    places = db.q("SELECT * FROM places WHERE trip_id=? ORDER BY day IS NULL, day, pos, id", (trip_id,))
    trip["days"] = day_count(trip)
    routes = day_routes(trip, places)
    votes: dict[int, list[int]] = {}
    for v in db.q("SELECT v.place_id, v.user_id FROM votes v JOIN places p ON p.id=v.place_id WHERE p.trip_id=?", (trip_id,)):
        votes.setdefault(v["place_id"], []).append(v["user_id"])
    start = date.fromisoformat(trip["start_date"])
    for p in places:
        p["meals"] = json.loads(p["meals"])
        p["info"] = json.loads(p["info"])
        # Planned for a weekday on which OSM says the place is closed (or closed at its meal times)
        planned = p["day"] and p["status"] != "rejected" and p["id"] != trip["hotel_id"]
        p["hours_issue"] = hours.issue(p["opening_hours"], start + timedelta(p["day"] - 1), p["meals"]) if planned else ""
        p["votes"] = votes.get(p["id"], [])
        del p["wiki_hint"], p["walk_via"]
    trip["bbox"] = json.loads(trip["bbox"])
    trip["job"] = json.loads(trip["job"])
    trip["replan"] = json.loads(trip["replan"]).get("msg", "")
    return {
        "trip": trip,
        "members": db.q("SELECT u.id, u.name FROM trip_members m JOIN users u ON u.id=m.user_id WHERE m.trip_id=? ORDER BY u.name",
                        (trip_id,)),
        "places": places,
        "routes": routes,
        "weather": trip_weather(trip),
    }


class TripIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    destination: str = Field(min_length=1, max_length=200)
    lat: float
    lon: float
    bbox: list[float] = Field(min_length=4, max_length=4)
    start_date: str
    end_date: str


class TripPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=80)
    start_date: str | None = None
    end_date: str | None = None
    mode: str | None = None


@app.get("/api/trips")
def list_trips(user: dict = Depends(require_user)):
    return db.q(
        "SELECT t.id, t.title, t.destination, t.start_date, t.end_date, "
        "(SELECT COUNT(*) FROM places p WHERE p.trip_id=t.id AND p.status!='rejected') AS place_count, "
        "(SELECT GROUP_CONCAT(u.name, ', ') FROM trip_members m2 JOIN users u ON u.id=m2.user_id WHERE m2.trip_id=t.id) AS member_names "
        "FROM trips t JOIN trip_members m ON m.trip_id=t.id WHERE m.user_id=? ORDER BY t.start_date DESC", (user["id"],))


@app.post("/api/trips")
def create_trip(body: TripIn, user: dict = Depends(require_user)):
    check_dates(body.start_date, body.end_date)
    now = time.time()
    with db.tx() as con:
        trip_id = con.execute(
            "INSERT INTO trips (title, destination, lat, lon, bbox, start_date, end_date, invite_code, created_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (body.title.strip(), body.destination.strip(), body.lat, body.lon, json.dumps(body.bbox), body.start_date,
             body.end_date, secrets.token_urlsafe(9), user["id"], now, now)).lastrowid
        con.execute("INSERT INTO trip_members (trip_id, user_id) VALUES (?,?)", (trip_id, user["id"]))
    return trip_payload(trip_id, user)


@app.get("/api/trips/{trip_id}")
def get_trip(trip_id: int, user: dict = Depends(require_user)):
    return trip_payload(trip_id, user)


@app.patch("/api/trips/{trip_id}")
def patch_trip(trip_id: int, body: TripPatch, user: dict = Depends(require_user)):
    trip = member_trip(trip_id, user)
    start, end = body.start_date or trip["start_date"], body.end_date or trip["end_date"]
    check_dates(start, end)
    mode = body.mode if body.mode in geo.OSRM_PROFILES else trip["mode"]
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    with db.tx() as con:
        con.execute("UPDATE trips SET title=?, start_date=?, end_date=?, mode=?, updated_at=? WHERE id=?",
                    (body.title.strip() if body.title else trip["title"], start, end, mode, time.time(), trip_id))
        # Places on days that no longer exist move to the ideas list
        con.execute("UPDATE places SET day=NULL WHERE trip_id=? AND day>?", (trip_id, days))
    return trip_payload(trip_id, user)


@app.delete("/api/trips/{trip_id}")
def delete_trip(trip_id: int, user: dict = Depends(require_user)):
    trip = member_trip(trip_id, user)
    if trip["created_by"] != user["id"]:
        raise HTTPException(403, "Nur wer die Reise angelegt hat, kann sie löschen.")
    db.run("DELETE FROM trips WHERE id=?", (trip_id,))
    return {"ok": True}


@app.post("/api/trips/{trip_id}/invite/rotate")
def rotate_invite(trip_id: int, user: dict = Depends(require_user)):
    member_trip(trip_id, user)
    db.run("UPDATE trips SET invite_code=?, updated_at=? WHERE id=?", (secrets.token_urlsafe(9), time.time(), trip_id))
    return trip_payload(trip_id, user)


@app.delete("/api/trips/{trip_id}/members/{user_id}")
def remove_member(trip_id: int, user_id: int, user: dict = Depends(require_user)):
    trip = member_trip(trip_id, user)
    if user_id == trip["created_by"]:
        raise HTTPException(403, "Wer die Reise angelegt hat, bleibt dabei.")
    if user_id != user["id"] and trip["created_by"] != user["id"]:
        raise HTTPException(403, "Andere entfernen kann nur, wer die Reise angelegt hat.")
    db.run("DELETE FROM trip_members WHERE trip_id=? AND user_id=?", (trip_id, user_id))
    touch(trip_id)
    return {"ok": True} if user_id == user["id"] else trip_payload(trip_id, user)


# ---------- Places ----------

class PlaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    lat: float
    lon: float
    kind: str = "other"
    meals: list[str] = []
    day: int | None = None
    osm_ref: str = ""
    address: str = ""
    opening_hours: str = ""
    website: str = ""
    phone: str = ""
    wikidata: str = ""
    wikipedia: str = ""


class PlacePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    kind: str | None = None
    meals: list[str] | None = None
    day: int | None = None
    clear_day: bool = False
    status: str | None = None
    note: str | None = Field(None, max_length=2000)
    leg_mode: str | None = None  # way to the next stop: auto|walk|transit


class OrderIn(BaseModel):
    day: int | None = None
    ids: list[int]


def clean_meals(kind: str, meals: list[str]) -> str:
    return json.dumps([m for m in geo.MEALS if m in meals] if kind in geo.FOOD_KINDS else [])


def insert_place(trip_id: int, user_id: int | None, f: dict) -> int:
    kind = f.get("kind") if f.get("kind") in geo.KINDS else "other"
    with db.tx() as con:
        pos = con.execute("SELECT COALESCE(MAX(pos),0)+1 FROM places WHERE trip_id=? AND day IS ?", (trip_id, f.get("day"))).fetchone()[0]
        return con.execute(
            "INSERT INTO places (trip_id, name, kind, meals, lat, lon, status, day, pos, source, reason, verified, osm_ref, address, "
            "opening_hours, website, phone, wikidata, wikipedia, wiki_hint, leg_mode, walk_label, walk_via, created_by, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (trip_id, f["name"][:120], kind, clean_meals(kind, f.get("meals", [])), f["lat"], f["lon"], f.get("status", "accepted"),
             f.get("day"), pos, f.get("source", "manual"), f.get("reason", ""), int(f.get("verified", 0)), f.get("osm_ref", ""),
             f.get("address", ""), f.get("opening_hours", ""), f.get("website", ""), f.get("phone", ""), f.get("wikidata", ""),
             f.get("wikipedia", ""), f.get("wiki_hint", ""), "walk" if f.get("walk_label") else "auto", f.get("walk_label", ""),
             f.get("walk_via", ""), user_id, time.time())).lastrowid


@app.get("/api/geocode")
def geocode(q: str, trip_id: int | None = None, user: dict = Depends(require_user)):
    """Place search in OpenStreetMap; with trip_id, results near the destination come first."""
    if len(q.strip()) < 2:
        return []
    area = None
    if trip_id:
        trip = member_trip(trip_id, user)
        area = geo.search_area(trip["lat"], trip["lon"], json.loads(trip["bbox"]))
    try:
        return geo.search(q, area)
    except Exception:
        raise HTTPException(502, "Die Ortssuche ist gerade nicht erreichbar.")


@app.post("/api/trips/{trip_id}/places")
def add_place(trip_id: int, body: PlaceIn, user: dict = Depends(require_user)):
    trip = member_trip(trip_id, user)
    fields = body.model_dump()
    if fields["day"] is not None and not 1 <= fields["day"] <= day_count(trip):
        fields["day"] = None
    fields["verified"] = bool(body.osm_ref)
    enqueue_info(insert_place(trip_id, user["id"], fields))
    touch(trip_id)
    return trip_payload(trip_id, user)


@app.patch("/api/places/{place_id}")
def patch_place(place_id: int, body: PlacePatch, user: dict = Depends(require_user)):
    place = member_place(place_id, user)
    trip = member_trip(place["trip_id"], user)
    kind = body.kind if body.kind in geo.KINDS else place["kind"]
    meals = clean_meals(kind, body.meals if body.meals is not None else json.loads(place["meals"]))
    status = body.status if body.status in ("suggested", "accepted", "rejected") else place["status"]
    day, pos = place["day"], place["pos"]
    if body.clear_day or (body.day is not None and 1 <= body.day <= day_count(trip)):
        new_day = None if body.clear_day else body.day
        if new_day != day:
            day = new_day
            pos = db.one("SELECT COALESCE(MAX(pos),0)+1 AS p FROM places WHERE trip_id=? AND day IS ?", (trip["id"], day))["p"]
    leg_mode, walk_label = place["leg_mode"], place["walk_label"]
    if body.leg_mode in ("auto", "walk", "transit"):
        # Choosing a mode by hand drops a stroll suggested by the AI
        leg_mode, walk_label = body.leg_mode, ""
    db.run("UPDATE places SET name=?, kind=?, meals=?, status=?, day=?, pos=?, note=?, leg_mode=?, walk_label=? WHERE id=?",
           (body.name.strip() if body.name else place["name"], kind, meals, status, day, pos,
            body.note if body.note is not None else place["note"], leg_mode, walk_label, place_id))
    if status == "accepted" and place["info_status"] == "none":
        enqueue_info(place_id)
    touch(trip["id"])
    return trip_payload(trip["id"], user)


@app.delete("/api/places/{place_id}")
def delete_place(place_id: int, user: dict = Depends(require_user)):
    place = member_place(place_id, user)
    db.run("DELETE FROM places WHERE id=?", (place_id,))
    db.run("UPDATE trips SET hotel_id=NULL WHERE hotel_id=?", (place_id,))
    touch(place["trip_id"])
    return trip_payload(place["trip_id"], user)


@app.post("/api/places/{place_id}/vote")
def vote(place_id: int, user: dict = Depends(require_user)):
    place = member_place(place_id, user)
    if db.one("SELECT 1 FROM votes WHERE place_id=? AND user_id=?", (place_id, user["id"])):
        db.run("DELETE FROM votes WHERE place_id=? AND user_id=?", (place_id, user["id"]))
    else:
        db.run("INSERT INTO votes (place_id, user_id) VALUES (?,?)", (place_id, user["id"]))
    touch(place["trip_id"])
    return trip_payload(place["trip_id"], user)


@app.post("/api/places/{place_id}/info")
def load_info(place_id: int, user: dict = Depends(require_user)):
    """Fetch the place texts if that hasn't happened yet (suggestions get them on first open)."""
    place = member_place(place_id, user)
    if place["info_status"] == "none":
        enqueue_info(place_id)
    return trip_payload(place["trip_id"], user)


@app.put("/api/trips/{trip_id}/order")
def set_order(trip_id: int, body: OrderIn, user: dict = Depends(require_user)):
    trip = member_trip(trip_id, user)
    day = body.day if body.day is not None and 1 <= body.day <= day_count(trip) else None
    with db.tx() as con:
        for pos, pid in enumerate(body.ids, start=1):
            con.execute("UPDATE places SET day=?, pos=? WHERE id=? AND trip_id=?", (day, pos, pid, trip_id))
    touch(trip_id)
    return trip_payload(trip_id, user)


@app.post("/api/trips/{trip_id}/accept")
def accept_all(trip_id: int, day: int | None = None, user: dict = Depends(require_user)):
    member_trip(trip_id, user)
    rows = db.q("SELECT id, info_status FROM places WHERE trip_id=? AND status='suggested'" + (" AND day=?" if day else ""),
                (trip_id, day) if day else (trip_id,))
    with db.tx() as con:
        con.executemany("UPDATE places SET status='accepted' WHERE id=?", [(r["id"],) for r in rows])
    for r in rows:
        if r["info_status"] == "none":
            enqueue_info(r["id"])
    touch(trip_id)
    return trip_payload(trip_id, user)


# ---------- Hotel ----------

class HotelIn(BaseModel):
    place_id: int | None = None   # an existing place of the trip ...
    place: PlaceIn | None = None  # ... or a search result to add


@app.put("/api/trips/{trip_id}/hotel")
def set_hotel(trip_id: int, body: HotelIn, user: dict = Depends(require_user)):
    """The place every day starts and ends at. Empty body removes it."""
    member_trip(trip_id, user)
    hotel_id = None
    if body.place:
        fields = body.place.model_dump()
        fields.update(kind="lodging", day=None, verified=bool(body.place.osm_ref))
        hotel_id = insert_place(trip_id, user["id"], fields)
        enqueue_info(hotel_id)
    elif body.place_id:
        hotel_id = member_place(body.place_id, user)["id"]
        db.run("UPDATE places SET day=NULL, status='accepted' WHERE id=? AND trip_id=?", (hotel_id, trip_id))
    db.run("UPDATE trips SET hotel_id=?, updated_at=? WHERE id=?", (hotel_id, time.time(), trip_id))
    return trip_payload(trip_id, user)


# ---------- Replanning around the weather ----------

def _planned(trip: dict) -> list[dict]:
    return db.q("SELECT id, name, kind, meals, day, pos FROM places WHERE trip_id=? AND day IS NOT NULL AND status!='rejected' "
                "AND id IS NOT ? ORDER BY day, pos, id", (trip["id"], trip["hotel_id"]))


def _weather_lines(trip: dict) -> list[str]:
    """One line per trip day with a forecast, for the AI."""
    start = date.fromisoformat(trip["start_date"])
    lines = []
    for day, w in sorted(trip_weather(trip)["days"].items(), key=lambda kv: int(kv[0])):
        d = start + timedelta(int(day) - 1)
        rain = f", Regen wahrscheinlich ab etwa {w['rain_from']} Uhr" if w["rain_from"] is not None else ""
        lines.append(f"Tag {day} ({WEEKDAYS[d.weekday()]}): {w['tmin']} bis {w['tmax']} Grad, Regenwahrscheinlichkeit {w['pop']} %{rain}")
    return lines


def replan_job(trip_id: int) -> None:
    try:
        trip = db.one("SELECT * FROM trips WHERE id=?", (trip_id,))
        before = _planned(trip)
        result = ai.replan(trip["destination"], day_count(trip), _weather_lines(trip), before)
        known = {p["id"]: p for p in before}
        days = day_count(trip)
        moves = [(it["day"], it["order"], it["id"]) for it in result["plan"] if it["id"] in known and 1 <= it["day"] <= days]
        with db.tx() as con:
            con.executemany("UPDATE places SET day=?, pos=? WHERE id=?", moves)
            con.execute("UPDATE trips SET replan=? WHERE id=?", (json.dumps(
                {"msg": result["summary"].strip(), "prev": [[p["id"], p["day"], p["pos"]] for p in before]}, ensure_ascii=False), trip_id))
        day_routes(trip, db.q("SELECT * FROM places WHERE trip_id=? ORDER BY day, pos, id", (trip_id,)))
        set_job(trip_id, "idle")
    except ai.AIError as exc:
        set_job(trip_id, "error", str(exc))
    except Exception:
        log.exception("replan job failed")
        set_job(trip_id, "error", "Das Umplanen hat nicht geklappt. Versuch es noch einmal.")


@app.post("/api/trips/{trip_id}/replan")
def replan(trip_id: int, user: dict = Depends(require_user)):
    """Let the AI move the planned places between days and reorder them to suit the forecast."""
    trip = member_trip(trip_id, user)
    if not ai.enabled():
        raise HTTPException(400, "Umplanen braucht einen Claude-API-Schlüssel.")
    if json.loads(trip["job"]).get("state") == "running":
        raise HTTPException(409, "Es läuft gerade schon eine Planung.")
    if not _weather_lines(trip):
        raise HTTPException(400, "Für diese Reise gibt es noch keine Wettervorhersage.")
    set_job(trip_id, "running", "Claude plant die Tage nach dem Wetter um …")
    threading.Thread(target=replan_job, args=(trip_id,), daemon=True).start()
    return trip_payload(trip_id, user)


@app.post("/api/trips/{trip_id}/replan/{action}")
def replan_done(trip_id: int, action: str, user: dict = Depends(require_user)):
    """action: undo puts every place back where it was before replanning, keep just clears the notice."""
    trip = member_trip(trip_id, user)
    if action == "undo":
        with db.tx() as con:
            con.executemany("UPDATE places SET day=?, pos=? WHERE id=? AND trip_id=?",
                            [(day, pos, pid, trip_id) for pid, day, pos in json.loads(trip["replan"]).get("prev", [])])
    db.run("UPDATE trips SET replan='{}', updated_at=? WHERE id=?", (time.time(), trip_id))
    return trip_payload(trip_id, user)


# ---------- Suggestions (background job per trip) ----------

class SuggestIn(BaseModel):
    wishes: str = Field("", max_length=1000)
    day: int | None = None


def set_job(trip_id: int, state: str, msg: str = "") -> None:
    db.run("UPDATE trips SET job=?, updated_at=? WHERE id=?",
           (json.dumps({"state": state, "msg": msg}, ensure_ascii=False), time.time(), trip_id))


def _locate(name: str, lat: float, lon: float, trip: dict, area: list) -> dict | None:
    """Find an AI-suggested place in OpenStreetMap. The AI's own coordinates only pick between several hits."""
    hits = geo.search(name, area, bounded=True, limit=4) or [
        h for h in geo.search(f"{name}, {trip['destination']}", limit=3)
        if geo.distance_m(h["lat"], h["lon"], trip["lat"], trip["lon"]) < 80_000]
    if not hits:
        return None
    if not (abs(lat) <= 90 and abs(lon) <= 180 and geo.distance_m(lat, lon, trip["lat"], trip["lon"]) < 80_000):
        return hits[0]
    best = min(hits, key=lambda h: geo.distance_m(h["lat"], h["lon"], lat, lon))
    # A hit far from where the AI expects the place is probably something else with the same name
    return best if geo.distance_m(best["lat"], best["lon"], lat, lon) < 3000 else None


def _wiki_items(trip: dict, days: int, known: set[str], only_day: int | None) -> list[dict]:
    """Without an API key: prominent Wikipedia places near the destination, split into days from west to east."""
    per_day = 5
    found = [p for p in geo.notable_nearby(trip["lat"], trip["lon"], 60) if p["name"].lower() not in known]
    if only_day:
        return [{**p, "day": only_day, "order": i} for i, p in enumerate(found[:4])]
    found = sorted(found[:days * per_day], key=lambda p: p["lon"])
    items = []
    for d in range(days):
        rest = found[d * per_day:(d + 1) * per_day]
        here = rest[:1]
        while len(here) < len(rest):  # nearest neighbour gives a walkable order
            last = here[-1]
            here.append(min((p for p in rest if p not in here),
                            key=lambda p: geo.distance_m(last["lat"], last["lon"], p["lat"], p["lon"])))
        items += [{**p, "day": d + 1, "order": i} for i, p in enumerate(here)]
    return items


def suggest_job(trip_id: int, user_id: int, wishes: str, only_day: int | None) -> None:
    try:
        trip = db.one("SELECT * FROM trips WHERE id=?", (trip_id,))
        days = day_count(trip)
        rows = db.q("SELECT id, name, day, status, osm_ref FROM places WHERE trip_id=?", (trip_id,))
        hotel = next((r["name"] for r in rows if r["id"] == trip["hotel_id"]), None)
        known_names = {r["name"].lower() for r in rows}
        known_refs = {r["osm_ref"] for r in rows if r["osm_ref"]}
        use_ai = ai.enabled()
        if use_ai:
            start = date.fromisoformat(trip["start_date"])
            labels = [f"{WEEKDAYS[(start + timedelta(d)).weekday()]}, {(start + timedelta(d)):%d.%m.%Y}" for d in range(days)]
            existing = [r["name"] + (" (abgelehnt)" if r["status"] == "rejected" else f" (Tag {r['day']})" if r["day"] else "")
                        for r in rows if r["id"] != trip["hotel_id"]]
            items = ai.suggest(trip["destination"], labels, existing, wishes, only_day, hotel, _weather_lines(trip))
        else:
            set_job(trip_id, "running", "Suche bekannte Orte bei Wikipedia …")
            items = _wiki_items(trip, days, known_names, only_day)
        items = sorted(items, key=lambda it: (it["day"] or 99, it["order"]))[:MAX_SUGGESTIONS]
        area = geo.search_area(trip["lat"], trip["lon"], json.loads(trip["bbox"]))
        added = 0
        for i, it in enumerate(items, start=1):
            name = it["name"].strip()
            if not name or name.lower() in known_names:
                continue
            fields = {"name": name, "kind": it["kind"], "meals": it.get("meals", []), "lat": it["lat"], "lon": it["lon"],
                      "day": only_day or (it["day"] if 1 <= it["day"] <= days else None), "status": "suggested",
                      "reason": it.get("reason", "").strip(), "source": "ai" if use_ai else "wiki"}
            if use_ai:
                set_job(trip_id, "running", f"Prüfe Orte in OpenStreetMap ({i} von {len(items)}) …")
                fields["wiki_hint"] = it.get("wikipedia_de", "").strip()
                hit = _locate(name, it["lat"], it["lon"], trip, area)
                if hit:
                    if hit["osm_ref"] in known_refs:
                        continue
                    known_refs.add(hit["osm_ref"])
                    fields.update({k: hit[k] for k in ("lat", "lon", "osm_ref", "address", "opening_hours", "website",
                                                       "phone", "wikidata", "wikipedia")}, verified=True)
                elif not (abs(it["lat"]) <= 90 and geo.distance_m(it["lat"], it["lon"], trip["lat"], trip["lon"]) < 80_000):
                    continue  # neither found nor plausibly located: drop it
                if it.get("walk_to_next", "").strip():
                    fields["walk_label"] = it["walk_to_next"].strip()[:120]
                    # A point the stroll should pass, only if OSM knows it and it is near the stop
                    via = it.get("walk_via", "").strip() and geo.search(it["walk_via"].strip(), area, bounded=True, limit=1)
                    if via and geo.distance_m(via[0]["lat"], via[0]["lon"], fields["lat"], fields["lon"]) < 2500:
                        fields["walk_via"] = json.dumps([via[0]["lat"], via[0]["lon"]])
            else:
                fields.update(verified=True, wikipedia=f"de:{it['title']}")
            known_names.add(name.lower())
            insert_place(trip_id, user_id, fields)
            added += 1
        if not added:
            raise ai.AIError("Es wurden keine neuen Orte gefunden.")
        day_routes(trip, db.q("SELECT * FROM places WHERE trip_id=? ORDER BY day, pos, id", (trip_id,)))  # warm the route cache
        set_job(trip_id, "idle")
    except ai.AIError as exc:
        set_job(trip_id, "error", str(exc))
    except Exception:
        log.exception("suggest job failed")
        set_job(trip_id, "error", "Die Vorschläge konnten nicht erstellt werden. Versuch es noch einmal.")


@app.post("/api/trips/{trip_id}/suggest")
def suggest(trip_id: int, body: SuggestIn, user: dict = Depends(require_user)):
    trip = member_trip(trip_id, user)
    if json.loads(trip["job"]).get("state") == "running":
        raise HTTPException(409, "Es werden gerade schon Vorschläge erstellt.")
    day = body.day if body.day is not None and 1 <= body.day <= day_count(trip) else None
    db.run("UPDATE trips SET wishes=? WHERE id=?", (body.wishes.strip(), trip_id))
    set_job(trip_id, "running", "Claude stellt Orte und Tagesrouten zusammen …" if ai.enabled() else "Suche Orte …")
    threading.Thread(target=suggest_job, args=(trip_id, user["id"], body.wishes.strip(), day), daemon=True).start()
    return trip_payload(trip_id, user)


@app.post("/api/trips/{trip_id}/job/dismiss")
def dismiss_job(trip_id: int, user: dict = Depends(require_user)):
    trip = member_trip(trip_id, user)
    if json.loads(trip["job"]).get("state") == "error":
        set_job(trip_id, "idle")
    return trip_payload(trip_id, user)


# ---------- Place texts (one background worker) ----------

_info_queue: "queue.Queue[int]" = queue.Queue()


def enqueue_info(place_id: int) -> None:
    db.run("UPDATE places SET info_status='pending' WHERE id=?", (place_id,))
    _info_queue.put(place_id)


def _lead(extract: str) -> str:
    """Opening of an article: whole paragraphs up to roughly 700 characters."""
    out = ""
    for para in extract.split("\n\n\n")[0].split("\n"):  # text before the first section heading
        para = para.strip()
        if not para:
            continue
        if out and len(out) + len(para) > 700:
            break
        out += ("\n\n" if out else "") + para
    if len(out) > 900:
        out = out[:900].rsplit(". ", 1)[0] + "."
    return out


def build_info(place: dict) -> dict:
    page = geo.find_article(place)
    if not page:
        return {}
    info = {"wiki_url": page["url"], "wiki_title": page["title"], "wiki_lang": page["lang"],
            "image": page["image"], "image_page": page["image_page"]}
    if ai.enabled():
        try:
            info.update(ai.place_info(place["name"], page["title"], page["extract"]), by="ai")
            return info
        except ai.AIError as exc:
            log.warning("place info for %s failed: %s", place["name"], exc)
    info.update(summary=_lead(page["extract"]), history="", facts=[], by="extract")
    return info


def _info_worker() -> None:
    while True:
        place_id = _info_queue.get()
        place = db.one("SELECT * FROM places WHERE id=?", (place_id,))
        if not place:
            continue
        info = {}
        try:
            info = build_info(place)
        except Exception:
            log.exception("place info failed")
        db.run("UPDATE places SET info=?, info_status='done' WHERE id=?", (json.dumps(info, ensure_ascii=False), place_id))
        touch(place["trip_id"])


@app.on_event("startup")
def startup() -> None:
    db.init()
    if not APP_TOKEN:
        log.warning("APP_TOKEN is not set: nobody can create the first account.")
    # Jobs that were running when the server stopped
    db.run("UPDATE trips SET job='{\"state\":\"idle\"}' WHERE job LIKE '%running%'")
    threading.Thread(target=_info_worker, daemon=True).start()
    for row in db.q("SELECT id FROM places WHERE info_status='pending'"):
        _info_queue.put(row["id"])


# ---------- Frontend ----------

@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"  # browser revalidates, so updates show up right away
    return response


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
