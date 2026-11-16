#!/usr/bin/env python3
"""24-hour top-up collector. Does not filter rows. Timestamps are UTC."""
import argparse, csv, json, math, os, re, statistics, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def run(cmd, timeout=None):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, 124, stdout=e.stdout or "", stderr=f"TIMEOUT after {timeout}s")
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=str(e))
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 125, stdout="", stderr=str(e))

def append_csv(path, row):
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)

class Probe:
    def __init__(self, a):
        self.a = a
        self.dir = Path(a.outdir)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "iperf").mkdir(exist_ok=True)
        self.csv = self.dir / "samples.csv"
        self.log = self.dir / "benchmark.log"
        self.endpoints = [
            ("lab", a.lab_host, a.iperf_port),
            ("uae", a.uae_host, a.iperf_port),
            ("eu", a.eu_host, a.iperf_port),
        ]

    def logline(self, msg):
        line = f"{utc_now()} | {self.a.network} | {msg}"
        print(line, flush=True)
        with self.log.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def radio(self):
        return {
            "rsrp_dbm": os.environ.get("RADIO_RSRP", ""),
            "sinr_db": os.environ.get("RADIO_SINR", ""),
            "band": os.environ.get("RADIO_BAND", ""),
        }

    def sample(self, kpi, metric, value, unit, status="PASS", target="", endpoint="",
               streams="", seconds="", retransmits="", nbytes=""):
        row = {
            "timestamp_utc": utc_now(),
            "network": self.a.network,
            "endpoint": endpoint,
            "link": self.a.link,
            "device": self.a.device,
            "kpi_id": kpi,
            "metric": metric,
            "value": value,
            "unit": unit,
            "status": status,
            "target": target,
            "streams": streams,
            "seconds": seconds,
            "retransmits": retransmits,
            "bytes": nbytes,
        }
        row.update(self.radio())
        append_csv(self.csv, row)

    def ping_stats(self, host, count, interval):
        p = run(["ping", "-c", str(count), "-i", str(interval), "-W", str(self.a.ping_wait), host],
                timeout=max(30, int(count * interval + self.a.ping_wait + 10)))
        vals = [float(x) for x in re.findall(r"time[=<]([\d.]+)\s*ms", p.stdout or "")]
        loss_m = re.search(r"([\d.]+)% packet loss", p.stdout or "")
        loss = float(loss_m.group(1)) if loss_m else 100.0
        if not vals:
            return None, None, None, None, loss
        vals.sort()
        def pct(q):
            if len(vals) == 1:
                return vals[0]
            k = (len(vals) - 1) * q
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return vals[int(k)]
            return vals[f] * (c - k) + vals[c] * (k - f)
        return statistics.mean(vals), pct(0.50), pct(0.95), pct(0.99), loss

    def latency(self, endpoint, host):
        avg, p50, p95, p99, loss = self.ping_stats(host, 20, 0.2)
        if avg is None:
            self.sample("KPI-003", "RTT average", "", "ms", "FAIL", host, endpoint)
            self.sample("KPI-005", "Ping packet loss", loss, "%", "FAIL", host, endpoint)
            return
        self.sample("KPI-003", "RTT average", round(avg, 3), "ms", "PASS", host, endpoint)
        self.sample("KPI-003", "RTT P50", round(p50, 3), "ms", "PASS", host, endpoint)
        self.sample("KPI-003", "RTT P95", round(p95, 3), "ms", "PASS", host, endpoint)
        self.sample("KPI-003", "RTT P99", round(p99, 3), "ms", "PASS", host, endpoint)
        self.sample("KPI-005", "Ping packet loss", round(loss, 3), "%", "PASS", host, endpoint)

    def dns(self):
        vals = []
        for _ in range(5):
            p = run(["dig", f"@{self.a.dns_server}", self.a.dns_name, "+stats", "+tries=1", f"+time={self.a.dig_query}"], timeout=self.a.dig_timeout)
            m = re.search(r"Query time:\s*(\d+)\s*msec", p.stdout or "")
            if m:
                vals.append(float(m.group(1)))
        if vals:
            self.sample("KPI-006", "DNS response time", round(statistics.mean(vals), 3), "ms", "PASS", self.a.dns_name, "public")
        else:
            self.sample("KPI-006", "DNS response time", "", "ms", "FAIL", self.a.dns_name, "public")

    def https_one(self, url, name):
        fmt = "%{time_namelookup},%{time_connect},%{time_appconnect},%{time_starttransfer},%{time_total},%{http_code},%{remote_ip}"
        p = run(["curl", "-L", "--max-time", str(self.a.curl_max), "-o", "/dev/null", "-sS", "-w", fmt, url], timeout=self.a.curl_timeout)
        if p.returncode != 0:
            for kpi, metric in [("KPI-007", "TTFB"), ("KPI-008", "TCP connect"), ("KPI-009", "TLS handshake")]:
                self.sample(kpi, f"{metric} - {name}", "", "ms", "FAIL", url, "public")
            return
        try:
            _dn, tc, ta, ttfb, _total, code, _rip = p.stdout.strip().split(",", 6)
            tc = float(tc) * 1000
            ta = float(ta) * 1000
            ttfb = float(ttfb) * 1000
            tls = max(0.0, ta - tc)
            status = "PASS" if 200 <= int(code) < 500 else "FAIL"
            self.sample("KPI-008", f"TCP connect - {name}", round(tc, 3), "ms", status, url, "public")
            self.sample("KPI-009", f"TLS handshake - {name}", round(tls, 3), "ms", status, url, "public")
            self.sample("KPI-007", f"TTFB - {name}", round(ttfb, 3), "ms", status, url, "public")
        except Exception as e:
            self.logline(f"WEB PARSE FAIL {name} {e}")

    def save_json(self, endpoint, direction, raw):
        name = f"iperf_{utc_stamp()}_{endpoint}_{direction}.json"
        (self.dir / "iperf" / name).write_text(raw or "", encoding="utf-8")
        return name

    def iperf_tcp(self, endpoint, host, port, reverse):
        direction = "download" if reverse else "upload"
        seconds = self.a.iperf_seconds
        cmd = ["iperf3", "-c", host, "-p", str(port), "-P", str(self.a.iperf_streams), "-t", str(seconds), "-J"]
        if reverse:
            cmd.insert(5, "-R")
        ping = subprocess.Popen(
            ["ping", "-c", str(seconds), "-i", "1", "-W", str(self.a.ping_wait), host],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        p = run(cmd, timeout=seconds + self.a.iperf_extra)
        try:
            ping.wait(timeout=seconds + self.a.iperf_extra)
        except Exception:
            ping.kill()
        ping_out = ""
        if ping.stdout:
            ping_out = ping.stdout.read() if hasattr(ping.stdout, "read") else ""
        self.save_json(endpoint, direction, p.stdout)
        kpi = "KPI-001" if reverse else "KPI-002"
        metric = "Download throughput" if reverse else "Upload throughput"
        loaded = [float(x) for x in re.findall(r"time[=<]([\d.]+)\s*ms", ping_out or "")]
        if loaded:
            self.sample("KPI-003L", "RTT under load", round(statistics.mean(loaded), 3), "ms", "PASS", host, endpoint)
        else:
            self.sample("KPI-003L", "RTT under load", "", "ms", "FAIL", host, endpoint)
        if p.returncode != 0:
            self.sample(kpi, metric, "", "Mbps", "FAIL", f"{host}:{port}", endpoint,
                        self.a.iperf_streams, seconds)
            self.logline(f"{endpoint} {metric} FAIL rc={p.returncode}")
            return
        try:
            j = json.loads(p.stdout)
            end = j.get("end", {})
            block = end.get("sum_received" if reverse else "sum_sent", {})
            bps = block.get("bits_per_second")
            if bps is None:
                raise ValueError("bits_per_second missing")
            self.sample(
                kpi, metric, round(float(bps) / 1e6, 3), "Mbps", "PASS", f"{host}:{port}", endpoint,
                j.get("start", {}).get("test_start", {}).get("num_streams", self.a.iperf_streams),
                block.get("seconds", seconds),
                block.get("retransmits", ""),
                block.get("bytes", ""),
            )
        except Exception as e:
            self.sample(kpi, metric, "", "Mbps", "FAIL", f"{host}:{port}", endpoint)
            self.logline(f"{endpoint} {metric} PARSE FAIL {e}")

    def udp(self, endpoint, host, port, seconds, bitrate):
        cmd = ["iperf3", "-c", host, "-p", str(port), "-u", "-b", bitrate, "-t", str(seconds), "-J"]
        p = run(cmd, timeout=seconds + self.a.iperf_extra)
        self.save_json(endpoint, "udp", p.stdout)
        if p.returncode != 0:
            self.sample("KPI-004", "UDP jitter", "", "ms", "FAIL", f"{host}:{port}", endpoint, "", seconds)
            self.sample("KPI-005", "UDP packet loss", "", "%", "FAIL", f"{host}:{port}", endpoint, "", seconds)
            return
        try:
            s = json.loads(p.stdout)["end"]["sum"]
            self.sample("KPI-004", "UDP jitter", round(float(s.get("jitter_ms", 0)), 3), "ms", "PASS", f"{host}:{port}", endpoint, "", seconds)
            self.sample("KPI-005", "UDP packet loss", round(float(s.get("lost_percent", 0)), 3), "%", "PASS", f"{host}:{port}", endpoint, "", seconds, "", s.get("bytes", ""))
        except Exception as e:
            self.logline(f"{endpoint} UDP PARSE FAIL {e}")

    def voice_mos(self, host):
        _avg, _p50, p95, _p99, _ping_loss = self.ping_stats(host, 50, 0.1)
        p = run(["iperf3", "-c", host, "-p", str(self.a.iperf_port), "-u", "-b", "100K", "-l", "200", "-t", str(self.a.voice_seconds), "-J"], timeout=self.a.voice_seconds + self.a.iperf_extra)
        self.save_json("lab", "voice", p.stdout)
        jitter = loss = None
        if p.returncode == 0:
            try:
                s = json.loads(p.stdout)["end"]["sum"]
                jitter = float(s.get("jitter_ms", 0))
                loss = float(s.get("lost_percent", 0))
            except Exception:
                pass
        if p95 is not None:
            self.sample("KPI-030", "VoIP RTT P95", round(p95, 3), "ms", "PASS", host, "lab")
        if jitter is not None:
            self.sample("KPI-031", "VoIP jitter", round(jitter, 3), "ms", "PASS", host, "lab")
        if loss is not None:
            self.sample("KPI-032", "VoIP packet loss", round(loss, 3), "%", "PASS", host, "lab")
        if p95 is not None and loss is not None:
            one_way = p95 / 2
            Id = 0.024 * one_way + 0.11 * max(0, one_way - 177.3)
            Ie = 30 * math.log10(1 + 15 * loss / 100) if loss > 0 else 0
            R = max(0, min(100, 93.2 - Id - Ie))
            mos = 1 + 0.035 * R + R * (R - 60) * (100 - R) * 7e-6
            mos = max(1, min(4.5, mos))
            self.sample("KPI-033", "Estimated Voice MOS", round(mos, 3), "MOS", "PASS", host, "lab")

    def light(self):
        self.logline("LIGHT cycle")
        for name, host, _port in self.endpoints:
            self.latency(name, host)
        self.dns()
        self.https_one(self.a.https1, self.a.name1)
        self.https_one(self.a.https2, self.a.name2)

    def iperf_cycle(self):
        self.logline("IPERF cycle")
        for name, host, port in self.endpoints:
            self.iperf_tcp(name, host, port, reverse=True)
            time.sleep(5)
            self.iperf_tcp(name, host, port, reverse=False)
            time.sleep(5)

    def udp_cycle(self):
        self.logline("UDP cycle")
        for name, host, port in self.endpoints:
            self.udp(name, host, port, self.a.udp_seconds, self.a.udp_bitrate)

    def run(self):
        if self.a.offset:
            self.logline(f"stagger sleep {self.a.offset}s")
            time.sleep(self.a.offset)
        start = time.time()
        end = start + self.a.hours * 3600
        next_light = next_iperf = next_udp = next_voice = start
        self.logline(f"TOPUP START hours={self.a.hours} link={self.a.link} device={self.a.device}")
        while time.time() < end:
            now = time.time()
            if now >= next_light:
                self.light()
                next_light += self.a.light_interval
            if now >= next_iperf:
                self.iperf_cycle()
                next_iperf += self.a.iperf_interval
            if now >= next_udp:
                self.udp_cycle()
                next_udp += self.a.udp_interval
            if now >= next_voice:
                self.voice_mos(self.a.lab_host)
                next_voice += self.a.voice_interval
            time.sleep(2)
        self.logline("TOPUP COMPLETE")

    def schema_demo(self):
        """Write one illustrative row of each KPI. Not a measurement."""
        self.sample("KPI-003", "RTT average", 11.2, "ms", "PASS", "lab.example", "lab")
        self.sample("KPI-008", "TCP connect - eand.ae", 8.1, "ms", "PASS", "https://www.eand.ae/", "public")
        self.sample("KPI-009", "TLS handshake - eand.ae", 30.2, "ms", "PASS", "https://www.eand.ae/", "public")
        self.sample("KPI-007", "TTFB - eand.ae", 75.0, "ms", "PASS", "https://www.eand.ae/", "public")
        self.sample("KPI-001", "Download throughput", 700.0, "Mbps", "PASS", "lab.example:5202", "lab", 4, 30, 12, 2621440000)
        self.sample("KPI-003L", "RTT under load", 14.5, "ms", "PASS", "lab.example", "lab")
        self.sample("KPI-005", "UDP packet loss", 0.0, "%", "PASS", "lab.example:5202", "lab", "", 60, "", 75000000)
        self.sample("KPI-033", "Estimated Voice MOS", 4.40, "MOS", "PASS", "lab.example", "lab")
        demo = {
            "start": {"test_start": {"protocol": "TCP", "num_streams": 4, "duration": 30}},
            "end": {"sum_received": {"bits_per_second": 700000000, "bytes": 2621440000, "seconds": 30, "retransmits": 12}},
        }
        (self.dir / "iperf" / "iperf_SAMPLE_lab_download.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
        self.logline("SCHEMA DEMO written. These rows are examples, not measurements.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", required=True)
    ap.add_argument("--link", required=True)
    ap.add_argument("--device", required=True)
    ap.add_argument("--lab-host", required=True)
    ap.add_argument("--uae-host", required=True)
    ap.add_argument("--eu-host", required=True)
    ap.add_argument("--iperf-port", type=int, required=True)
    ap.add_argument("--iperf-streams", type=int, default=4)
    ap.add_argument("--iperf-seconds", type=int, default=30)
    ap.add_argument("--udp-bitrate", default="10M")
    ap.add_argument("--udp-seconds", type=int, default=60)
    ap.add_argument("--https1", required=True)
    ap.add_argument("--name1", required=True)
    ap.add_argument("--https2", required=True)
    ap.add_argument("--name2", required=True)
    ap.add_argument("--dns-server", required=True)
    ap.add_argument("--dns-name", required=True)
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--light-interval", type=int, default=300)
    ap.add_argument("--iperf-interval", type=int, default=1800)
    ap.add_argument("--udp-interval", type=int, default=900)
    ap.add_argument("--voice-interval", type=int, default=1800)
    ap.add_argument("--ping-wait", type=int, default=2)
    ap.add_argument("--dig-query", type=int, default=3)
    ap.add_argument("--dig-timeout", type=int, default=10)
    ap.add_argument("--curl-max", type=int, default=30)
    ap.add_argument("--curl-timeout", type=int, default=40)
    ap.add_argument("--iperf-extra", type=int, default=30)
    ap.add_argument("--voice-seconds", type=int, default=150)
    ap.add_argument("--outdir", default="")
    ap.add_argument("--schema-demo", action="store_true")
    a = ap.parse_args()
    if not a.outdir:
        a.outdir = str(Path("results") / re.sub(r"[^A-Za-z0-9_-]+", "_", a.network))
    probe = Probe(a)
    if a.schema_demo:
        probe.schema_demo()
    else:
        probe.run()

if __name__ == "__main__":
    main()
