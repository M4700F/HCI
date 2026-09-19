# SUMO setup

The general pipeline default is `surrogate`, but the one-day emergency path uses `run_sumo_actual.py` and `run_sumo_batch.py` with real SUMO/TraCI vehicle simulation. Keep the SUMO release pinned and record its version in the generated metadata.

## macOS

```bash
brew install sumo
export SUMO_HOME="$(brew --prefix sumo)/share/sumo"
sumo --version
```

Alternative Python package:

```bash
python -m pip install 'eclipse-sumo==1.27.1'
sumo --version
python -c 'import traci, sumolib; print("TraCI OK")'
```

Record the exact `sumo --version`, OS, CPU, Python version, and dependency lock in the run metadata. The emergency network uses `V_NS`, `V_EW`, and a vehicle-phase proxy for `P_ALL`; it must be treated as a narrow vehicle-network prototype because no validated pedestrian walking areas are included. Run the emergency matrix with `configs/experiments/sumo_emergency.yaml` and report its scope accurately.
