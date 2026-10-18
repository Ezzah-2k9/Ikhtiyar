"""Pure helpers for cumulative monthly CO2-savings goals."""

import calendar
import math
from datetime import date


def month_key(day):
    return day.strftime("%Y-%m")


def previous_month_key(day):
    first = day.replace(day=1)
    previous = date.fromordinal(first.toordinal() - 1)
    return month_key(previous)


def saved_co2_for_month(history, period):
    total = 0.0
    for trip in history or []:
        raw_date = trip.get("trip_date")
        if hasattr(raw_date, "strftime"):
            trip_period = raw_date.strftime("%Y-%m")
        else:
            trip_period = str(raw_date or "")[:7]
        if trip_period != period:
            continue
        try:
            value = float(trip.get("co2_saved") or 0)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            total += max(0.0, value)
    return round(total, 2)


def build_goal_state(goal, history, today, *, finished=False):
    if not goal:
        return None
    try:
        target = float(goal.get("target_co2_kg") or 0)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(target) or target <= 0:
        return None

    period = str(goal.get("month") or month_key(today))
    saved = saved_co2_for_month(history, period)
    remaining = max(0.0, round(target - saved, 2))
    percent = min(100, int(round(saved / target * 100)))
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    pace_target = target * today.day / days_in_month if period == month_key(today) else target
    behind_pace = period == month_key(today) and today.day > 1 and saved + 0.005 < pace_target
    reached = saved + 0.005 >= target
    if finished:
        status = "reached" if reached else "missed"
    elif reached:
        status = "reached"
    elif behind_pace:
        status = "behind"
    else:
        status = "on_track"

    return {
        "month": period,
        "target_co2_kg": round(target, 2),
        "saved_co2_kg": saved,
        "remaining_co2_kg": remaining,
        "progress_percent": percent,
        "pace_target_kg": round(pace_target, 2),
        "behind_pace": behind_pace,
        "reached": reached,
        "status": status,
        "finished": finished,
    }
