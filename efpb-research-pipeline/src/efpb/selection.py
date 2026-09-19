"""Pre-declared calibration rules (see docs/preregistration_calibration.md). Pure functions, no experiment code."""
from __future__ import annotations

from math import hypot
from typing import Any, Callable, Dict, List, Optional, Tuple


def normalise(value: float, low: float, high: float) -> float:
    return 0.0 if high == low else (value - low) / (high - low)


def pick_closest_to_ideal(rows: List[Dict[str, Any]], exclude: Optional[Callable[[Dict[str, Any]], bool]] = None) -> Dict[str, Any]:
    """One controller's configurations -> the one closest to the ideal point (lowest delay and lowest max wait).

    Both objectives are scaled to 0-1 over that controller's own configurations, so no controller is favoured by the scale of
    its numbers. An exact tie keeps the default configuration (a parameter is not changed for nothing), then goes to the lower
    max wait, then the lower config id. Configurations excluded by `exclude` (for example
    any with a collision) are skipped unless every configuration is excluded.
    """
    pool = [row for row in rows if not (exclude and exclude(row))] or list(rows)
    delays, waits = [float(r["person_delay_s"]) for r in pool], [float(r["max_norm_wait"]) for r in pool]
    d_low, d_high, w_low, w_high = min(delays), max(delays), min(waits), max(waits)
    def key(row):
        distance = hypot(normalise(float(row["person_delay_s"]), d_low, d_high), normalise(float(row["max_norm_wait"]), w_low, w_high))
        is_default = row.get("is_default") in (True, "True")
        return (round(distance, 12), 0 if is_default else 1, float(row["max_norm_wait"]), row["config_id"])
    return min(pool, key=key)


def adopt(delay_diff: float, wait_diff: float) -> bool:
    """Confirmation rule: the selected configuration (minus the default, on new seeds) replaces the default unless it is
    worse in both objectives."""
    return not (delay_diff > 0 and wait_diff > 0)


def nest(dotted: str, value: Any) -> Dict[str, Any]:
    head, _, rest = dotted.partition(".")
    return {head: nest(rest, value) if rest else value}


def merge(into: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(into.get(key), dict):
            merge(into[key], value)
        else:
            into[key] = value
    return into


def frozen_settings(adopted: Dict[str, Dict[str, Any]], defaults: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Adopted overrides per controller -> (global signal settings, per-controller settings).

    The fixed-time plan is global (every controller falls back to it when sensors fail); the other controllers get only the
    settings that differ from their defaults.
    """
    global_settings: Dict[str, Any] = {}
    per_controller: Dict[str, Any] = {}
    for controller, overrides in adopted.items():
        for dotted, value in overrides.items():
            if controller == "fixed_time":
                merge(global_settings, nest(dotted, value))
            elif value != defaults[controller].get(dotted):
                merge(per_controller.setdefault(controller, {}), nest(dotted, value))
    return global_settings, per_controller
