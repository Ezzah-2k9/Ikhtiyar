"""Cumulative monthly target helpers for account travel history."""

import calendar
import math
from datetime import date

GOAL_TYPES = {
    "co2_savings": {
        "title": "CO₂ savings",
        "description": "Save this much CO₂ compared with driving every recorded trip.",
        "unit": "kg CO₂",
        "aggregate_label": "saved",
        "direction": "increase",
    },
    "spending_limit": {
        "title": "Transport budget",
        "description": "Keep your total monthly transport cost under this amount.",
        "unit": "AED",
        "aggregate_label": "spent",
        "direction": "limit",
    },
    "trip_count": {
        "title": "Trips this month",
        "description": "Record this many journeys over the month.",
        "unit": "trips",
        "aggregate_label": "recorded",
        "direction": "increase",
    },
    "sustainable_trips": {
        "title": "Lower-impact trips",
        "description": "Choose walking, cycling, Metro, or bus for this many saved journeys.",
        "unit": "trips",
        "aggregate_label": "completed",
        "direction": "increase",
    },
    "active_distance": {
        "title": "Active travel distance",
        "description": "Walk or cycle this many kilometres across the month.",
        "unit": "km",
        "aggregate_label": "travelled",
        "direction": "increase",
    },
}

SUSTAINABLE_MODES = {"walking", "cycling", "metro", "bus"}
ACTIVE_MODES = {"walking", "cycling"}


def month_key(day):
    return day.strftime("%Y-%m")


def previous_month_key(day):
    first = day.replace(day=1)
    return month_key(date.fromordinal(first.toordinal() - 1))


def _trip_period(trip):
    raw_date = trip.get("trip_date")
    return raw_date.strftime("%Y-%m") if hasattr(raw_date, "strftime") else str(raw_date or "")[:7]


def _number(value):
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def aggregate_goal(history, period, goal_type):
    trips = [trip for trip in history or [] if _trip_period(trip) == period]
    if goal_type == "spending_limit":
        return round(sum(max(0.0, _number(trip.get("chosen_cost"))) for trip in trips), 2)
    if goal_type == "trip_count":
        return float(len(trips))
    if goal_type == "sustainable_trips":
        return float(sum(str(trip.get("chosen_transport", "")).lower() in SUSTAINABLE_MODES for trip in trips))
    if goal_type == "active_distance":
        return round(sum(
            max(0.0, _number(trip.get("distance_km")))
            for trip in trips
            if str(trip.get("chosen_transport", "")).lower() in ACTIVE_MODES
        ), 2)
    return round(sum(max(0.0, _number(trip.get("co2_saved"))) for trip in trips), 2)


def build_goal_state(goal, history, today, *, finished=False):
    if not goal:
        return None
    goal_type = str(goal.get("goal_type") or "co2_savings")
    if goal_type not in GOAL_TYPES:
        goal_type = "co2_savings"
    target = _number(goal.get("target_value", goal.get("target_co2_kg")))
    if target <= 0:
        return None

    period = str(goal.get("month") or month_key(today))
    value = aggregate_goal(history, period, goal_type)
    definition = GOAL_TYPES[goal_type]
    limit = definition["direction"] == "limit"
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    pace_target = target * today.day / days_in_month if period == month_key(today) else target

    if limit:
        remaining = round(target - value, 2)
        progress_percent = min(100, max(0, int(round(value / target * 100))))
        reached = value <= target + 0.005
        behind_pace = period == month_key(today) and value > pace_target + 0.005
        status = "over_limit" if value > target else ("on_track" if not behind_pace else "behind")
    else:
        remaining = max(0.0, round(target - value, 2))
        progress_percent = min(100, int(round(value / target * 100)))
        reached = value + 0.005 >= target
        behind_pace = period == month_key(today) and today.day > 1 and value + 0.005 < pace_target
        status = "reached" if reached else ("behind" if behind_pace else "on_track")

    if finished:
        status = "reached" if reached else "missed"
    elif limit and reached:
        status = "on_track"
    elif not limit and reached:
        status = "reached"

    return {
        "month": period,
        "goal_type": goal_type,
        "title": definition["title"],
        "description": definition["description"],
        "unit": definition["unit"],
        "aggregate_label": definition["aggregate_label"],
        "direction": definition["direction"],
        "target_value": round(target, 2),
        "current_value": round(value, 2),
        "remaining_value": remaining,
        "progress_percent": progress_percent,
        "pace_target": round(pace_target, 2),
        "behind_pace": behind_pace,
        "reached": reached,
        "status": status,
        "finished": finished,
        # Backward-compatible aliases for an already deployed CO₂-only goal.
        "target_co2_kg": round(target, 2),
        "saved_co2_kg": round(value, 2),
        "remaining_co2_kg": max(0.0, round(target - value, 2)),
    }
