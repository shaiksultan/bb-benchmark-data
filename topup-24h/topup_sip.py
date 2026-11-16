#!/usr/bin/env python3
"""SIPp UAC. --hold-ms is passed to SIPp as -d (pause, milliseconds)."""
import argparse, csv, re, subprocess
from datetime import datetime, timezone
from pathlib import Path

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--calls", type=int, default=20)
    ap.add_argument("--rate", type=int, default=1)
    ap.add_argument("--hold-ms", type=int, default=3000)
    ap.add_argument("--sip-timeout", type=int, default=60)
    ap.add_argument("--process-floor", type=int, default=120)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    d = Path(a.outdir)
    d.mkdir(parents=True, exist_ok=True)
    cmd = [
        "sipp", f"{a.server}:{a.port}", "-sn", "uac", "-s", "test",
        "-m", str(a.calls), "-r", str(a.rate), "-d", str(a.hold_ms),
        "-timeout", f"{a.sip_timeout}s",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=max(a.process_floor, a.calls * 5))
        raw = (p.stdout or "") + "\n" + (p.stderr or "")
        rc = p.returncode
    except Exception as e:
        raw, rc = str(e), 125
    m = re.search(r"Successful call\s+\|\s*\d+\s*\|\s*(\d+)", raw, re.I)
    successful = int(m.group(1)) if m else (a.calls if rc == 0 else 0)
    failed = max(0, a.calls - successful)
    row = {
        "timestamp_utc": utc_now(), "network": a.network, "server": a.server, "port": a.port,
        "attempted_calls": a.calls, "successful_calls": successful, "failed_calls": failed,
        "success_rate_pct": round(successful / a.calls * 100, 2) if a.calls else 0,
        "hold_ms": a.hold_ms, "return_code": rc,
    }
    csvp = d / "sip_sim_samples.csv"
    exists = csvp.exists()
    with csvp.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)
    (d / "sip_sim.log").open("a", encoding="utf-8").write(f"{row['timestamp_utc']} hold_ms={a.hold_ms} rc={rc}\n")
    print(row["success_rate_pct"])

if __name__ == "__main__":
    main()
