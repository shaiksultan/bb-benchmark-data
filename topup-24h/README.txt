24-hour top-up scripts
======================

These files are separate from the September campaign scripts. Nothing in
"Final Code" is changed.

Before the run
1. Put Ubuntu 24.04.3 on every client, matching the lab server.
2. Run INSTALL_CLIENT.sh on each probe and INSTALL_SERVER.sh on the lab host.
3. Run INSTALL_SERVER.sh cloud on the UAE VM and the Europe VM.
4. Confirm ./write_versions.sh prints VERSIONS OK on every probe.
   Required match with the lab server:
   iperf 3.16, curl 8.5.0, Python 3.12, SIPp 3.7.2, Ookla Speedtest 1.2.0.84.
5. Fill LAB_HOST, UAE_HOST, and EU_HOST in topup.conf.
6. In each paths/*.env file set LINK (ethernet or wifi-5ghz) and DEVICE.
   Optional radio readings: export RADIO_RSRP, RADIO_SINR, and RADIO_BAND.
   If they are unset, those columns stay empty.

Start
- Lab server: ./START_LAB_SERVER.sh
- Each cloud VM: ./START_CLOUD_SERVER.sh
- Each probe, within the same hour:
    ./RUN_TOPUP.sh paths/fiber.env
    ./RUN_TOPUP.sh paths/fwa.env
    ./RUN_TOPUP.sh paths/mobile.env
    ./RUN_TOPUP.sh paths/leo.env
  The path files already stagger the probes by 0, 5, 10, and 15 minutes.

What you send the VP
Zip the results/<path> folder from each probe. sample-data/ shows the file
layout and the columns. Those rows are examples, not measurements.

Each probe folder contains:
- versions.txt
- samples.csv          one row per KPI, UTC, endpoint, link, device, status
- reliability.csv      every ping, including failures
- speedtest_samples.csv
- sip_sim_samples.csv  hold_ms is the value passed to SIPp
- iperf/*.json         the raw iperf3 -J output

The script does not remove outliers.

Timeouts are the block at the bottom of topup.conf. RUN_TOPUP.sh passes
them into the collectors. A test that hits a process cap is written as
FAIL with status still in the CSV.
