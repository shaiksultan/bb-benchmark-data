#!/usr/bin/env python3
"""One ping per interval to lab, UAE, and Europe. Failures stay in the file."""
import argparse, csv, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", required=True)
    ap.add_argument("--link", required=True)
    ap.add_argument("--device", required=True)
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--interval", type=int, default=1)
    ap.add_argument("--ping-wait", type=int, default=2)
    ap.add_argument("--ping-timeout", type=int, default=4)
    ap.add_argument("--lab-host", required=True)
    ap.add_argument("--uae-host", required=True)
    ap.add_argument("--eu-host", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    d = Path(a.outdir)
    d.mkdir(parents=True, exist_ok=True)
    csvp = d / "reliability.csv"
    targets = [("lab", a.lab_host), ("uae", a.uae_host), ("eu", a.eu_host)]
    totals = {name: 0 for name, _ in targets}
    oks = {name: 0 for name, _ in targets}
    end = time.time() + a.hours * 3600
    while time.time() < end:
        for name, host in targets:
            try:
                p = subprocess.run(["ping", "-c", "1", "-W", str(a.ping_wait), host], capture_output=True, text=True, timeout=a.ping_timeout)
                good = p.returncode == 0
            except Exception:
                good = False
            totals[name] += 1
            oks[name] += int(good)
            row = {
                "timestamp_utc": utc_now(),
                "network": a.network,
                "endpoint": name,
                "target": host,
                "link": a.link,
                "device": a.device,
                "success": 1 if good else 0,
                "availability_pct": f"{oks[name] / totals[name] * 100:.5f}",
                "rsrp_dbm": os.environ.get("RADIO_RSRP", ""),
                "sinr_db": os.environ.get("RADIO_SINR", ""),
                "band": os.environ.get("RADIO_BAND", ""),
            }
            exists = csvp.exists()
            with csvp.open("a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(row.keys()))
                if not exists:
                    w.writeheader()
                w.writerow(row)
        time.sleep(a.interval)

if __name__ == "__main__":
    main()
