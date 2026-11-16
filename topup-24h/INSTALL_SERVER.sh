#!/usr/bin/env bash
# Lab server or cloud VM. Cloud VMs only need iperf3. The lab server also needs SIPp.
set -euo pipefail
sudo apt-get update
sudo apt-get install -y iperf3 python3 curl iputils-ping
if [[ "${1:-lab}" == "lab" ]]; then
  sudo apt-get install -y sip-tester
  echo "Confirm SIPp is v3.7.2. The lab host already has that build. Do not replace it with a different one."
fi
iperf3 --version | head -n 1
