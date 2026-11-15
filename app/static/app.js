"use strict";
// Reiseplaner frontend: plain JS, no build step. State lives in S; every change re-renders list, detail and map from it.

const KINDS = {
  sight: "Sehenswürdigkeit", museum: "Museum", nature: "Park & Natur", restaurant: "Restaurant", cafe: "Café",
  bar: "Bar", shop: "Einkaufen", activity: "Aktivität", lodging: "Unterkunft", other: "Sonstiges",
};
const MEALS = { breakfast: "Frühstück", lunch: "Mittagessen", dinner: "Abendessen" };
const FOOD = ["restaurant", "cafe", "bar"];
const MODES = { foot: "zu Fuß und mit Öffis", bike: "mit dem Rad", car: "mit dem Auto" };
const WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];
const PEEK = 148; // visible height of the collapsed sheet on phones

const ICON = {
  back: '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>',
  close: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
  spark: '<svg viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/></svg>',
  nav: '<svg viewBox="0 0 24 24"><path d="M21 3L3 10.5l7.5 3L13.5 21z"/></svg>',
  users: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.4 3.2-5.5 6.5-5.5s5.9 2.1 6.5 5.5M16 4.8a3.5 3.5 0 0 1 0 6.4M18.5 14.9c1.6.9 2.7 2.6 3 5.1"/></svg>',
  dots: '<svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  grip: '<svg viewBox="0 0 24 24"><path d="M5 9h14M5 15h14"/></svg>',
  thumb: '<svg viewBox="0 0 24 24"><path d="M7 11v9H4v-9zM7 11l4-8c1.7 0 2.6 1.2 2.3 2.8L12.7 9H18a2 2 0 0 1 2 2.4l-1.3 6.9A2 2 0 0 1 16.700 20H7"/></svg>',
  locate: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.5"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>',
  layers: '<svg viewBox="0 0 24 24"><path d="M12 3l9 5-9 5-9-5zM3 13l9 5 9-5"/></svg>',
  bed: '<svg viewBox="0 0 24 24"><path d="M3 18v-9M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5M7 11.500a1.500 1.500 0 1 0 0-.010"/></svg>',
  walk: '<svg viewBox="0 0 24 24"><circle cx="13" cy="4.500" r="1.500"/><path d="M9 21l2.500-6-2-2.500 1-5 3 3 3 1M7 12l1.500-4 3.500-1M13 15.500l2 5.500"/></svg>',
  bus: '<svg viewBox="0 0 24 24"><rect x="5" y="4" width="14" height="13" rx="2"/><path d="M5 11h14M8 17v2.500M16 17v2.500M8.500 14h.010M15.500 14h.010"/></svg>',
  tree: '<svg viewBox="0 0 24 24"><path d="M12 21v-7M12 14a5 5 0 0 1-4.500-7.200A4.500 4.500 0 0 1 16.500 6.800 5 5 0 0 1 12 14zM9 21h6"/></svg>',
  sun: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.600 5.600l1.400 1.400M17 17l1.400 1.400M5.600 18.400L7 17M17 7l1.400-1.400"/></svg>',
  cloud: '<svg viewBox="0 0 24 24"><path d="M7 18a4 4 0 0 1-.500-7.970A5.500 5.500 0 0 1 17.200 9.050 4.500 4.500 0 0 1 17 18z"/></svg>',
  rain: '<svg viewBox="0 0 24 24"><path d="M7 15a4 4 0 0 1-.500-7.970A5.500 5.500 0 0 1 17.200 6.050 4.500 4.500 0 0 1 17 15M8.500 18l-1 2.500M12.500 18l-1 2.500M16.500 18l-1 2.500"/></svg>',
  out: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
};

const S = {
  me: null, ai: false, version: "",
  data: null,          // { trip, members, places, routes } of the open trip
  view: "all",         // "all" | day number | "ideas"
  filters: new Set(),  // "k:<kind>" and "m:<meal>"; a place shows if it matches any of them
  grouped: false,      // separate lists per kind and meal instead of plan order
  sel: null,           // id of the place shown in the detail view
  showRejected: false,
  offline: false,
};
let map = null, mapLayer = null, meMarker = null, pollTimer = null, dragging = false;

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const isDesktop = () => matchMedia("(min-width: 900px)").matches;

// ---------- Helpers ----------

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function api(path, opts = {}) {
  const method = opts.method || "GET";
  let res;
  try {
    res = await fetch("/api" + path, {
      method, credentials: "same-origin",
      headers: opts.body ? { "Content-Type": "application/json" } : {},
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
  } catch (err) {
    throw new ApiError(method === "GET" ? "Keine Verbindung zum Server." : "Keine Verbindung. Ändern geht nur online.", 0);
  }
  if (method === "GET") setOffline(res.headers.get("X-From-Cache") === "1");
  const data = await res.json().catch(() => null);
  if (res.status === 401 && S.me) { S.me = null; router(); }
  if (!res.ok) throw new ApiError(typeof data?.detail === "string" ? data.detail : "Das hat nicht geklappt. Bitte prüfe die Eingaben.", res.status);
  return data;
}

function setOffline(flag) {
  if (S.offline === flag) return;
  S.offline = flag;
  document.body.classList.toggle("offline", flag);
}

let toastTimer;
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 3500);
}

const dayDate = (trip, day) => { const d = new Date(trip.start_date + "T12:00:00"); d.setDate(d.getDate() + day - 1); return d; };
const fmtDay = (d) => d.toLocaleDateString("de-DE", { weekday: "short", day: "numeric", month: "numeric" });
function fmtRange(a, b) {
  const x = new Date(a + "T12:00:00"), y = new Date(b + "T12:00:00");
  const long = { day: "numeric", month: "long", year: "numeric" };
  if (a === b) return x.toLocaleDateString("de-DE", long);
  const first = x.getFullYear() !== y.getFullYear() ? long : x.getMonth() !== y.getMonth() ? { day: "numeric", month: "long" } : { day: "numeric" };
  return x.toLocaleDateString("de-DE", first) + (first.month ? " – " : ".–") + y.toLocaleDateString("de-DE", long);
}
const fmtDist = (m) => (m < 950 ? Math.round(m / 10) * 10 + " m" : (m / 1000).toFixed(1).replace(".", ",") + " km");
function fmtDur(s) {
  const min = Math.max(1, Math.round(s / 60));
  return min < 60 ? min + " min" : Math.floor(min / 60) + " h" + (min % 60 ? " " + (min % 60) + " min" : "");
}

// OSM opening_hours syntax, made readable in German
function fmtHours(raw) {
  const words = { Mo: "Mo", Tu: "Di", We: "Mi", Th: "Do", Fr: "Fr", Sa: "Sa", Su: "So", PH: "Feiertage", off: "geschlossen", closed: "geschlossen" };
  if (raw.trim() === "24/7") return ["durchgehend geöffnet"];
  return raw.split(";").map((part) => part.trim().replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su|PH|off|closed)\b/g, (w) => words[w])
    .replace(/-/g, "–").replace(/,(?=\S)/g, ", ")).filter(Boolean);
}

// Google's encoded polyline format, as returned by OSRM
function decodePolyline(str, precision = 5) {
  const out = [], scale = 10 ** precision;
  let i = 0, lat = 0, lon = 0;
  while (i < str.length) {
    for (const which of [0, 1]) {
      let shift = 0, result = 0, b;
      do { b = str.charCodeAt(i++) - 63; result |= (b & 31) << shift; shift += 5; } while (b >= 32);
      const delta = result & 1 ? ~(result >> 1) : result >> 1;
      if (which === 0) lat += delta; else lon += delta;
    }
    out.push([lat / scale, lon / scale]);
  }
  return out;
}

// ---------- Handover to Apple Maps / Google Maps ----------

const ll = (p) => `${p.lat.toFixed(6)},${p.lon.toFixed(6)}`;

