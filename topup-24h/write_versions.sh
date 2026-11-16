#!/usr/bin/env bash
# Record the tool versions for this host. A mismatch stops the campaign.
set -u
OUT="${1:-versions.txt}"
{
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname=$(hostname)"
  . /etc/os-release
  echo "os=${PRETTY_NAME}"
  uname -a
  echo "--- iperf3 ---"
  iperf3 --version 2>&1 | head -n 2
  echo "--- curl ---"
  curl --version 2>&1 | head -n 1
  echo "--- python ---"
  python3 --version 2>&1
  echo "--- sipp ---"
  sipp -v 2>&1 | head -n 1
  echo "--- speedtest ---"
  speedtest --version 2>&1 | head -n 1
  echo "--- link ---"
  iface=$(ip route show default 2>/dev/null | awk '{print $5; exit}')
  echo "default_iface=${iface}"
  if [[ -n "${iface}" ]] && command -v ethtool >/dev/null; then
    ethtool "${iface}" 2>&1 | awk '/Speed:|Duplex:|Link detected:/'
  else
    echo "ethtool: not available"
  fi
} > "${OUT}"
cat "${OUT}"
python3 - "${OUT}" <<'PY'
import sys
text=open(sys.argv[1], encoding="utf-8", errors="replace").read()
need=[("iperf 3.16","iperf3"),("curl 8.5.0","curl"),("Python 3.12","python"),
      ("SIPp v3.7.2","sipp"),("Speedtest by Ookla 1.2.0.84","ookla")]
bad=[label for needle,label in need if needle not in text]
if bad:
    print("VERSION MISMATCH:", ", ".join(bad))
    print("Required: iperf 3.16, curl 8.5.0, Python 3.12, SIPp 3.7.2, Ookla 1.2.0.84")
    sys.exit(1)
print("VERSIONS OK")
PY
