"""Goal progress and monthly aggregation. Pure functions."""
from dataclasses import dataclass
from datetime import date

from bmi_dashboard.services.calculations import round_half_up


@dataclass(frozen=True)
class GoalProgress:
    status: str  # no_data | target_equals_start | in_progress | behind | achieved
    progress_percent: float | None  # clamped to 0..100
    raw_progress_percent: float | None  # unclamped; negative when moving away from the target
    remaining_kg: float | None  # current - target (positive: above target)
    direction: str  # lose | gain | maintain


def goal_progress(starting_weight_kg: float, current_weight_kg: float | None, target_weight_kg: float) -> GoalProgress:
    """progress % = (start - current) / (start - target) x 100.

    The same formula works for weight-gain goals because numerator and
    denominator change sign together.
    """
    if starting_weight_kg > target_weight_kg:
        direction = "lose"
    elif starting_weight_kg < target_weight_kg:
        direction = "gain"
    else:
        direction = "maintain"

    if current_weight_kg is None:
        return GoalProgress("no_data", None, None, None, direction)

    remaining = round_half_up(current_weight_kg - target_weight_kg, 1)
    if direction == "maintain":
        return GoalProgress("target_equals_start", None, None, remaining, direction)

    raw = (starting_weight_kg - current_weight_kg) / (starting_weight_kg - target_weight_kg) * 100
    clamped = min(100.0, max(0.0, raw))
    if raw >= 100:
        status = "achieved"
    elif raw < 0:
        status = "behind"
    else:
        status = "in_progress"
    return GoalProgress(status, round_half_up(clamped, 1), round_half_up(raw, 1), remaining, direction)


def monthly_summary(entries: list[tuple[date, float]]) -> list[dict]:
    """Group (date, weight_kg) pairs by calendar month, oldest month first."""
    months: dict[str, list[tuple[date, float]]] = {}
    for recorded_on, weight in entries:
        months.setdefault(recorded_on.strftime("%Y-%m"), []).append((recorded_on, weight))

    summary = []
    for month in sorted(months):
        rows = sorted(months[month])
        weights = [w for _, w in rows]
        summary.append(
            {
                "month": month,
                "entries": len(rows),
                "first_weight_kg": rows[0][1],
                "last_weight_kg": rows[-1][1],
                "change_kg": round_half_up(rows[-1][1] - rows[0][1], 2),
                "average_weight_kg": round_half_up(sum(weights) / len(weights), 2),
                "min_weight_kg": min(weights),
                "max_weight_kg": max(weights),
            }
        )
    return summary