function placeLinks(p) {
  const text = p.verified && p.address ? `${p.name}, ${p.address}` : ll(p);
  return {
    apple: `https://maps.apple.com/place?coordinate=${ll(p)}&name=${encodeURIComponent(p.name)}`,
    google: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(text)}`,
  };
}

// Both apps take a limited number of stops per link, so long days are split into parts of ten.
// The first part starts at the current position, each further part at the last stop of the one before.
function routeLinks(stops, mode) {
  const apple = { foot: "walking", bike: "cycling", car: "driving" }[mode];
  const google = { foot: "walking", bike: "bicycling", car: "driving" }[mode];
  const parts = [];
  for (let i = 0; i < stops.length; i += 10) {
    const chunk = stops.slice(i, i + 10), from = i ? stops[i - 1] : null;
    const via = chunk.slice(0, -1), last = chunk[chunk.length - 1];
    parts.push({
      from: i + 1, to: i + chunk.length,
      apple: "https://maps.apple.com/directions?" + (from ? `source=${ll(from)}&` : "") + via.map((s) => `waypoint=${ll(s)}&`).join("")
        + `destination=${ll(last)}&mode=${apple}`,
      google: "https://www.google.com/maps/dir/?api=1" + (from ? `&origin=${ll(from)}` : "") + `&destination=${ll(last)}`
        + (via.length ? `&waypoints=${encodeURIComponent(via.map(ll).join("|"))}` : "") + `&travelmode=${google}`,
    });
  }
  return parts;
}

// ---------- Selectors over the open trip ----------

const hotel = () => S.data.places.find((p) => p.id === S.data.trip.hotel_id) || null;
const active = () => S.data.places.filter((p) => p.status !== "rejected" && p.id !== S.data.trip.hotel_id);
// The points a day's legs connect: hotel, stops, hotel (or just the stops without a hotel)
function dayPoints(day) {
  const stops = dayStops(day), h = hotel();
  return h && stops.length ? [h, ...stops, h] : stops;
}
const weatherIcon = (code) => (code <= 1 ? ICON.sun : code <= 48 ? ICON.cloud : ICON.rain);
const dayStops = (day) => active().filter((p) => p.day === day);
const matches = (p) => !S.filters.size || S.filters.has("k:" + p.kind) || p.meals.some((m) => S.filters.has("m:" + m));
const inView = (p) => S.view === "all" || (S.view === "ideas" ? p.day == null : p.day === S.view);
const visible = () => active().filter((p) => inView(p) && matches(p));
const stopNumber = (p) => (p.day == null ? "" : dayStops(p.day).indexOf(p) + 1);
const place = (id) => S.data.places.find((p) => p.id === id);
const sortable = () => S.view !== "all" && !S.filters.size && !S.grouped && !S.offline;

// ---------- Modal ----------

function modal(title, body, onMount) {
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal-back"><div class="modal" role="dialog" aria-label="${esc(title)}">
    <header><h2>${esc(title)}</h2><button class="icon-btn" data-close aria-label="Schließen">${ICON.close}</button></header>
    <div class="modal-body">${body}</div></div></div>`;
  const close = () => (root.innerHTML = "");
  root.firstChild.addEventListener("click", (e) => { if (e.target === root.firstChild || e.target.closest("[data-close]")) close(); });
  onMount?.($(".modal-body", root), close);
  return close;
}

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if ($("#modal-root").firstChild) $("#modal-root").innerHTML = "";
  else if (S.sel) select(null);
});

// Run an action from a button: disable it meanwhile, show errors as toast
async function busy(btn, fn) {
  if (btn) btn.disabled = true;
  try { return await fn(); } catch (err) { toast(err.message); } finally { if (btn) btn.disabled = false; }
}

// ---------- Theme ----------

function applyTheme() {
  const pref = localStorage.getItem("theme") || "auto";
  const dark = pref === "dark" || (pref === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  $("#theme-color").content = dark ? "#141413" : "#f6f5f1";
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);

// ---------- Sign in ----------

async function renderAuth(inviteCode) {
  stopTrip();
  let invite = null;
  if (inviteCode) invite = await api("/invite/" + inviteCode).catch((err) => (toast(err.message), null));
  let mode = invite ? "register" : "login";
  const draw = () => {
    $("#app").innerHTML = `<main class="auth"><div class="auth-card">
      <img src="/icons/icon-192.png" alt="" class="logo">
      <h1>Reiseplaner</h1>
      ${invite ? `<p class="invite-note"><b>${esc(invite.inviter)}</b> lädt dich ein: <b>${esc(invite.title)}</b>, ${fmtRange(invite.start_date, invite.end_date)}</p>` : ""}
      <div class="seg" role="tablist">
        <button data-mode="login" class="${mode === "login" ? "on" : ""}">Anmelden</button>
        <button data-mode="register" class="${mode === "register" ? "on" : ""}">Konto anlegen</button>
      </div>
      <form id="auth-form">
        <label>Name<input name="name" autocomplete="username" required minlength="2" maxlength="30"></label>
        <label>Passwort<input name="password" type="password" autocomplete="${mode === "login" ? "current-password" : "new-password"}" required minlength="${mode === "login" ? 1 : 8}"></label>
        ${mode === "register" && !invite ? `<label>Code<input name="code" required autocomplete="off">
          <small>Der Einladungscode aus dem Link deiner Freunde oder, fürs allererste Konto, der Zugangscode des Servers.</small></label>` : ""}
        ${mode === "register" ? "<small>Mindestens 8 Zeichen. Das Passwort lässt sich später nicht zurücksetzen, merk es dir gut.</small>" : ""}
        <button class="btn primary" type="submit">${mode === "login" ? "Anmelden" : "Konto anlegen"}</button>
      </form></div></main>`;
    $(".seg").onclick = (e) => { const m = e.target.dataset.mode; if (m) { mode = m; draw(); } };
    $("#auth-form").onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      busy($("button[type=submit]", e.target), async () => {
        const body = { name: f.get("name").trim(), password: f.get("password") };
        if (mode === "register") body.code = inviteCode && invite ? inviteCode : (f.get("code") || "").trim();
        const res = await api("/auth/" + mode, { method: "POST", body });
        S.me = res.user;
        if (res.trip_id) location.hash = "#/trip/" + res.trip_id;
        router();
      });
    };
  };
  draw();
}

// ---------- Trip list ----------

async function renderTrips() {
  stopTrip();
  $("#app").innerHTML = `<main class="home"><header class="home-head">
      <h1>Reisen</h1>
      <button class="icon-btn" id="account" aria-label="Konto und Einstellungen">${ICON.dots}</button>
    </header><div id="trip-list" class="trip-list"><p class="muted">Lade …</p></div>
    <button class="btn primary fab" id="new-trip">${ICON.plus} Neue Reise</button></main>`;
  $("#new-trip").onclick = newTripDialog;
  $("#account").onclick = accountDialog;
  let trips;
  try { trips = await api("/trips"); } catch (err) { $("#trip-list").innerHTML = `<p class="muted">${esc(err.message)}</p>`; return; }
  const today = new Date().toISOString().slice(0, 10);
  $("#trip-list").innerHTML = trips.length ? trips.map((t) => `<a class="trip-card ${t.end_date < today ? "past" : ""}" href="#/trip/${t.id}">
      <h2>${esc(t.title)}</h2>
      <p>${fmtRange(t.start_date, t.end_date)}</p>
      <p class="muted">${t.place_count} ${t.place_count === 1 ? "Ort" : "Orte"} · ${esc(t.member_names)}</p></a>`).join("")
    : `<div class="empty"><h2>Noch keine Reise</h2><p>Leg eine Reise an und lade deine Freunde ein. ${S.ai ? "Claude schlägt euch Orte und Tagesrouten vor." : ""}</p></div>`;
}

function accountDialog() {
  const pref = localStorage.getItem("theme") || "auto";
  modal("Konto", `<p>Angemeldet als <b>${esc(S.me.name)}</b></p>
    <label>Darstellung</label>
    <div class="seg" id="theme-seg">${[["auto", "Automatisch"], ["light", "Hell"], ["dark", "Dunkel"]]
      .map(([k, l]) => `<button data-theme-pref="${k}" class="${pref === k ? "on" : ""}">${l}</button>`).join("")}</div>
    <p class="muted small">${S.ai ? "KI-Vorschläge sind aktiv." : "Kein API-Schlüssel hinterlegt: Vorschläge kommen ohne KI aus Wikipedia."} Version ${esc(S.version)}</p>
    <button class="btn" id="logout">Abmelden</button>`, (el, close) => {
    $("#theme-seg", el).onclick = (e) => {
      const k = e.target.dataset.themePref;
      if (!k) return;
      localStorage.setItem("theme", k);
      applyTheme();
      el.querySelectorAll("[data-theme-pref]").forEach((b) => b.classList.toggle("on", b.dataset.themePref === k));
    };
    $("#logout", el).onclick = () => busy(null, async () => {
      await api("/auth/logout", { method: "POST" });
      navigator.serviceWorker?.controller?.postMessage("clear-data");
      S.me = null; close(); location.hash = "#/"; router();
    });
  });
}

