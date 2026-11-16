#!/usr/bin/env bash
# On the lab server only. One iperf3 listener per path, plus one SIPp UAS per path.
# Cloud VMs use START_CLOUD_SERVER.sh and do not run SIPp.
set -euo pipefail
command -v iperf3 >/dev/null
command -v sipp >/dev/null
for port in 5201 5202 5203 5204; do
  iperf3 -s -p "${port}" -D
done
for port in 5061 5062 5063 5064; do
  sipp -sn uas -p "${port}" >/var/log/sipp-${port}.log 2>&1 &
  echo $! > /var/run/sipp-${port}.pid
done
echo "Lab listeners up: iperf3 5201-5204, SIPp 5061-5064"
echo "Allow TCP and UDP 5201-5204, UDP 5061-5064, and ICMP."
