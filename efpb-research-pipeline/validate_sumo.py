from __future__ import annotations

import json

from efpb.sumo_backend import validate_network


if __name__ == "__main__":
    print(json.dumps(validate_network(), indent=2))
