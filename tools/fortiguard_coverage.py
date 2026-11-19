#!/usr/bin/env python3
"""Measure how much of the feed FortiGuard already rates as Games.

Runs on a machine inside your network that can reach a FortiGate's REST API.
Uses the FortiOS monitor endpoint `utm/rating-lookup` (FortiOS 7.x) with a
read-only REST API admin token. Nothing is changed on the FortiGate.

    export FGT_HOST=10.0.0.1            # FortiGate mgmt address[:port]
    export FGT_TOKEN=xxxxxxxx           # REST API admin token (read-only profile)
    python3 tools/fortiguard_coverage.py --sample 500
    python3 tools/fortiguard_coverage.py --file fortigate/domains-priority.txt --all

Writes review/fortiguard-coverage.csv (host, category) and prints a summary.
Hosts NOT rated Games are the ones this feed adds on top of your FortiGuard
category block; submit the best of them for re-rating at
https://www.fortiguard.com/faq/wfratingsubmit so other districts benefit.

NOTE: written against the documented FortiOS REST API; verify on your
firmware (`GET /api/v2/monitor/utm/rating-lookup?url=example.com`) first.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import random
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME_CATEGORIES = {"games"}


def lookup(host: str, base: str, token: str, ctx: ssl.SSLContext) -> str:
    q = urllib.parse.urlencode({"url": host})
    req = urllib.request.Request(f"{base}/api/v2/monitor/utm/rating-lookup?{q}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        data = json.loads(r.read())
    res = data.get("results")
    if isinstance(res, list):
        res = res[0] if res else {}
    res = res or {}
    return str(res.get("category_name") or res.get("category") or res.get("rating") or "unknown")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / "fortigate" / "domains-priority.txt"))
    ap.add_argument("--sample", type=int, default=300, help="random sample size")
    ap.add_argument("--all", action="store_true", help="look up every host")
    ap.add_argument("--delay", type=float, default=0.2)
    ap.add_argument("--insecure", action="store_true", help="skip TLS verify (self-signed mgmt cert)")
    a = ap.parse_args()

    host, token = os.environ.get("FGT_HOST"), os.environ.get("FGT_TOKEN")
    if not host or not token:
        sys.exit("set FGT_HOST and FGT_TOKEN")
    base = host if host.startswith("http") else f"https://{host}"
    ctx = ssl.create_default_context()
    if a.insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    hosts = sorted({l.strip().lstrip("*.") for l in Path(a.file).read_text().splitlines()
                    if l.strip() and not l.startswith("#")})
    if not a.all and len(hosts) > a.sample:
        hosts = random.sample(hosts, a.sample)

    rows, counts = [], collections.Counter()
    for i, h in enumerate(hosts, 1):
        try:
            cat = lookup(h, base, token, ctx)
        except Exception as e:  # noqa: BLE001
            cat = f"error: {e}"
        rows.append((h, cat))
        counts[cat] += 1
        if i % 50 == 0:
            print(f"  {i}/{len(hosts)}", file=sys.stderr)
        time.sleep(a.delay)

    out = ROOT / "review" / "fortiguard-coverage.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["host", "fortiguard_category"])
        w.writerows(sorted(rows))

    total = len(rows)
    games = sum(n for c, n in counts.items() if c.lower() in GAME_CATEGORIES)
    print(f"\nChecked {total} hosts from {a.file}")
    print(f"Rated Games by FortiGuard: {games} ({games / max(total, 1):.0%})")
    print(f"NOT rated Games (feed adds coverage): {total - games} ({(total - games) / max(total, 1):.0%})")
    print("\nTop categories:")
    for c, n in counts.most_common(15):
        print(f"  {n:6d}  {c}")
    print(f"\nDetail: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
