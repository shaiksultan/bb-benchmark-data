#!/usr/bin/env python3
"""One Ookla test. Server id is pinned when --server-id is set, and always stored."""
import argparse, csv, json, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", required=True)
    ap.add_argument("--link", required=True)
    ap.add_argument("--device", required=True)
    ap.add_argument("--server-id", default="")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    d = Path(a.outdir)
    d.mkdir(parents=True, exist_ok=True)
    csvp = d / "speedtest_samples.csv"
    exe = shutil.which("speedtest")
    if not exe:
        print("Ookla CLI not found")
        return
    cmd = [exe, "--accept-license", "--accept-gdpr", "-f", "json"]
    if a.server_id:
        cmd += ["--server-id", a.server_id]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
    raw = (p.stdout or "").strip()
    status = "FAIL"
    row = {
        "timestamp_utc": utc_now(), "network": a.network, "link": a.link, "device": a.device,
        "download_mbps": "", "upload_mbps": "", "ping_latency_ms": "", "ping_jitter_ms": "",
        "packet_loss_pct": "", "server_name": "", "server_id": a.server_id, "status": status,
    }
    if p.returncode == 0 and raw.startswith("{"):
        j = json.loads(raw)
        row.update({
            "download_mbps": round(j["download"]["bandwidth"] * 8 / 1e6, 3),
            "upload_mbps": round(j["upload"]["bandwidth"] * 8 / 1e6, 3),
            "ping_latency_ms": j["ping"]["latency"],
            "ping_jitter_ms": j["ping"].get("jitter", ""),
            "packet_loss_pct": j.get("packetLoss", ""),
            "server_name": j["server"].get("name", ""),
            "server_id": j["server"].get("id", ""),
            "status": "PASS",
        })
    exists = csvp.exists()
    with csvp.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)
    print(row["status"], row["download_mbps"], row["server_id"])

if __name__ == "__main__":
    main()
