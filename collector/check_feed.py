#!/usr/bin/env python3
"""Safety check run before every publish (see the workflow).

Fails (exit 1) if any output feed contains:
  * a domain covered by seeds/allow.txt,
  * a shared-platform/CDN network apex from seeds/platforms.txt, or a
    GitHub/npm file CDN host (collector/cdn.py, seeds/cdn-mirrors.txt), or
  * any CRITICAL domain below. These are hard-coded so that an accidental
    edit to seeds/allow.txt can't let them back in.
A failed check stops the workflow before the commit step, so the FortiGates
keep pulling the last good feed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cdn  # noqa: E402
from hostutil import Matcher, normalize_host, read_list  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Services Chromebooks, Google Workspace, Android apps and curriculum depend on.
CRITICAL = [
    "*.google.com", "*.googleapis.com", "*.gstatic.com", "*.googleusercontent.com",
    "*.gvt1.com", "*.gvt2.com", "*.gvt3.com", "*.1e100.net", "*.ggpht.com",
    "*.android.com", "*.googlevideo.com", "*.ytimg.com", "*.youtube.com",
    "*.chromium.org", "*.pki.goog", "*.microsoft.com", "*.microsoftonline.com",
    "*.office.com", "*.msauth.net", "*.msftauth.net", "*.apple.com", "*.icloud.com", "*.github.com",
    "*.githubusercontent.com", "*.jsdelivr.net", "*.unpkg.com", "*.cloudflare.com",
    "*.amazonaws.com", "*.edu", "*.gov",
    # Curriculum / assessment platforms students need.
    "*.amplify.com",
]


def main() -> int:
    allow = Matcher(read_list(ROOT / "seeds" / "allow.txt"))
    critical = Matcher(CRITICAL)
    platforms = {h for h in (normalize_host(x) for x in read_list(ROOT / "seeds" / "platforms.txt")) if h}
    # GitHub/npm file CDNs and their mirrors are never blocked as whole hosts.
    for line in read_list(ROOT / "seeds" / "cdn-mirrors.txt"):
        parts = line.split()
        if len(parts) == 2 and parts[1] != "ignore":
            cdn.register(parts[0], parts[1])
    platforms |= cdn.CDN_HOSTS
    problems = []
    for f in sorted((ROOT / "fortigate").glob("domains*.txt")):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            h = normalize_host(line)
            if not h:
                continue
            why = ("CRITICAL" if critical.matches(h) else
                   "allowlist" if allow.matches(h) else
                   "platform apex" if h in platforms else None)
            if why:
                problems.append(f"{f.name}:{n}: {line}  ({why})")
    for f in sorted((ROOT / "fortigate").glob("urls*.txt")):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            host = line.split("/", 1)[0]
            if "/" not in line.rstrip("*").rstrip("/") and critical.matches(host):
                problems.append(f"{f.name}:{n}: {line}  (whole critical host)")
    if problems:
        print(f"FEED CHECK FAILED: {len(problems)} protected entries in output")
        print("\n".join(problems[:200]))
        return 1
    print("Feed check passed: no protected domains in output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
