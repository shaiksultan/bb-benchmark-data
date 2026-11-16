# 24-hour top-up setup

Use this page to run the follow-up campaign. The scripts are in `topup-24h/`. They do not replace the September collectors.

The run lasts 24 hours. Fiber, fixed wireless, mobile, and LEO start in the same hour. Each probe measures three far ends: the lab server, one cloud VM in a UAE region, and one cloud VM in Europe. Every row is kept. The scripts do not apply the 1.5×IQR filter.

## Versions

Install the same versions on the lab server and every probe. These are the versions already on the lab server from the September campaign.

| Component | Version | Where |
| --- | --- | --- |
| OS | Ubuntu 24.04.3 LTS | Lab server, both cloud VMs, every probe |
| iperf3 | 3.16 | All of them. The Ubuntu 24.04 package is 3.16. Ubuntu 22.04 installs 3.9, so those probes need 24.04. |
| curl | 8.5.0 | Probes. TCP, TLS, and TTFB come from curl. |
| Python | 3.12 | Probes and the lab server |
| SIPp | 3.7.2 | Lab server and probes. Copy the lab server binary if `apt` installs 3.6.1 or 3.7.7. Cloud VMs do not need SIPp. |
| Ookla Speedtest CLI | 1.2.0.84 | Probes only |

`write_versions.sh` stops the run unless those five tools match. It writes `versions.txt` into the result folder.

## Install

On each probe:

```bash
cd topup-24h
chmod +x *.sh
./INSTALL_CLIENT.sh
./write_versions.sh
```

Stop if that script does not print `VERSIONS OK`.

On the lab server:

```bash
./INSTALL_SERVER.sh lab
./write_versions.sh
```

On each cloud VM:

```bash
./INSTALL_SERVER.sh cloud
iperf3 --version
```

The first line of `iperf3 --version` must say `iperf 3.16`.

## Open these ports

On the lab server and both cloud VMs:

- TCP and UDP 5201, 5202, 5203, 5204 for iperf3
- ICMP for the ping tests

On the lab server only:

- UDP 5061, 5062, 5063, 5064 for SIPp

| Path | iperf3 port | SIPp port | Start delay |
| --- | ---: | ---: | ---: |
| LEO | 5201 | 5061 | 15 minutes |
| Fiber | 5202 | 5062 | none |
| Fixed wireless | 5203 | 5063 | 5 minutes |
| Mobile | 5204 | 5064 | 10 minutes |

The delay is `OFFSET_SEC` in `paths/*.env`. It keeps the four probes off the same server at the same moment.

## Fill the config

In `topup.conf`, set the three hosts. Leave them empty and the probe will refuse to start.

```bash
LAB_HOST=<lab server>
UAE_HOST=<UAE cloud VM>
EU_HOST=<Europe cloud VM>
```

Optional: set `OOKLA_SERVER_ID` to one Ookla server for every path. If it stays empty, Ookla chooses a server and the script still records the id it used.

In each file under `paths/`, set:

- `LINK` to `ethernet` or `wifi-5ghz`
- `DEVICE` to the probe hostname

Fixed wireless and mobile can export radio readings before the run. If these are unset, the columns stay empty.

```bash
export RADIO_RSRP=
export RADIO_SINR=
export RADIO_BAND=
```

Use a wired client on fiber, fixed wireless, and LEO. Use 2.5 GbE on the fixed-wireless probe when the CPE has that port, so the test is not capped by a 1 GbE NIC. Mobile stays on the handset tether.

## Start

1. Lab server: `./START_LAB_SERVER.sh`
2. UAE VM and Europe VM: `./START_CLOUD_SERVER.sh` on each
3. Within the same hour, on the four probes:

```bash
./RUN_TOPUP.sh paths/fiber.env
./RUN_TOPUP.sh paths/fwa.env
./RUN_TOPUP.sh paths/mobile.env
./RUN_TOPUP.sh paths/leo.env
```

Each command runs for `HOURS` (24). It starts the once-per-second ping monitor, the KPI probe, Ookla once an hour, and SIPp on the lab server.

## What each probe measures

| Test | How often | Far end | Setting |
| --- | --- | --- | --- |
| Ping availability | 1 second | Lab, UAE, Europe | `RELIABILITY_INTERVAL_SEC` |
| Idle RTT, DNS, TCP, TLS, TTFB | 5 minutes | Ping to all three hosts. Web timing to the two public pages. | `LIGHT_INTERVAL_SEC` |
| iperf3 download and upload | 30 minutes | All three hosts | 4 streams, 30 seconds. A parallel ping is stored as RTT under load. |
| UDP jitter and loss | 15 minutes | All three hosts | 10 Mb/s for 60 seconds |
| Voice pattern and MOS | 30 minutes | Lab only | 150 seconds, 100 kb/s, 200-byte packets |
| Ookla | 60 minutes | The pinned server, or Ookla's choice | Server id is stored |
| SIPp | 30 minutes | Lab only | 20 calls, 1 per second, 3000 ms hold passed to SIPp |

iperf3 is run with `-J`. The JSON is saved under `results/<path>/iperf/` before the bitrate is read.

TCP, TLS, and TTFB come from curl. TCP is `time_connect`. TLS is `time_appconnect` minus `time_connect`. TTFB is `time_starttransfer`. Curl follows redirects.

Voice MOS is the same E-model-style estimate as the September script. It is not a listening score.

## Timeouts

All of these are at the bottom of `topup.conf`. A test that hits a process cap is stored as `FAIL`. The row is not deleted.

| Name | Seconds | Meaning |
| --- | ---: | --- |
| `PING_WAIT_SEC` | 2 | `ping -W`, how long one ping waits for a reply |
| `PING_PROCESS_SEC` | 4 | Availability script gives up on that ping and records a failure |
| `DIG_QUERY_SEC` | 3 | `dig +time` |
| `DIG_PROCESS_SEC` | 10 | Script cap for the dig process |
| `CURL_MAX_SEC` | 30 | `curl --max-time` |
| `CURL_PROCESS_SEC` | 40 | Script cap for the curl process |
| `IPERF_EXTRA_SEC` | 30 | Added to the iperf3 test length. A 30-second test may run for 60 seconds. |
| `VOICE_SECONDS` | 150 | Voice UDP test length |
| `OOKLA_TIMEOUT_SEC` | 180 | Ookla CLI |
| `SIP_TIMEOUT_SEC` | 60 | SIPp `-timeout` |
| `SIP_PROCESS_FLOOR_SEC` | 120 | Minimum script cap for SIPp. Longer runs get 5 seconds per call. |

## Files to keep for the VP

When the 24 hours finish, zip `results/fiber`, `results/fwa`, `results/mobile`, and `results/leo`. `sample-data/fiber/` shows the layout. The numbers in that folder are placeholders.

Each result folder contains:

- `versions.txt`
- `samples.csv` with UTC time, endpoint, link, device, KPI, value, unit, and pass or fail
- `reliability.csv` with every ping, including failures
- `speedtest_samples.csv`
- `sip_sim_samples.csv`, including `hold_ms`
- `iperf/*.json`

Do not run a 1.5×IQR screen before sending these files. The unfiltered logs are the record of the top-up.
