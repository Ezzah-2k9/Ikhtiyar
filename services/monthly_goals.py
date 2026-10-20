"""Pure aggregation helpers for user-selected monthly travel goals."""

import calendar
import math
from datetime import date

GOAL_METRICS = {
    "co2_saved": {"label": "CO₂ saved", "unit": "kg", "direction": "at_least"},
    "budget": {"label": "Travel budget", "unit": "AED", "direction": "at_most"},
    "trip_count": {"label": "Recorded trips", "unit": "trips", "direction": "at_least"},
    "sustainable_trips": {"label": "Sustainable trips", "unit": "trips", "direction": "at_least"},
    "active_distance": {"label": "Walking and cycling distance", "unit": "km", "direction": "at_least"},
}


def month_key(day):
    return day.strftime("%Y-%m")


def previous_month_key(day):
    first = day.replace(day=1)
    previous = date.fromordinal(first.toordinal() - 1)
    return month_key(previous)


def monthly_metric_value(history, period, metric):
    total = 0.0
    for trip in history or []:
        raw_date = trip.get("trip_date")
        trip_period = raw_date.strftime("%Y-%m") if hasattr(raw_date, "strftime") else str(raw_date or "")[:7]
        if trip_period != period:
            continue
        mode = str(trip.get("chosen_transport", "")).lower()
        try:
            if metric == "co2_saved":
                value = max(0.0, float(trip.get("co2_saved") or 0))
            elif metric == "budget":
                value = max(0.0, float(trip.get("chosen_cost") or 0))
            elif metric == "trip_count":
                value = 1.0
            elif metric == "sustainable_trips":
                value = 1.0 if mode in {"metro", "bus", "walking", "cycling"} else 0.0
            elif metric == "active_distance":
                value = max(0.0, float(trip.get("distance_km") or 0)) if mode in {"walking", "cycling"} else 0.0
            else:
                return 0.0
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            total += value
    return round(total, 2)


def build_goal_state(goal, history, today, *, finished=False):
    if not goal:
        return None
    metric = str(goal.get("goal_metric") or "co2_saved")
    if metric not in GOAL_METRICS:
        metric = "co2_saved"
    try:
        target = float(goal.get("target_value", goal.get("target_co2_kg")) or 0)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(target) or target <= 0:
        return None

    period = str(goal.get("month") or month_key(today))
    value = monthly_metric_value(history, period, metric)
    direction = GOAL_METRICS[metric]["direction"]
    remaining = max(0.0, target - value) if direction == "at_least" else max(0.0, target - value)
    reached = value + 0.005 >= target if direction == "at_least" else (finished and value <= target + 0.005)
    percent = min(100, int(round(value / target * 100)))
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    pace_target = target * today.day / days_in_month if period == month_key(today) else target
    behind_pace = period == month_key(today) and (
        value + 0.005 < pace_target if direction == "at_least" else value > target
    )
    status = ("reached" if reached else "missed") if finished else (
        "reached" if reached else "behind" if behind_pace else "on_track"
    )
    meta = GOAL_METRICS[metric]
    return {
        "month": period, "goal_metric": metric, "goal_label": meta["label"], "goal_unit": meta["unit"],
        "goal_direction": direction, "target_value": round(target, 2), "current_value": value,
        "remaining_value": remaining, "progress_percent": percent, "pace_target": round(pace_target, 2),
        "behind_pace": behind_pace, "reached": reached, "status": status, "finished": finished,
        # Compatibility fields for older stored CO₂ goals and templates.
        "target_co2_kg": round(target, 2), "saved_co2_kg": value,
        "remaining_co2_kg": remaining,
    }
