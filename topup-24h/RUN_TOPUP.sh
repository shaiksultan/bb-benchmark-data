#!/usr/bin/env bash
# Start one path for the top-up. Example: ./RUN_TOPUP.sh paths/fiber.env
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "${HERE}"
PATH_FILE="${1:-}"
[[ -n "${PATH_FILE}" && -f "${PATH_FILE}" ]] || { echo "Usage: ./RUN_TOPUP.sh paths/fiber.env"; exit 1; }
# shellcheck disable=SC1091
source ./topup.conf
# shellcheck disable=SC1090
source "${PATH_FILE}"

: "${LAB_HOST:?Set LAB_HOST in topup.conf}"
: "${UAE_HOST:?Set UAE_HOST in topup.conf}"
: "${EU_HOST:?Set EU_HOST in topup.conf}"
: "${LINK:?Set LINK in the path file, for example ethernet or wifi-5ghz}"
: "${DEVICE:?Set DEVICE in the path file, for example the probe hostname}"

OUT="results/${PATH_NAME}"
mkdir -p "${OUT}/iperf"
./write_versions.sh "${OUT}/versions.txt"

python3 topup_reliability.py \
  --network "${PATH_NAME}" --link "${LINK}" --device "${DEVICE}" \
  --hours "${HOURS}" --interval "${RELIABILITY_INTERVAL_SEC}" \
  --ping-wait "${PING_WAIT_SEC}" --ping-timeout "${PING_PROCESS_SEC}" \
  --lab-host "${LAB_HOST}" --uae-host "${UAE_HOST}" --eu-host "${EU_HOST}" \
  --outdir "${OUT}" > "${OUT}/reliability_console.log" 2>&1 &
echo $! > "${OUT}/reliability.pid"

python3 topup_probe.py \
  --network "${PATH_NAME}" --link "${LINK}" --device "${DEVICE}" \
  --lab-host "${LAB_HOST}" --uae-host "${UAE_HOST}" --eu-host "${EU_HOST}" \
  --iperf-port "${IPERF_PORT}" --iperf-streams "${IPERF_STREAMS}" --iperf-seconds "${IPERF_SECONDS}" \
  --udp-bitrate "${UDP_BITRATE}" --udp-seconds "${UDP_SECONDS}" \
  --https1 "${HTTPS_1}" --name1 "${HTTPS_1_NAME}" --https2 "${HTTPS_2}" --name2 "${HTTPS_2_NAME}" \
  --dns-server "${DNS_SERVER}" --dns-name "${DNS_NAME}" \
  --hours "${HOURS}" --offset "${OFFSET_SEC}" \
  --light-interval "${LIGHT_INTERVAL_SEC}" --iperf-interval "${IPERF_INTERVAL_SEC}" \
  --udp-interval "${UDP_INTERVAL_SEC}" --voice-interval "${VOIP_INTERVAL_SEC}" \
  --ping-wait "${PING_WAIT_SEC}" --dig-query "${DIG_QUERY_SEC}" --dig-timeout "${DIG_PROCESS_SEC}" \
  --curl-max "${CURL_MAX_SEC}" --curl-timeout "${CURL_PROCESS_SEC}" \
  --iperf-extra "${IPERF_EXTRA_SEC}" --voice-seconds "${VOICE_SECONDS}" \
  --outdir "${OUT}" > "${OUT}/probe_console.log" 2>&1 &
echo $! > "${OUT}/probe.pid"

END=$(( $(date +%s) + HOURS*3600 ))
NEXT_OOKLA=0
NEXT_SIP=0
while [[ $(date +%s) -lt ${END} ]]; do
  NOW=$(date +%s)
  if [[ ${NOW} -ge ${NEXT_OOKLA} ]]; then
    python3 topup_ookla.py --network "${PATH_NAME}" --link "${LINK}" --device "${DEVICE}" \
      --server-id "${OOKLA_SERVER_ID}" --timeout "${OOKLA_TIMEOUT_SEC}" --outdir "${OUT}" >> "${OUT}/extra.log" 2>&1 || true
    NEXT_OOKLA=$((NOW + OOKLA_INTERVAL_SEC))
  fi
  if [[ ${NOW} -ge ${NEXT_SIP} ]]; then
    python3 topup_sip.py --network "${PATH_NAME}" --server "${LAB_HOST}" --port "${SIP_PORT}" \
      --calls "${SIP_CALLS}" --rate "${SIP_RATE}" --hold-ms "${SIP_HOLD_MS}" \
      --sip-timeout "${SIP_TIMEOUT_SEC}" --process-floor "${SIP_PROCESS_FLOOR_SEC}" \
      --outdir "${OUT}" >> "${OUT}/extra.log" 2>&1 || true
    NEXT_SIP=$((NOW + VOIP_INTERVAL_SEC))
  fi
  sleep 30
done
wait "$(cat "${OUT}/probe.pid")" || true
kill "$(cat "${OUT}/reliability.pid")" 2>/dev/null || true
echo "Finished ${PATH_NAME}. Share the folder ${OUT}"
