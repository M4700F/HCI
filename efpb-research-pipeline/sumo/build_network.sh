#!/usr/bin/env bash
set -euo pipefail
: "${SUMO_HOME:?Set SUMO_HOME to your SUMO installation directory}"
mkdir -p "$(dirname "$0")/net"
netconvert \
  --node-files "$(dirname "$0")/net/nodes.nod.xml" \
  --edge-files "$(dirname "$0")/net/edges.edg.xml" \
  --connection-files "$(dirname "$0")/net/connections.con.xml" \
  --crossings.guess true \
  --sidewalks.guess true \
  --output-file "$(dirname "$0")/net/intersection.net.xml"
netcheck --net-file "$(dirname "$0")/net/intersection.net.xml" || true
echo "Built sumo/net/intersection.net.xml"