// Search field + result list, used for the destination and for adding places
function searchUI(el, tripId, onPick) {
  el.innerHTML = `<form class="search"><input name="q" placeholder="${tripId ? "Name oder Adresse" : "Stadt oder Region"}" required minlength="2" enterkeyhint="search">
    <button class="btn primary" type="submit">Suchen</button></form><div class="results"></div>`;
  const results = $(".results", el);
  $("form", el).onsubmit = (e) => {
    e.preventDefault();
    results.innerHTML = '<p class="muted">Suche …</p>';
    busy($("button", e.target), async () => {
      const q = new FormData(e.target).get("q");
      const hits = await api(`/geocode?q=${encodeURIComponent(q)}${tripId ? "&trip_id=" + tripId : ""}`).catch((err) => (toast(err.message), []));
      results.innerHTML = hits.length ? hits.map((h, i) => `<button class="result" data-i="${i}"><b>${esc(h.name)}</b><small>${esc(h.display)}</small></button>`).join("")
        : '<p class="muted">Nichts gefunden. Versuch es mit einer anderen Schreibweise.</p>';
      results.onclick = (ev) => { const b = ev.target.closest(".result"); if (b) onPick(hits[+b.dataset.i]); };
    });
  };
  setTimeout(() => $("input", el).focus(), 50);
}

function newTripDialog() {
  modal("Neue Reise", '<div id="step"></div><p class="muted small">Ortssuche: © OpenStreetMap-Mitwirkende</p>', (el, close) => {
    searchUI($("#step", el), null, (hit) => {
      const today = new Date().toISOString().slice(0, 10);
      $("#step", el).innerHTML = `<form id="trip-form">
        <p class="picked"><b>${esc(hit.name)}</b><small>${esc(hit.display)}</small></p>
        <label>Titel<input name="title" value="${esc(hit.name)}" required maxlength="80"></label>
        <div class="two"><label>Von<input name="start" type="date" required min="${today}" value="${today}"></label>
        <label>Bis<input name="end" type="date" required value="${today}"></label></div>
        <button class="btn primary" type="submit">Reise anlegen</button></form>`;
      const form = $("#trip-form", el);
      form.start.onchange = () => { form.end.min = form.start.value; if (form.end.value < form.start.value) form.end.value = form.start.value; };
      form.onsubmit = (e) => {
        e.preventDefault();
        busy($("button", form), async () => {
          const data = await api("/trips", { method: "POST", body: {
            title: form.title.value.trim(), destination: hit.display || hit.name, lat: hit.lat, lon: hit.lon, bbox: hit.bbox,
            start_date: form.start.value, end_date: form.end.value } });
          close();
          location.hash = "#/trip/" + data.trip.id;
        });
      };
    });
  });
}

// ---------- Trip view ----------

function stopTrip() {
  clearTimeout(pollTimer);
  if (map) { map.remove(); map = null; meMarker = null; }
  S.data = null;
  $("#modal-root").innerHTML = "";
}

async function openTrip(id) {
  stopTrip();
  Object.assign(S, { view: "all", filters: new Set(), grouped: false, sel: null, showRejected: false });
  $("#app").innerHTML = `<div class="trip" id="trip">
    <div id="map"></div>
    <div class="map-top">
      <a class="round" href="#/" aria-label="Zurück zu den Reisen">${ICON.back}</a>
      <div class="offline-pill">Offline · letzter Stand</div>
      <button class="round" id="locate" aria-label="Meinen Standort zeigen">${ICON.locate}</button>
    </div>
    <section class="panel sheet" id="panel"><div class="sheet-in">
      <div class="grip-zone"><div class="handle"></div><div id="panel-head"></div></div>
      <div class="sheet-body" id="panel-body"></div>
    </div></section>
    <section class="detail sheet" id="detail" hidden><div class="sheet-in">
      <div class="grip-zone"><div class="handle"></div><div id="detail-head"></div></div>
      <div class="sheet-body" id="detail-body"></div>
    </div></section></div>`;
  try { S.data = await api("/trips/" + id); } catch (err) { toast(err.message); location.hash = "#/"; return; }
  // Open on today if the trip is running
  const today = new Date().toISOString().slice(0, 10), t = S.data.trip;
  if (today >= t.start_date && today <= t.end_date) S.view = Math.round((new Date(today) - new Date(t.start_date)) / 864e5) + 1;

  map = L.map("map", { zoomControl: false, attributionControl: false }).setView([t.lat, t.lon], 13);
  L.control.attribution({ position: isDesktop() ? "bottomright" : "topright", prefix: false }).addTo(map);
  if (isDesktop()) L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, crossOrigin: true,
    attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> · Routen: <a href="https://routing.openstreetmap.de/about.html" target="_blank" rel="noopener">FOSSGIS</a>',
  }).addTo(map);
  mapLayer = L.layerGroup().addTo(map);
  new ResizeObserver(() => map?.invalidateSize()).observe($("#map"));
  map.on("click", () => { if (S.sel) select(null); });

  setupSheet($("#panel"), "half");
  setupSheet($("#detail"), "half", () => select(null));
  $("#locate").onclick = locateMe;
  $("#trip").addEventListener("click", onTripClick);
  $("#panel-body").addEventListener("pointerdown", startSort);
  renderAll(true);
  schedulePoll();
}

function renderAll(fit) {
  if (!S.data) return;
  renderPanel();
  renderDetail();
  renderMap(fit);
}

function update(data, fit) {
  S.data = data;
  if (S.sel && !place(S.sel)) S.sel = null;
  if (typeof S.view === "number" && S.view > data.trip.days) S.view = "all";
  renderAll(fit);
  schedulePoll();
}

// Other members' changes arrive by polling; faster while a job or a place text is pending
function schedulePoll() {
  clearTimeout(pollTimer);
  if (!S.data) return;
  const waiting = S.data.trip.job.state === "running" || S.data.places.some((p) => p.info_status === "pending");
  pollTimer = setTimeout(async () => {
    if (!S.data) return;
    if ((document.hidden && !waiting) || dragging) return schedulePoll();
    const before = S.data, wasRunning = before.trip.job.state === "running";
    try {
      const data = await api("/trips/" + before.trip.id);
      if (S.data !== before) return; // something else updated meanwhile
      if (data.trip.updated_at !== before.trip.updated_at) update(data, wasRunning && data.trip.job.state !== "running");
      else schedulePoll();
    } catch (err) {
      if (err.status === 404) { toast("Diese Reise gibt es nicht mehr."); location.hash = "#/"; } else schedulePoll();
    }
  }, waiting ? 2000 : 20000);
}

// ----- Panel: header, day chips, filters, list -----

