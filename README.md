# bb-benchmark-data

Public package for the broadband benchmark: the September probe logs, the workbooks, and the 24-hour top-up scripts.

Paths compared: fixed fiber, 5G fixed wireless, mobile 5G, and LEO satellite.

## Files

| File | What it is |
| --- | --- |
| [data/data.zip](data/data.zip) | Raw probe logs, 4–6 September 2026, all four paths |
| [topup-24h.zip](topup-24h.zip) | 24-hour follow-up scripts. The same files are in [topup-24h/](topup-24h/) |
| [data/network-kpi-timestamp.xlsx](data/network-kpi-timestamp.xlsx) | Network KPIs with timestamps, after the 1.5×IQR screen |
| [data/network-kpi-outliers-availability.xlsx](data/network-kpi-outliers-availability.xlsx) | Outlier candidates and the availability log, including failed pings |
| [data/application-qoe.xlsx](data/application-qoe.xlsx) | Application timing for social, messaging, calling, and Teams |
| [data/youtube-netflix-ott.xlsx](data/youtube-netflix-ott.xlsx) | YouTube and Netflix playback runs |
| [data/video-quality-uvq.xlsx](data/video-quality-uvq.xlsx) | GoChat and BOTIM video scores from Google UVQ |

`topup-24h/sample-data/` shows the column layout. Those rows are placeholders, not measurements.

## KPIs the scripts record

Network, written by the probe scripts:

- iperf3 download and upload
- Round-trip time: average, P50, P95, P99, and round-trip time while iperf3 is running (top-up only)
- UDP jitter and UDP packet loss
- Ping loss and probe success. Every failed ping stays in the file.
- DNS response time
- TCP connect, TLS handshake, and time to first byte. TLS is the time after TCP, from curl.
- Voice-pattern delay, jitter, loss, and an estimated MOS from delay and loss. This is not a listening score.
- Gaming-pattern delay, jitter, and loss
- Ookla download, upload, ping, and server id
- SIPp call setup toward the lab server

Application and video, stored in the workbooks rather than in the probe script:

- Facebook, Instagram, X, TikTok, WhatsApp, BOTIM, GoChat, Teams join, and application YouTube timing
- YouTube playback from the player’s Stats for Nerds panel, kept separate from the application YouTube timing
- Netflix playback and the player-reported VMAF score
- GoChat and BOTIM Google UVQ scores

The top-up script does not delete outliers. Keep the unfiltered rows. A 1.5×IQR screen, if used later, is applied per network and per KPI.

## Install the top-up

Match these versions on the lab server and every probe: Ubuntu 24.04.3, iperf 3.16, curl 8.5.0, Python 3.12, SIPp 3.7.2, Ookla Speedtest CLI 1.2.0.84. Cloud VMs need iperf 3.16 only.

```bash
unzip topup-24h.zip
cd topup-24h
chmod +x *.sh
./INSTALL_CLIENT.sh          # each probe
./INSTALL_SERVER.sh lab      # lab server
./INSTALL_SERVER.sh cloud    # UAE VM and Europe VM
./write_versions.sh          # must print VERSIONS OK
```

Set `LAB_HOST`, `UAE_HOST`, and `EU_HOST` in `topup.conf`. Set `LINK` and `DEVICE` in each file under `paths/`. Open TCP and UDP 5201–5204 and ICMP on all three servers, and UDP 5061–5064 on the lab server.

```bash
./START_LAB_SERVER.sh
./START_CLOUD_SERVER.sh
./RUN_TOPUP.sh paths/fiber.env
./RUN_TOPUP.sh paths/fwa.env
./RUN_TOPUP.sh paths/mobile.env
./RUN_TOPUP.sh paths/leo.env
```

Timeouts are at the bottom of `topup.conf`. Ports, the schedule, and the file list to keep after the run are in [docs/setup.md](docs/setup.md).
