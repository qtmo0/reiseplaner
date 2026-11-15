"""Opening hours from OpenStreetMap, read just far enough to answer: is this place open on that weekday,
and at the meals it is planned for? Anything beyond plain weekday and time rules counts as unknown."""

import re

_DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_DAY = r"(?:Mo|Tu|We|Th|Fr|Sa|Su|PH|SH)"
_RULE = re.compile(rf"({_DAY}(?:\s*[-,]\s*{_DAY})*)?\s*:?\s*(.*)")
_TIME = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTH = "(?:" + "|".join(_MONTHS) + ")"
_SEASON = re.compile(rf"({_MONTH}(?:\s*-\s*{_MONTH})?(?:\s*,\s*{_MONTH}(?:\s*-\s*{_MONTH})?)*)\s*:?\s*(.*)")
WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
# When a place has to be open to serve a meal (minutes of the day)
_MEALS = {"breakfast": (7 * 60, 11 * 60, "zum Frühstück"), "lunch": (12 * 60, 14 * 60 + 30, "mittags"),
          "dinner": (18 * 60 + 30, 21 * 60 + 30, "abends")}


def _in_season(selector: str, month: int) -> bool:
    """month (1-12) inside a selector like 'Oct-Apr' or 'May-Sep,Dec'."""
    for part in re.split(r"\s*,\s*", selector):
        ends = re.split(r"\s*-\s*", part)
        a, b = _MONTHS.index(ends[0]) + 1, _MONTHS.index(ends[-1]) + 1
        if (a <= month <= b) if a <= b else (month >= a or month <= b):
            return True
    return False


def week_hours(raw: str, month: int) -> list[list[tuple[int, int]]] | None:
    """Opening intervals in minutes for Monday to Sunday in the given month; an empty list is a closed day.
    None if the text uses syntax this reader doesn't cover (dates, holidays only, sunrise, comments)."""
    raw = raw.strip()
    if raw == "24/7":
        return [[(0, 1440)] for _ in range(7)]
    week: list = [None] * 7
    for rule in raw.split(";"):
        rule = rule.strip()
        if not rule:
            continue
        season = _SEASON.fullmatch(rule)
        if season:  # a rule for part of the year, e.g. "Oct-Apr: Tu-Su 10:00-17:30"
            if not _in_season(season[1], month):
                continue
            rule = season[2]
        days_part, rest = _RULE.fullmatch(rule).groups()
        days = list(range(7))
        if days_part:
            days = []
            for part in re.split(r"\s*,\s*", days_part):
                ends = re.split(r"\s*-\s*", part)
                if any(e not in _DAYS for e in ends):
                    continue  # public or school holidays: not a weekday
                a, b = _DAYS.index(ends[0]), _DAYS.index(ends[-1])
                days += [d % 7 for d in range(a, b + 1 if b >= a else b + 8)]
            if not days:
                continue
        rest = rest.strip()
        if rest in ("off", "closed"):
            hours = []
        elif not rest:
            hours = [(0, 1440)]
        else:
            hours = []
            for span in rest.split(","):
                m = _TIME.fullmatch(span.strip())
                if not m:
                    return None
                start, end = int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])
                hours.append((start, end if end > start else end + 1440))  # open past midnight
        for d in days:
            week[d] = hours
    if all(day is None for day in week):
        return None
    return [day or [] for day in week]


def issue(raw: str, day, meals: list[str]) -> str:
    """Why a visit on that date looks doubtful, as German text; '' if fine or unknown."""
    weekday = day.weekday()
    week = week_hours(raw, day.month) if raw else None
    if week is None:
        return ""
    spans = week[weekday]
    if not spans:
        return f"{WEEKDAYS[weekday]}s geschlossen"
    wanted = [_MEALS[m] for m in meals if m in _MEALS]
    if wanted and not any(min(end, b) - max(start, a) >= 30 for a, b, _ in wanted for start, end in spans):
        return f"{WEEKDAYS[weekday]}s {' und '.join(label for _, _, label in wanted)} nicht geöffnet"
    return ""
