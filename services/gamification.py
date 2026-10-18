"""Pure progress rules for Ikhtiyar streaks and weekly challenges."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

UAE_TZ = ZoneInfo("Asia/Dubai")

CHALLENGES = (
    {
        "key": "sustainable_choices",
        "title": "Choose a lighter ride",
        "description": "Record 3 trips by metro, bus, walking, or cycling.",
        "target": 3,
        "reward_xp": 40,
    },
    {
        "key": "active_distance",
        "title": "Move under your own power",
        "description": "Walk or cycle at least 5 km this week.",
        "target": 5,
        "reward_xp": 50,
    },
    {
        "key": "co2_saved",
        "title": "Keep 1.5 kg of CO₂ out of the trip total",
        "description": "Save at least 1.5 kg of CO₂ compared with the driving baseline.",
        "target": 1.5,
        "reward_xp": 60,
    },
)


def uae_today():
    return datetime.now(UAE_TZ).date()


def current_week_start(today=None):
    today = today or uae_today()
    return today - timedelta(days=today.weekday())


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def build_weekly_challenges(history, today=None):
    """Build this week's progress from retained trips; rewards are claimed separately."""
    today = today or uae_today()
    week_start = current_week_start(today)
    week_trips = [
        trip for trip in history
        if (trip_date := _as_date(trip.get("trip_date"))) is not None
        and week_start <= trip_date <= today
    ]

    sustainable_count = sum(
        1 for trip in week_trips
        if str(trip.get("chosen_transport", "")).lower() in {"metro", "bus", "walking", "cycling"}
    )
    active_distance = sum(
        max(0.0, float(trip.get("distance_km") or 0)) for trip in week_trips
        if str(trip.get("chosen_transport", "")).lower() in {"walking", "cycling"}
    )
    saved_co2 = sum(max(0.0, float(trip.get("co2_saved") or 0)) for trip in week_trips)
    values = {
        "sustainable_choices": sustainable_count,
        "active_distance": active_distance,
        "co2_saved": saved_co2,
    }

    challenges = []
    for definition in CHALLENGES:
        progress = min(float(definition["target"]), float(values[definition["key"]]))
        target = float(definition["target"])
        challenges.append({
            **definition,
            "progress": round(progress, 2),
            "progress_percent": round(min(100.0, progress / target * 100), 1),
            "is_complete": progress >= target,
            "week_start": week_start.isoformat(),
        })
    return challenges


def level_from_points(total_points):
    points = max(0, int(total_points or 0))
    level = points // 100 + 1
    into_level = points % 100
    return {
        "total_points": points,
        "level": level,
        "level_title": f"Level {level}",
        "level_progress": into_level,
        "points_to_next_level": 100 - into_level,
    }
