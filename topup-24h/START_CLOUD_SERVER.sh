#!/usr/bin/env bash
# On the UAE VM and the Europe VM. iperf3 only. ICMP must be allowed.
set -euo pipefail
command -v iperf3 >/dev/null
for port in 5201 5202 5203 5204; do
  iperf3 -s -p "${port}" -D
done
echo "Cloud iperf3 listeners up on 5201-5204 TCP and UDP. Allow ICMP."
