#!/usr/bin/env bash
# Ubuntu 24.04.3 client. Installs the same packages as the lab server, then checks versions.
set -euo pipefail
sudo apt-get update
sudo apt-get install -y iperf3 sip-tester python3 curl iputils-ping dnsutils ethtool iproute2 ca-certificates
if ! command -v speedtest >/dev/null; then
  curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
  sudo apt-get install -y speedtest
fi
echo "Installed. Now run ./write_versions.sh and do not start unless it prints VERSIONS OK."
echo "If SIPp is not v3.7.2, copy the lab server binary. apt on a new machine may install a different SIPp."
