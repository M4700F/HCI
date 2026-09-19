from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict


def sumo_environment() -> Dict[str, str]:
    env = dict(os.environ)
    sumo_home = env.get("SUMO_HOME")
    if sumo_home:
        tools = str(Path(sumo_home) / "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
    return env


def check_sumo() -> Dict[str, str]:
    env = sumo_environment()
    binary = shutil.which("sumo", path=env.get("PATH"))
    if not binary:
        raise RuntimeError("SUMO was not found. Install it and set SUMO_HOME/PATH; see SUMO_SETUP.md")
    version = subprocess.check_output([binary, "--version"], env=env, text=True).strip()
    return {"binary": binary, "version": version, "sumo_home": env.get("SUMO_HOME", "")}


def validate_network(config_path: str = "sumo/base.sumocfg") -> Dict[str, str]:
    """Validate a generated SUMO configuration without claiming a controller run."""
    info = check_sumo()
    cfg = Path(config_path)
    if not cfg.exists():
        raise FileNotFoundError(str(cfg))
    env = sumo_environment()
    binary = info["binary"]
    subprocess.check_call([binary, "-c", str(cfg), "--no-step-log", "true", "--duration-log.statistics", "true", "--end", "1"], env=env)
    return info