function renderPanel() {
  const { trip, members, places } = S.data;
  const dayScroll = $("#panel-head .days")?.scrollLeft || 0;
  $("#panel-head").innerHTML = `<div class="head-row">
      <a class="icon-btn desk-only" href="#/" aria-label="Zurück zu den Reisen">${ICON.back}</a>
      <div class="head-title"><h1>${esc(trip.title)}</h1><p>${fmtRange(trip.start_date, trip.end_date)} · ${members.length} ${members.length === 1 ? "Person" : "Personen"}</p></div>
      <button class="icon-btn" data-act="members" aria-label="Teilnehmer und Einladung">${ICON.users}</button>
      <button class="icon-btn" data-act="settings" aria-label="Reise bearbeiten">${ICON.dots}</button>
    </div>
    <div class="chips days" role="tablist">
      <button class="chip ${S.view === "all" ? "on" : ""}" data-view="all">Alle</button>
      ${Array.from({ length: trip.days }, (_, i) => { const w = S.data.weather.days[i + 1]; return `<button class="chip ${S.view === i + 1 ? "on" : ""}" data-view="${i + 1}">
        <b>Tag ${i + 1}</b> ${fmtDay(dayDate(trip, i + 1))}${w ? ` ${weatherIcon(w.code)}${w.tmax}°` : ""}</button>`; }).join("")}
      <button class="chip ${S.view === "ideas" ? "on" : ""}" data-view="ideas">Ideen</button>
    </div>`;

  // Keep the day chips where they were, then bring the chosen one fully into view
  const row = $("#panel-head .days"), on = $(".chip.on", row);
  row.scrollLeft = dayScroll;
  if (on.offsetLeft < row.scrollLeft + 16) row.scrollLeft = on.offsetLeft - 16;
  else if (on.offsetLeft + on.offsetWidth > row.scrollLeft + row.clientWidth - 16) row.scrollLeft = on.offsetLeft + on.offsetWidth - row.clientWidth + 16;

  const act = active(), list = visible();
  const kinds = Object.keys(KINDS).filter((k) => act.some((p) => p.kind === k));
  const meals = Object.keys(MEALS).filter((m) => act.some((p) => p.meals.includes(m)));
  const chip = (key, label, cls) => `<button class="chip small ${cls} ${S.filters.has(key) ? "on" : ""}" data-filter="${key}">${label}</button>`;
  const filterRow = kinds.length + meals.length > 1 ? `<div class="chips filters">
      ${kinds.map((k) => chip("k:" + k, `<i class="dot kind-${k}"></i>${KINDS[k]}`, "")).join("")}
      ${meals.map((m) => chip("m:" + m, MEALS[m], "meal")).join("")}
      <button class="chip small ${S.grouped ? "on" : ""}" data-act="group" title="Getrennte Listen je Art und Mahlzeit">${ICON.layers} Getrennt</button>
    </div>` : "";

  const job = trip.job;
  const replanBox = trip.replan ? `<div class="notice stack"><span><b>Umgeplant.</b> ${esc(trip.replan)}</span>
      <span><button class="link" data-act="replan-undo">Rückgängig</button><button class="link" data-act="replan-keep">Behalten</button></span></div>` : "";
  const jobBox = job.state === "running" ? `<div class="notice"><span class="spinner"></span>${esc(job.msg)}</div>`
    : job.state === "error" ? `<div class="notice error">${esc(job.msg)}<button class="link" data-act="dismiss-job">OK</button></div>` : "";

  const day = typeof S.view === "number" ? S.view : null;
  const stops = day ? dayStops(day) : [];
  const route = day ? S.data.routes[day] : null;
  const pending = list.filter((p) => p.status === "suggested").length;
  let summary = "";
  if (day && stops.length) {
    summary = `${stops.length} ${stops.length === 1 ? "Stopp" : "Stopps"}`
      + (route ? ` · ${route.open ? "mindestens " : ""}${fmtDur(route.duration)} unterwegs` : "");
  } else if (!day) summary = `${list.length} ${list.length === 1 ? "Ort" : "Orte"}`;

  // Weather: forecast for the chosen day, or what the dates are usually like while there is no forecast yet
  const W = S.data.weather, w = day && W.days[day];
  let weather = "";
  if (w) {
    weather = `<div class="weather">${weatherIcon(w.code)}<span>${w.tmin} bis ${w.tmax}° · Regen ${w.pop} %${w.rain_from != null ? `, ab etwa ${w.rain_from} Uhr` : ""}</span></div>`;
    if (w.pop >= 60 && stops.length) weather += `<div class="notice error"><span>An diesem Tag regnet es wahrscheinlich.</span>${S.ai && job.state !== "running" ? '<button class="link" data-act="replan">Tage umplanen</button>' : ""}</div>`;
  } else if (W.usual && (day || S.view === "all")) {
    const wet = Math.round(W.usual.wet * 10);
    weather = `<div class="weather">${ICON.cloud}<span>Noch keine Vorhersage (kommt etwa 16 Tage vorher). In den letzten ${W.usual.years} Jahren waren es um diese Zeit ${W.usual.tmin} bis ${W.usual.tmax}°, Regen an ${wet < 1 ? "kaum einem Tag" : `etwa ${wet} von 10 Tagen`}.</span></div>`;
  }
  const actions = `<div class="actions">
      <button class="btn primary" data-act="suggest" ${job.state === "running" ? "disabled" : ""}>${ICON.spark} Vorschläge</button>
      <button class="btn" data-act="add">${ICON.plus} Ort</button>
      ${day && stops.length ? `<button class="btn" data-act="route">${ICON.nav} Route</button>` : ""}
    </div>
    <div class="summary"><span>${summary}</span>${pending ? `<button class="link" data-act="accept-all">${pending === 1 ? "Vorschlag annehmen" : "Alle annehmen"}</button>` : ""}</div>`;

  let body;
  if (!places.length) {
    body = `<div class="empty"><h2>Noch keine Orte</h2><p>${S.ai ? "Lass dir von Claude Orte und eine Route für jeden Tag vorschlagen" : "Lass dir bekannte Orte aus Wikipedia vorschlagen"}, oder füge eigene Orte hinzu.</p></div>`;
  } else if (!list.length) {
    body = `<p class="muted pad">${S.filters.size ? "Kein Ort passt zu diesem Filter." : day ? "Für diesen Tag ist noch nichts geplant." : "Keine Orte ohne festen Tag."}</p>`;
  } else if (S.grouped) {
    const groups = [...kinds.map((k) => ["k:" + k, KINDS[k], list.filter((p) => p.kind === k)]),
      ...meals.map((m) => ["m:" + m, MEALS[m], list.filter((p) => p.meals.includes(m))])]
      .filter(([key, , items]) => items.length && (!S.filters.size || S.filters.has(key)));
    body = groups.map(([, label, items]) => `<h3 class="group">${label} <span>${items.length}</span></h3><ul class="places">${items.map((p) => placeRow(p)).join("")}</ul>`).join("");
  } else {
    // Leg i runs from point i to point i + 1; with a hotel, point 0 and the last point are the hotel
    const legs = day && route && !S.filters.size ? route.legs : null, h = hotel();
    const off = legs && h && legs.length === list.length + 1 ? 0 : -1;
    const hotelRow = off === 0 ? `<div class="hotel-row"><button class="open" data-act="open-hotel"><span class="badge kind-lodging">${ICON.bed}</span>
      <span class="txt"><b>${esc(h.name)}</b><small>Unterkunft</small></span></button></div>` : "";
    body = hotelRow + `<ul class="places" id="sort-list">${list.map((p, i) => placeRow(p, legs && legs[i + off], i + off)).join("")}</ul>`
      + (off === 0 ? legRow(legs[legs.length - 1], legs.length - 1) + hotelRow : "");
  }
  const rejected = places.filter((p) => p.status === "rejected");
  if (S.view === "all" && rejected.length) {
    body += `<button class="link pad" data-act="toggle-rejected">${S.showRejected ? "Abgelehnte ausblenden" : `Abgelehnt (${rejected.length})`}</button>`;
    if (S.showRejected) body += `<ul class="places rejected">${rejected.map((p) => placeRow(p)).join("")}</ul>`;
  }
  const scroll = $("#panel-body").scrollTop;
  $("#panel-body").innerHTML = filterRow + jobBox + replanBox + actions + weather + body;
  $("#panel-body").scrollTop = scroll;
}

// The way between two stops, shown between their rows; a tap opens the details
function legRow(leg, index) {
  if (!leg) return "";
  let cls = "", text;
  const len = leg.duration == null ? "" : `${fmtDur(leg.duration)}${leg.distance ? " · " + fmtDist(leg.distance) : ""}`;
  if (leg.mode === "transit") {
    cls = "transit";
    text = leg.fallback ? `${ICON.bus}<span>Öffis · Verbindung in der Karten-App</span>`
      : `${ICON.bus}<span>${leg.transit.lines.map((l) => esc(`${l.kind} ${l.name}`.trim())).join(" → ")} · ${len}</span>`;
  } else if (leg.scenic) {
    cls = "scenic";
    text = `${ICON.tree}<span>Spaziergang ${esc(leg.label)} · ${len}</span>`;
  } else text = `${leg.mode === "walk" ? ICON.walk : ""}<span>${len || "Strecke nicht berechenbar"}</span>`;
  return `<button class="leg ${cls}" data-act="leg" data-leg="${index}">${text}</button>`;
}

function placeRow(p, leg, legIndex) {
  const n = stopNumber(p);
  const tags = [KINDS[p.kind], ...p.meals.map((m) => MEALS[m])];
  if ((S.view === "all" || S.grouped) && p.day) tags.push("Tag " + p.day);
  const side = p.status === "suggested" ? `<button class="mini ok" data-act="accept" aria-label="Vorschlag annehmen">${ICON.check}</button>
      <button class="mini no" data-act="reject" aria-label="Vorschlag ablehnen">${ICON.close}</button>`
    : p.status === "rejected" ? `<button class="link" data-act="restore">Zurückholen</button>`
    : sortable() ? `<span class="grip" aria-label="Verschieben">${ICON.grip}</span>` : "";
  return `<li class="place ${p.status} ${S.sel === p.id ? "sel" : ""}" data-id="${p.id}">
    ${legRow(leg, legIndex)}
    <div class="row"><button class="open" data-act="open">
      <span class="badge kind-${p.kind}">${n}</span>
      <span class="txt"><b>${esc(p.name)}</b><small>${tags.join(" · ")}${p.status === "suggested" ? " · Vorschlag" : ""}${p.votes.length ? ` · 👍 ${p.votes.length}` : ""}</small></span>
    </button>${side}</div></li>`;
}

