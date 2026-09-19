from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict


def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_config(path: str) -> Dict[str, Any]:
    import yaml

    p = Path(path).resolve()
    data = yaml.safe_load(p.read_text()) or {}
    parent = data.pop("extends", None)
    if parent:
        data = _deep_merge(load_config(str((p.parent / parent).resolve())), data)
    data["_config_path"] = str(p)
    data["config_hash"] = sha256_json(data)
    return data


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# Keys that name or list runs but do not change what one run computes.
FINGERPRINT_EXCLUDED = ("_config_path", "config_hash", "experiment_id", "scenarios", "seeds", "controllers", "sweep", "per_controller", "frozen")


def effective_config(config: Dict[str, Any], controller: str) -> Dict[str, Any]:
    """The config one controller runs with: `per_controller[controller]` is merged over the shared settings and then dropped."""
    merged = copy.deepcopy(config)
    extra = merged.pop("per_controller", None) or {}
    return _deep_merge(merged, extra.get(controller, {}))


def result_fingerprint(config: Dict[str, Any], scenario: Dict[str, Any], controller: str, seed: int, extra: Any = None) -> str:
    """Hash of everything that decides one run's result: settings, scenario, controller, seed (and `extra`, e.g. network files).

    Stored runs are reused only when their fingerprint matches, so a changed parameter cannot silently reuse old output.
    """
    settings = {key: value for key, value in effective_config(config, controller).items() if key not in FINGERPRINT_EXCLUDED}
    return sha256_json({"settings": settings, "scenario": scenario, "controller": controller, "seed": seed, "extra": extra})


def write_json(path: str, value: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