// ----- Detail -----

function renderDetail() {
  const el = $("#detail"), p = S.sel && place(S.sel);
  $("#trip").classList.toggle("has-detail", !!p);
  if (!p) { el.hidden = true; return; }
  const wasHidden = el.hidden;
  el.hidden = false;
  if (wasHidden) el.sheet.set("half");
  // Don't replace a field the user is typing in
  if (el.contains(document.activeElement) && ["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement.tagName)) return;
  const { trip } = S.data, info = p.info || {}, links = placeLinks(p), mine = p.votes.includes(S.me.id);
  $("#detail-head").innerHTML = `<div class="head-row">
      <div class="head-title"><h1>${esc(p.name)}</h1><p>${p.id === trip.hotel_id ? "Unterkunft der Reise, Start und Ziel jedes Tages" : [KINDS[p.kind], ...p.meals.map((m) => MEALS[m])].join(" · ") + (p.day ? ` · Tag ${p.day}, Stopp ${stopNumber(p)}` : "")}</p></div>
      <button class="icon-btn" data-act="close-detail" aria-label="Schließen">${ICON.close}</button></div>`;

  const sections = [];
  if (p.status === "suggested") sections.push(`<div class="decide"><button class="btn primary" data-act="accept">${ICON.check} Annehmen</button><button class="btn" data-act="reject">Ablehnen</button></div>`);
  if (p.status === "rejected") sections.push(`<div class="decide"><button class="btn" data-act="restore">Zurück in den Plan</button></div>`);
  sections.push(`<div class="handover">
      <a class="btn" href="${links.apple}" target="_blank" rel="noopener">Apple Karten</a>
      <a class="btn" href="${links.google}" target="_blank" rel="noopener">Google Maps</a>
      <button class="btn vote ${mine ? "on" : ""}" data-act="vote" aria-pressed="${mine}">${ICON.thumb} ${p.votes.length || ""}</button></div>`);
  if (p.id === trip.hotel_id) sections.push('<div class="decide"><button class="btn" data-act="unset-hotel">Nicht mehr als Unterkunft</button></div>');
  else if (p.kind === "lodging") sections.push('<div class="decide"><button class="btn" data-act="set-hotel">Als Unterkunft der Reise festlegen</button></div>');
  if (p.votes.length) sections.push(`<p class="muted small">Dafür: ${p.votes.map((id) => esc(S.data.members.find((m) => m.id === id)?.name || "?")).join(", ")}</p>`);
  if (!p.verified) sections.push('<p class="warn">Dieser Ort wurde in OpenStreetMap nicht gefunden. Die Position ist ungefähr; prüft vor dem Losgehen, ob es ihn noch gibt.</p>');
  if (info.image) sections.push(`<a class="photo" href="${esc(info.image_page || info.wiki_url)}" target="_blank" rel="noopener"><img src="${esc(info.image)}" alt="" crossorigin="anonymous" loading="lazy"><span>Bild: Wikimedia Commons</span></a>`);
  if (p.reason) sections.push(p.source === "ai" ? `<h3>Warum hierhin?</h3><p>${esc(p.reason)}</p><p class="muted small">Einschätzung von Claude, nicht belegt.</p>` : `<p>${esc(p.reason)}</p>`);

  if (p.info_status === "pending") sections.push('<div class="notice"><span class="spinner"></span>Lade Infos zu diesem Ort …</div>');
  else if (p.info_status === "none") sections.push(S.offline ? '<p class="muted">Infos zu diesem Ort wurden noch nicht geladen.</p>' : '<div class="notice"><span class="spinner"></span>Lade Infos zu diesem Ort …</div>');
  else if (info.wiki_url) {
    if (info.summary) sections.push(`<h3>Über diesen Ort</h3>${info.summary.split("\n\n").map((t) => `<p>${esc(t)}</p>`).join("")}`);
    if (info.history) sections.push(`<h3>Geschichte</h3><p>${esc(info.history)}</p>`);
    if (info.facts?.length) sections.push(`<h3>Wissenswert</h3><ul class="facts">${info.facts.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>`);
    sections.push(`<p class="source">Quelle: <a href="${esc(info.wiki_url)}" target="_blank" rel="noopener">Wikipedia, „${esc(info.wiki_title)}“</a> (CC BY-SA 4.0)${info.by === "ai" ? ", von Claude zusammengefasst" : ", Anfang des Artikels"}</p>`);
  } else sections.push('<p class="muted">Zu diesem Ort gibt es keinen verknüpften Wikipedia-Artikel, deshalb hier keine Beschreibung.</p>');

  const facts = [];
  if (p.address) facts.push(["Adresse", esc(p.address)]);
  if (p.opening_hours) facts.push(["Geöffnet", fmtHours(p.opening_hours).map(esc).join("<br>")]);
  if (p.website) facts.push(["Website", `<a href="${esc(p.website)}" target="_blank" rel="noopener">${esc(p.website.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, ""))}</a>`]);
  if (p.phone) facts.push(["Telefon", `<a href="tel:${esc(p.phone.replace(/[^+\d]/g, ""))}">${esc(p.phone)}</a>`]);
  if (facts.length) sections.push(`<h3>Praktisches</h3><dl class="facts-table">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`);
  if (p.osm_ref) sections.push(`<p class="source">Quelle: <a href="https://www.openstreetmap.org/${esc(p.osm_ref)}" target="_blank" rel="noopener">OpenStreetMap</a>${p.opening_hours ? ". Öffnungszeiten können veraltet sein." : ""}</p>`);

  const food = FOOD.includes(p.kind);
  sections.push(`<h3>Notiz</h3><textarea id="note" rows="2" maxlength="2000" placeholder="Für alle sichtbar, z. B. „Tisch für 20 Uhr reserviert“">${esc(p.note)}</textarea>
    <h3>Einordnung</h3>
    <div class="two"><label>Art<select id="kind">${Object.entries(KINDS).map(([k, l]) => `<option value="${k}" ${k === p.kind ? "selected" : ""}>${l}</option>`).join("")}</select></label>
    <label>Tag<select id="day"><option value="">Ideen (ohne Tag)</option>${Array.from({ length: trip.days }, (_, i) =>
      `<option value="${i + 1}" ${p.day === i + 1 ? "selected" : ""}>Tag ${i + 1}, ${fmtDay(dayDate(trip, i + 1))}</option>`).join("")}</select></label></div>
    ${food ? `<div class="chips wrap">${Object.entries(MEALS).map(([m, l]) => `<button class="chip small meal ${p.meals.includes(m) ? "on" : ""}" data-meal="${m}">${l}</button>`).join("")}</div>` : ""}
    <button class="link danger" data-act="delete">Ort löschen</button>`);
  $("#detail-body").innerHTML = sections.join("");
  $("#detail-body").scrollTop = 0;

  const patch = (body) => busy(null, async () => update(await api("/places/" + p.id, { method: "PATCH", body })));
  $("#note").onchange = (e) => patch({ note: e.target.value });
  $("#kind").onchange = (e) => { e.target.blur(); patch({ kind: e.target.value }); };
  $("#day").onchange = (e) => { e.target.blur(); patch(e.target.value ? { day: +e.target.value } : { clear_day: true }); };
}

function select(id) {
  S.sel = id;
  renderAll();
  const p = id && place(id);
  if (!p) return;
  if (p.info_status === "none" && !S.offline) api(`/places/${id}/info`, { method: "POST" }).then((d) => S.sel === id && update(d)).catch(() => {});
  // Keep the place clear of the sheet
  setTimeout(() => map?.panInside([p.lat, p.lon], { paddingTopLeft: [50, 110], paddingBottomRight: [50, isDesktop() ? 50 : $("#detail").sheet.visible() + 30] }), 60);
}

// ----- Map -----

function renderMap(fit) {
  if (!map) return;
  mapLayer.clearLayers();
  const { trip, routes } = S.data, bounds = [];
  const days = S.view === "all" ? Array.from({ length: trip.days }, (_, i) => i + 1) : typeof S.view === "number" ? [S.view] : [];
  for (const d of days) {
    if (!routes[d]) continue;
    const dim = S.view === "all" ? 0.55 : 1;
    for (const leg of routes[d].legs) {
      for (const seg of leg.segs) {
        const line = seg.pts || decodePolyline(seg.g, seg.p);
        // Rides are dashed, suggested strolls green, a straight line stands for a connection without known path
        const cls = seg.m === "t" ? "route-transit" : leg.scenic ? "route-scenic" : "route-line";
        L.polyline(line, { className: "route-case", weight: 8, opacity: dim, interactive: false }).addTo(mapLayer);
        L.polyline(line, { className: cls, weight: 4.5, opacity: dim, dashArray: seg.pts ? "2 10" : seg.m === "t" ? "10 8" : null, interactive: false }).addTo(mapLayer);
        if (typeof S.view === "number") bounds.push(...line);
      }
    }
  }
  const h = hotel();
  if (h && S.view !== "ideas") {
    const icon = L.divIcon({ className: "", iconSize: [34, 34], iconAnchor: [17, 17], html: `<div class="pin kind-lodging hotel ${S.sel === h.id ? "sel" : ""}">${ICON.bed}</div>` });
    L.marker([h.lat, h.lon], { icon, title: h.name, zIndexOffset: 500 }).on("click", () => select(h.id)).addTo(mapLayer);
    if (typeof S.view === "number" && dayStops(S.view).length) bounds.push([h.lat, h.lon]);
  }
  for (const p of visible()) {
    const n = stopNumber(p);
    const icon = L.divIcon({
      className: "", iconSize: [34, 34], iconAnchor: [17, 17],
      html: `<div class="pin kind-${p.kind} ${p.status} ${S.sel === p.id ? "sel" : ""} ${n === "" ? "nonum" : ""}">${n}</div>`,
    });
    L.marker([p.lat, p.lon], { icon, title: p.name, zIndexOffset: S.sel === p.id ? 1000 : 0 }).on("click", () => select(p.id)).addTo(mapLayer);
    bounds.push([p.lat, p.lon]);
  }
  if (!fit) return;
  const pad = isDesktop() ? [50, 50] : [40, Math.min($("#panel").sheet.visible(), innerHeight * 0.55) + 30];
  if (bounds.length) map.fitBounds(bounds, { paddingTopLeft: [40, isDesktop() ? 50 : 110], paddingBottomRight: pad, maxZoom: 16 });
  else map.setView([trip.lat, trip.lon], 13);
}

function locateMe() {
  if (!navigator.geolocation) return toast("Dieses Gerät gibt keinen Standort her.");
  navigator.geolocation.getCurrentPosition((pos) => {
    if (!map) return;
    const at = [pos.coords.latitude, pos.coords.longitude];
    if (meMarker) meMarker.setLatLng(at);
    else meMarker = L.marker(at, { icon: L.divIcon({ className: "", iconSize: [22, 22], iconAnchor: [11, 11], html: '<div class="me-dot"></div>' }), interactive: false }).addTo(map);
    map.setView(at, Math.max(map.getZoom(), 15));
  }, () => toast("Standort nicht verfügbar. Er braucht deine Freigabe und eine HTTPS-Verbindung."), { enableHighAccuracy: true, timeout: 10000 });
}

// ----- Bottom sheet (phones). On desktop the same elements are plain columns. -----

function setupSheet(el, initial, onDismiss) {
  let snap = initial;
  const height = () => el.offsetHeight;
  const offsets = () => ({ full: 0, half: Math.round(height() * 0.5), peek: height() - PEEK });
  const put = (y, animate) => {
    el.style.transition = animate ? "" : "none";
    el.style.setProperty("--y", y + "px");
    el.style.setProperty("--vis", height() - y + "px");
  };
  el.sheet = {
    set(s) { snap = s; put(offsets()[s], true); },
    visible: () => (isDesktop() ? 0 : height() - offsets()[snap]),
  };
  put(offsets()[snap], false);
  // Follows every size change: rotation, browser toolbars sliding in and out, the detail sheet being shown
  new ResizeObserver(() => put(offsets()[snap], false)).observe(el);

  const zone = $(".grip-zone", el);
  zone.addEventListener("pointerdown", (e) => {
    if (isDesktop() || e.target.closest("button, a, .chips")) return;
    const startY = e.clientY, startOff = offsets()[snap];
    let moved = 0;
    zone.setPointerCapture(e.pointerId);
    const move = (ev) => {
      moved = ev.clientY - startY;
      put(Math.min(Math.max(0, startOff + moved), height() - (onDismiss ? 0 : PEEK)), false);
    };
    const up = () => {
      zone.removeEventListener("pointermove", move);
      zone.removeEventListener("pointerup", up);
      zone.removeEventListener("pointercancel", up);
      const o = offsets(), y = startOff + moved;
      if (Math.abs(moved) < 6) snap = snap === "full" ? "half" : "full"; // a tap toggles
      else if (onDismiss && y > o.half + 80) { put(o[snap], false); return onDismiss(); }
      else {
        // Nearest snap point, nudged in the direction of the swipe
        const target = y + Math.sign(moved) * 60;
        snap = Object.keys(o).filter((k) => !onDismiss || k !== "peek").reduce((a, b) => (Math.abs(o[a] - target) < Math.abs(o[b] - target) ? a : b));
      }
      put(o[snap], true);
    };
    zone.addEventListener("pointermove", move);
    zone.addEventListener("pointerup", up);
    zone.addEventListener("pointercancel", up);
  });
}

// ----- Reordering by drag handle -----

function startSort(e) {
  const grip = e.target.closest(".grip");
  const list = $("#sort-list");
  if (!grip || !list || !sortable()) return;
  e.preventDefault();
  const item = grip.closest(".place");
  let startY = e.clientY;
  dragging = true;
  list.classList.add("sorting");
  item.classList.add("dragging");
  grip.setPointerCapture(e.pointerId);
  const shift = (before) => {
    const top = item.offsetTop;
    list.insertBefore(item, before);
    startY += item.offsetTop - top;
  };
  const move = (ev) => {
    item.style.transform = `translateY(${ev.clientY - startY}px)`;
    const box = item.getBoundingClientRect(), mid = box.top + box.height / 2;
    const prev = item.previousElementSibling, next = item.nextElementSibling;
    if (prev && mid < prev.getBoundingClientRect().top + prev.offsetHeight / 2) shift(prev);
    else if (next && mid > next.getBoundingClientRect().top + next.offsetHeight / 2) shift(next.nextElementSibling);
    else return;
    item.style.transform = `translateY(${ev.clientY - startY}px)`;
  };
  const up = async () => {
    grip.removeEventListener("pointermove", move);
    grip.removeEventListener("pointerup", up);
    grip.removeEventListener("pointercancel", up);
    dragging = false;
    const ids = [...list.children].map((li) => +li.dataset.id);
    const changed = ids.some((id, i) => id !== visible()[i]?.id);
    if (!changed) return renderPanel();
    try {
      update(await api(`/trips/${S.data.trip.id}/order`, { method: "PUT", body: { day: typeof S.view === "number" ? S.view : null, ids } }));
    } catch (err) { toast(err.message); renderPanel(); }
  };
  grip.addEventListener("pointermove", move);
  grip.addEventListener("pointerup", up);
  grip.addEventListener("pointercancel", up);
}

// ----- Clicks inside the trip view -----

function onTripClick(e) {
  const t = e.target;
  const viewBtn = t.closest("[data-view]");
  if (viewBtn) {
    const v = viewBtn.dataset.view;
    S.view = v === "all" || v === "ideas" ? v : +v;
    S.sel = null;
    return renderAll(true);
  }
  const filterBtn = t.closest("[data-filter]");
  if (filterBtn) {
    const key = filterBtn.dataset.filter;
    S.filters.has(key) ? S.filters.delete(key) : S.filters.add(key);
    return renderAll(true);
  }
  const mealBtn = t.closest("[data-meal]");
  if (mealBtn && S.sel) {
    const p = place(S.sel), m = mealBtn.dataset.meal;
    const meals = p.meals.includes(m) ? p.meals.filter((x) => x !== m) : [...p.meals, m];
    return busy(mealBtn, async () => update(await api("/places/" + p.id, { method: "PATCH", body: { meals } })));
  }
  const btn = t.closest("[data-act]");
  if (!btn) return;
  const act = btn.dataset.act, trip = S.data.trip;
  const id = +btn.closest("[data-id]")?.dataset.id || S.sel;
  const call = (path, method, body, fit) => busy(btn, async () => update(await api(path, { method, body }), fit));
  if (act === "open") select(id);
  else if (act === "open-hotel") select(trip.hotel_id);
  else if (act === "leg") legDialog(+btn.dataset.leg);
  else if (act === "replan") call(`/trips/${trip.id}/replan`, "POST");
  else if (act === "replan-undo") call(`/trips/${trip.id}/replan/undo`, "POST", null, true);
  else if (act === "replan-keep") call(`/trips/${trip.id}/replan/keep`, "POST");
  else if (act === "set-hotel") call(`/trips/${trip.id}/hotel`, "PUT", { place_id: id }, true);
  else if (act === "unset-hotel") call(`/trips/${trip.id}/hotel`, "PUT", {}, true);
  else if (act === "close-detail") select(null);
  else if (act === "group") { S.grouped = !S.grouped; renderPanel(); }
  else if (act === "toggle-rejected") { S.showRejected = !S.showRejected; renderPanel(); }
  else if (act === "accept") call("/places/" + id, "PATCH", { status: "accepted" });
  else if (act === "reject") { if (S.sel === id) S.sel = null; call("/places/" + id, "PATCH", { status: "rejected" }); }
  else if (act === "restore") call("/places/" + id, "PATCH", { status: "accepted" });
  else if (act === "vote") call(`/places/${id}/vote`, "POST");
  else if (act === "accept-all") call(`/trips/${trip.id}/accept${typeof S.view === "number" ? "?day=" + S.view : ""}`, "POST");
  else if (act === "dismiss-job") call(`/trips/${trip.id}/job/dismiss`, "POST");
  else if (act === "delete") { if (confirm(`„${place(id).name}“ löschen?`)) { S.sel = null; call("/places/" + id, "DELETE"); } }
  else if (act === "suggest") suggestDialog();
  else if (act === "add") addPlaceDialog();
  else if (act === "route") routeDialog();
  else if (act === "members") membersDialog();
  else if (act === "settings") settingsDialog();
}

// ----- Dialogs -----

function suggestDialog() {
  const trip = S.data.trip, day = typeof S.view === "number" ? S.view : null, has = S.data.places.length > 0;
  modal("Vorschläge", `<form id="suggest-form">
      ${S.ai ? `<label>Wünsche (optional)<textarea name="wishes" rows="3" maxlength="1000" placeholder="z. B. viel Kunst, vegetarisch essen, nicht zu viel laufen">${esc(trip.wishes)}</textarea></label>`
        : '<p class="muted">Es ist kein Claude-API-Schlüssel hinterlegt. Statt eines durchdachten Plans bekommst du bekannte Orte aus Wikipedia in der Nähe, ohne Restaurants.</p>'}
      ${day ? `<div class="seg"><button type="button" class="on" data-scope="all">${has ? "Ganze Reise ergänzen" : "Ganze Reise"}</button><button type="button" data-scope="day">Nur Tag ${day}</button></div>` : ""}
      <p class="muted small">${S.ai ? "Claude schlägt Orte und eine Reihenfolge je Tag vor. Jeder Ort wird danach in OpenStreetMap geprüft, das dauert etwa eine Sekunde pro Ort." : ""}
        Vorschläge kannst du einzeln annehmen oder ablehnen.</p>
      <button class="btn primary" type="submit">${ICON.spark} Vorschläge holen</button></form>`, (el, close) => {
    let scope = "all";
    $(".seg", el)?.addEventListener("click", (e) => {
      if (!e.target.dataset.scope) return;
      scope = e.target.dataset.scope;
      el.querySelectorAll("[data-scope]").forEach((b) => b.classList.toggle("on", b === e.target));
    });
    $("#suggest-form", el).onsubmit = (e) => {
      e.preventDefault();
      busy($("button[type=submit]", el), async () => {
        const body = { wishes: e.target.wishes?.value || "", day: scope === "day" ? day : null };
        update(await api(`/trips/${trip.id}/suggest`, { method: "POST", body }));
        close();
      });
    };
  });
}

function addPlaceDialog() {
  const trip = S.data.trip;
  modal("Ort hinzufügen", '<div id="step"></div><p class="muted small">Ortssuche: © OpenStreetMap-Mitwirkende</p>', (el, close) => {
    searchUI($("#step", el), trip.id, (hit) => {
      let meals = [];
      const draw = (kind) => {
        $("#step", el).innerHTML = `<form id="place-form">
          <label>Name<input name="name" value="${esc(hit.name)}" required maxlength="120"></label>
          <p class="muted small">${esc(hit.display)}</p>
          <div class="two"><label>Art<select name="kind">${Object.entries(KINDS).map(([k, l]) => `<option value="${k}" ${k === kind ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <label>Tag<select name="day"><option value="">Ideen (ohne Tag)</option>${Array.from({ length: trip.days }, (_, i) =>
            `<option value="${i + 1}" ${S.view === i + 1 ? "selected" : ""}>Tag ${i + 1}, ${fmtDay(dayDate(trip, i + 1))}</option>`).join("")}</select></label></div>
          ${FOOD.includes(kind) ? `<div class="chips wrap">${Object.entries(MEALS).map(([m, l]) => `<button type="button" class="chip small meal ${meals.includes(m) ? "on" : ""}" data-m="${m}">${l}</button>`).join("")}</div>` : ""}
          <button class="btn primary" type="submit">Hinzufügen</button></form>`;
        const form = $("#place-form", el);
        form.kind.onchange = () => { hit.name = form.name.value; draw(form.kind.value); };
        form.onclick = (e) => {
          const m = e.target.dataset.m;
          if (!m) return;
          meals = meals.includes(m) ? meals.filter((x) => x !== m) : [...meals, m];
          e.target.classList.toggle("on");
        };
        form.onsubmit = (e) => {
          e.preventDefault();
          busy($("button[type=submit]", form), async () => {
            const { display, bbox, ...fields } = hit;
            const data = await api(`/trips/${trip.id}/places`, { method: "POST", body: {
              ...fields, name: form.name.value.trim(), kind: form.kind.value, meals, day: form.day.value ? +form.day.value : null } });
            close();
            update(data, true);
          });
        };
      };
      draw(hit.kind);
    });
  });
}

// One leg: what it is, the connection if it is a ride, how to change it, and the handover for just this leg
function legDialog(index) {
  const day = S.view, trip = S.data.trip, leg = S.data.routes[day]?.legs[index], pts = dayPoints(day);
  const a = pts[index], b = pts[index + 1];
  if (!leg || !a || !b) return;
  const origin = a.id === trip.hotel_id ? null : a; // the stop that carries the preference for this leg
  const m = leg.mode === "transit" ? ["transit", "transit"] : { walk: ["walking", "walking"], bike: ["cycling", "bicycling"], car: ["driving", "driving"] }[leg.mode];
  const apple = `https://maps.apple.com/directions?source=${ll(a)}&destination=${ll(b)}&mode=${m[0]}`;
  const google = `https://www.google.com/maps/dir/?api=1&origin=${ll(a)}&destination=${ll(b)}&travelmode=${m[1]}`;
  let info;
  if (leg.mode === "transit" && leg.fallback) info = "<p>Für diesen Abschnitt liegen keine Fahrplandaten vor. Die Verbindung zeigt dir die Karten-App.</p>";
  else if (leg.mode === "transit") {
    info = `<p><b>${fmtDur(leg.duration)}</b>, davon ${fmtDur(leg.transit.walk)} zu Fuß${leg.transit.transfers ? `, ${leg.transit.transfers} ${leg.transit.transfers === 1 ? "Umstieg" : "Umstiege"}` : ""}</p>
      <ol class="rides">${leg.transit.lines.map((l) => `<li><b>${esc(`${l.kind} ${l.name}`.trim())}</b>${l.headsign ? ` Richtung ${esc(l.headsign)}` : ""}<small>${esc(l.from)} → ${esc(l.to)} · ${fmtDur(l.duration)}</small></li>`).join("")}</ol>
      <p class="muted small">Verbindung an einem typischen ${WEEKDAYS[leg.weekday]}; die genaue Abfahrt zeigt die Karten-App. Fahrplandaten: <a href="https://transitous.org/sources/" target="_blank" rel="noopener">Transitous</a></p>`;
  } else {
    info = `<p><b>${leg.duration == null ? "Strecke nicht berechenbar" : `${fmtDur(leg.duration)} · ${fmtDist(leg.distance)}`}</b> ${leg.mode === "walk" ? "zu Fuß" : MODES[leg.mode]}</p>`
      + (leg.scenic ? `<p>Spaziergang ${esc(leg.label)}</p><p class="muted small">Vorschlag von Claude; die eingezeichnete Strecke ist der kürzeste Fußweg${" "}und kann vom beschriebenen Weg abweichen.</p>` : "");
  }
  const pref = origin?.leg_mode || "auto";
  const choose = origin && trip.mode === "foot" ? `<label>Diesen Abschnitt</label><div class="seg" id="leg-seg">
      ${[["auto", "Automatisch"], ["walk", "Zu Fuß"], ["transit", "Öffis"]].map(([k, l]) => `<button type="button" data-pref="${k}" class="${pref === k ? "on" : ""}">${l}</button>`).join("")}</div>
      <p class="muted small">Automatisch heißt: bis 25 Minuten zu Fuß, darüber mit Öffis, wenn es damit deutlich schneller geht.</p>` : "";
  modal(`${a.name} → ${b.name}`, `${info}${choose}
    <div class="handover"><a class="btn primary" href="${apple}" target="_blank" rel="noopener">Apple Karten</a>
      <a class="btn" href="${google}" target="_blank" rel="noopener">Google Maps</a></div>`, (el, close) => {
    $("#leg-seg", el)?.addEventListener("click", (e) => {
      const k = e.target.dataset.pref;
      if (k && k !== pref) busy(e.target, async () => { update(await api("/places/" + origin.id, { method: "PATCH", body: { leg_mode: k } })); close(); });
    });
  });
}

function hotelDialog() {
  const trip = S.data.trip;
  modal("Unterkunft", '<p class="muted small">Jeder Tag beginnt und endet an der Unterkunft.</p><div id="step"></div><p class="muted small">Ortssuche: © OpenStreetMap-Mitwirkende</p>', (el, close) => {
    searchUI($("#step", el), trip.id, (hit) => busy(null, async () => {
      const { display, bbox, ...place } = hit;
      const data = await api(`/trips/${trip.id}/hotel`, { method: "PUT", body: { place } });
      close();
      update(data, true);
    }));
  });
}

function routeDialog() {
  const trip = S.data.trip, h = hotel(), stops = [...dayStops(S.view), ...(h ? [h] : [])], parts = routeLinks(stops, trip.mode);
  const label = (p) => (parts.length > 1 ? ` · Stopp ${p.from}–${p.to}` : "");
  modal(`Route für Tag ${S.view}`, `<p>${stops.length} ${stops.length === 1 ? "Ziel" : "Ziele"}${h ? ", zuletzt die Unterkunft" : ""}. Start ist dein Standort.</p>
    ${parts.map((p) => `<div class="handover"><a class="btn primary" href="${p.apple}" target="_blank" rel="noopener">Apple Karten${label(p)}</a>
      <a class="btn" href="${p.google}" target="_blank" rel="noopener">Google Maps${label(p)}</a></div>`).join("")}
    <p class="muted small">${parts.length > 1 ? "Beide Apps nehmen nur eine begrenzte Zahl von Stopps pro Route an, deshalb ist der Tag geteilt. " : ""}Die Zwischenstopps werden in der geplanten Reihenfolge übergeben${trip.mode === "foot" ? ", als Fußweg. Karten-Apps können Öffis nicht über mehrere Stopps planen: Für einen Öffi-Abschnitt tippe ihn in der Liste an" : ""}.</p>`);
}

function membersDialog() {
  const { trip, members } = S.data, link = `${location.origin}/#/join/${trip.invite_code}`;
  modal("Teilnehmer", `<ul class="members">${members.map((m) => `<li><span>${esc(m.name)}${m.id === trip.created_by ? ' <small class="muted">hat die Reise angelegt</small>' : ""}</span>
      ${trip.created_by === S.me.id && m.id !== S.me.id ? `<button class="link danger" data-remove="${m.id}">Entfernen</button>` : ""}</li>`).join("")}</ul>
    <h3>Freunde einladen</h3>
    <p class="muted small">Wer diesen Link öffnet, legt sich ein Konto an (oder meldet sich an) und plant mit.</p>
    <input readonly value="${esc(link)}" id="invite-link">
    <div class="handover"><button class="btn primary" id="share">${navigator.share ? "Link teilen" : "Link kopieren"}</button>
      <button class="btn" id="rotate">Neuen Link erzeugen</button></div>`, (el, close) => {
    $("#share", el).onclick = async () => {
      if (navigator.share) return navigator.share({ title: trip.title, text: `Plane mit bei „${trip.title}“`, url: link }).catch(() => {});
      try { await navigator.clipboard.writeText(link); toast("Link kopiert."); } catch { $("#invite-link", el).select(); toast("Markiert. Jetzt kopieren."); }
    };
    $("#rotate", el).onclick = (e) => {
      if (!confirm("Der bisherige Link funktioniert dann nicht mehr. Neuen Link erzeugen?")) return;
      busy(e.target, async () => { update(await api(`/trips/${trip.id}/invite/rotate`, { method: "POST" })); close(); membersDialog(); });
    };
    el.onclick = (e) => {
      const uid = e.target.dataset.remove;
      if (uid && confirm("Diese Person aus der Reise entfernen?")) busy(e.target, async () => {
        update(await api(`/trips/${trip.id}/members/${uid}`, { method: "DELETE" })); close(); membersDialog();
      });
    };
  });
}

function settingsDialog() {
  const trip = S.data.trip, owner = trip.created_by === S.me.id;
  modal("Reise bearbeiten", `<form id="trip-form">
      <label>Titel<input name="title" value="${esc(trip.title)}" required maxlength="80"></label>
      <div class="two"><label>Von<input name="start" type="date" required value="${trip.start_date}"></label>
      <label>Bis<input name="end" type="date" required value="${trip.end_date}"></label></div>
      <label>Unterkunft</label>
      <div class="hotel-set"><span>${hotel() ? esc(hotel().name) : "Noch keine festgelegt"}</span><button type="button" class="link" id="pick-hotel">${hotel() ? "Ändern" : "Festlegen"}</button></div>
      <label>Unterwegs</label>
      <div class="seg" id="mode-seg">${Object.entries(MODES).map(([k, l]) => `<button type="button" data-mode="${k}" class="${trip.mode === k ? "on" : ""}">${l}</button>`).join("")}</div>
      <p class="muted small">Bestimmt, wie die Wege zwischen den Stopps berechnet und an die Karten-App übergeben werden. Wird die Reise kürzer, wandern die Orte der gestrichenen Tage zu den Ideen.</p>
      <button class="btn primary" type="submit">Speichern</button></form>
    <button class="link danger" id="leave">${owner ? "Reise löschen" : "Reise verlassen"}</button>`, (el, close) => {
    let mode = trip.mode;
    $("#pick-hotel", el).onclick = () => { close(); hotelDialog(); };
    $("#mode-seg", el).onclick = (e) => {
      if (!e.target.dataset.mode) return;
      mode = e.target.dataset.mode;
      el.querySelectorAll("[data-mode]").forEach((b) => b.classList.toggle("on", b === e.target));
    };
    $("#trip-form", el).onsubmit = (e) => {
      e.preventDefault();
      const f = e.target;
      busy($("button[type=submit]", f), async () => {
        update(await api("/trips/" + trip.id, { method: "PATCH", body: { title: f.title.value.trim(), start_date: f.start.value, end_date: f.end.value, mode } }), true);
        close();
      });
    };
    $("#leave", el).onclick = (e) => {
      if (!confirm(owner ? `„${trip.title}“ mit allen Orten für alle löschen?` : `„${trip.title}“ verlassen?`)) return;
      busy(e.target, async () => {
        await api(owner ? "/trips/" + trip.id : `/trips/${trip.id}/members/${S.me.id}`, { method: "DELETE" });
        close(); location.hash = "#/";
      });
    };
  });
}

// ---------- Router ----------

async function router() {
  const [, page, arg] = location.hash.split("/");
  if (!S.me) return renderAuth(page === "join" ? arg : null);
  if (page === "join") {
    try { location.hash = "#/trip/" + (await api(`/invite/${arg}/join`, { method: "POST" })).trip_id; }
    catch (err) { toast(err.message); location.hash = "#/"; }
    return;
  }
  if (page === "trip" && +arg) return openTrip(+arg);
  renderTrips();
}

async function start() {
  applyTheme();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  try {
    const me = await api("/me");
    Object.assign(S, { me: me.user, ai: me.ai, version: me.version });
  } catch (err) {
    $("#app").innerHTML = `<main class="auth"><div class="auth-card"><h1>Reiseplaner</h1><p>${esc(err.message)}</p><button class="btn" onclick="location.reload()">Noch einmal versuchen</button></div></main>`;
    return;
  }
  addEventListener("hashchange", router);
  document.addEventListener("visibilitychange", () => { if (!document.hidden && S.data) schedulePoll(); });
  router();
}

start();
