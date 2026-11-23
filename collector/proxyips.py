"""Proxy server IPs: dedicated servers that host bypass sites under many
rotating names.

A server's IP address is far more stable than the names pointed at it, so an
IP feed (fortigate/proxyips.txt) blocks every current and future name on a
confirmed proxy server, including names no source has seen yet.

Safety first: an IP only qualifies when it is clearly a single-purpose
proxy server. Cloud, CDN and shared-hosting ranges, any IP that also serves a
free-hosting platform subdomain, an allowlisted site or a ranked (popular)
domain, and private/reserved addresses are excluded. Everything else needs
evidence: >= min_confirmed confirmed bypass names making up >= min_ratio of
the names seen on it, or a manual confirmation (seeds/proxyips-confirmed.txt).
Suspicious servers that don't meet the bar are held for review as one item.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import ipaddress
import re
import socket
from pathlib import Path

# Proxy / decoy naming that, on a server full of stalled names, is worth a
# human look: proxy framework names, unblock vocabulary, school-tool decoys
# and common typosquats of them.
NAME_HINT = re.compile(
    r"rammer|proxy|ubg|unbl|bypass|scram|ultraviolet|\buv\b|nebula|interstellar|"
    r"school|schoo|classroom|clas+link|canvas|schoolo[gq]y|ixl|coursera|edu|learn|"
    r"study|math|homework|tutor|portal", re.I)


def load_exclusions(cfg: dict, root: Path, http_get, log) -> list:
    """Networks that must never appear in the IP feed."""
    nets = []
    cache = root / "data" / "cloudflare-ips.txt"
    try:
        data, _ = http_get("https://www.cloudflare.com/ips-v4", timeout=20, max_bytes=100_000)
        text = data.decode()
        if "/" in text:
            cache.parent.mkdir(exist_ok=True)
            cache.write_text(text)
    except Exception as e:  # noqa: BLE001
        log(f"[proxyips] Cloudflare ranges fetch failed ({e}); using cache")
    if cache.exists():
        nets += [ipaddress.ip_network(l.strip()) for l in cache.read_text().split() if "/" in l]
    else:
        # Hard fallback: Cloudflare's long-standing ranges.
        nets += [ipaddress.ip_network(n) for n in (
            "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
            "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
            "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
            "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22")]
    for c in cfg.get("shared_ranges", []):
        try:
            nets.append(ipaddress.ip_network(c, strict=False))
        except ValueError:
            log(f"[proxyips] bad shared range {c!r}")
    return nets


def excluded(ip: str, nets: list) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if a.version != 4 or not a.is_global:
        return True
    return any(a in n for n in nets)


def network_owner(ip: str, state: dict, http_get, today: dt.date) -> tuple[int | None, str]:
    """(ASN, holder) for an IP via RIPEstat (free, no key), cached 30 days."""
    cache = state.setdefault("ip_owner", {})
    c = cache.get(ip)
    if c and (today - dt.date.fromisoformat(c["checked"])).days < 30:
        return c.get("asn"), c.get("holder", "")
    try:
        import json
        data, _ = http_get(f"https://stat.ripe.net/data/prefix-overview/data.json?resource={ip}",
                           timeout=20, max_bytes=200_000)
        a = (json.loads(data)["data"].get("asns") or [{}])[0]
        cache[ip] = {"asn": a.get("asn"), "holder": a.get("holder") or "", "checked": today.isoformat()}
    except Exception:  # noqa: BLE001
        return None, ""  # unknown owner: treated as not verifiable (not published)
    return cache[ip]["asn"], cache[ip]["holder"]


def shared_owner(asn, holder: str, cfg: dict) -> bool:
    if asn is None:
        return True
    if asn in set(cfg.get("excluded_asns", [])):
        return True
    return any(re.search(p, holder, re.I) for p in cfg.get("excluded_owner_patterns", []))


def resolve_entries(entries: dict, eligible, today: str, budget: int, metrics) -> None:
    """Record current A records for eligible host entries (re-resolved daily)."""
    todo = [k for k, e in entries.items() if eligible(k, e) and e.get("ips_checked") != today]
    todo = todo[:budget]

    def res(h):
        try:
            return h, sorted(set(socket.gethostbyname_ex(h)[2]))
        except Exception:  # noqa: BLE001
            return h, []
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(5)
    try:
        with cf.ThreadPoolExecutor(64) as ex:
            for h, ips in ex.map(res, todo):
                e = entries[h]
                e["ips_checked"] = today
                if ips:
                    e["ips"] = ips
                metrics["proxyips_hosts_resolved"] += 1
    finally:
        socket.setdefaulttimeout(old)


def evaluate(state: dict, cfg: dict, nets: list, allow, platforms: set[str], popular_rank,
             platform_apex, trusted_sources: tuple, confirmed_seed: set[str],
             dismissed: set[str], today: dt.date, metrics, log, http_get=None) -> list[str]:
    """Decide which IPs are proxy servers. Returns the sorted IP list."""
    entries = state.get("entries", {})
    reg = state.setdefault("proxy_ips", {})
    min_confirmed = cfg.get("min_confirmed", 2)
    min_ratio = cfg.get("min_ratio", 0.6)
    max_age = cfg.get("max_age_days", 30)
    held_min = cfg.get("held_min_names", 3)

    by_ip: dict[str, list[str]] = {}
    for k, e in entries.items():
        if e["kind"] == "host" and e.get("ips") and e["status"] in ("confirmed", "pending", "new"):
            for ip in e["ips"]:
                by_ip.setdefault(ip, []).append(k)

    t = today.isoformat()
    for ip, hosts in by_ip.items():
        if excluded(ip, nets):
            continue
        # Shared hosting tell-tales: any platform subdomain, allowlisted or
        # ranked domain on the same IP means it is not single-purpose.
        def popular_site_itself(h):
            pr = popular_rank(h, platforms)
            return bool(pr) and h in (pr[0], "www." + pr[0])
        if any(platform_apex(h, platforms) or allow.matches(h) or popular_site_itself(h)
               for h in hosts):
            metrics["proxyips_shared_excluded"] += 1
            continue
        conf = [h for h in hosts if entries[h]["status"] == "confirmed"]
        # Only bypass-grade evidence counts toward qualifying a server: names
        # from student bypass lists / urlscan, or confirmed as proxy, clone,
        # impersonation or loader. Ordinary game sites found on GitHub are
        # real games but usually sit on shared platforms.
        bypass = [h for h in conf if entries[h]["source"].startswith(trusted_sources)
                  or entries[h].get("category") in ("proxy", "clone", "impersonation", "loader")]
        rec = reg.setdefault(ip, {"first_seen": t, "status": "watch"})
        rec.update(names=sorted(hosts)[:20], total=len(hosts), confirmed=len(conf))
        key = f"ip:{ip}"
        if key in dismissed:
            rec["status"] = "dismissed"
            continue
        if ip in confirmed_seed:
            rec.update(status="confirmed", last_seen=t, reason="confirmed by reviewer")
        elif len(bypass) >= min_confirmed and len(conf) / len(hosts) >= min_ratio:
            rec.update(status="confirmed", last_seen=t,
                       reason=f"{len(bypass)} of {len(hosts)} names are confirmed bypass sites")
        elif rec.get("status") != "confirmed":
            from_lists = [h for h in hosts if entries[h]["source"].startswith(trusted_sources)]
            hinted = [h for h in hosts if NAME_HINT.search(h)]
            if len(hosts) >= held_min and from_lists and hinted:
                rec.update(status="held", reason=(
                    f"{len(hosts)} names on one dedicated server, none confirmable "
                    f"(e.g. behind a challenge); names like {', '.join(sorted(hinted)[:3])}"))
            else:
                rec["status"] = "watch"
    # Manual confirmations for IPs we have no names for yet still apply.
    for ip in confirmed_seed:
        if not excluded(ip, nets):
            reg.setdefault(ip, {"first_seen": t}).update(
                status="confirmed", last_seen=t, reason="confirmed by reviewer")

    # Network owner check: cloud, CDN, PaaS, parking and shared-hosting
    # networks are never published, whatever the evidence.
    for ip, rec in reg.items():
        if rec.get("status") in ("confirmed", "held") and http_get is not None:
            asn, holder = network_owner(ip, state, http_get, today)
            rec["owner"] = f"AS{asn} {holder}"[:80] if asn else "unknown"
            if shared_owner(asn, holder, cfg):
                rec["status"] = "excluded"
                rec["reason"] = f"shared or unverifiable network: {rec['owner']}"
                metrics["proxyips_owner_excluded"] += 1
                if ip in confirmed_seed:
                    log(f"[proxyips] seed {ip} NOT published: {rec['reason']}")

    out = []
    for ip, rec in list(reg.items()):
        if rec.get("status") == "confirmed":
            age = (today - dt.date.fromisoformat(rec.get("last_seen", t))).days
            if age > max_age and ip not in confirmed_seed:
                rec["status"] = "expired"
                metrics["proxyips_expired"] += 1
                continue
            if excluded(ip, nets):
                rec["status"] = "excluded"
                continue
            out.append(ip)
        elif rec.get("status") == "watch" and rec.get("last_seen") is None and \
                (today - dt.date.fromisoformat(rec["first_seen"])).days > 90:
            del reg[ip]
    metrics["proxyips_published"] = len(out)
    metrics["proxyips_held"] = sum(1 for r in reg.values() if r.get("status") == "held")
    log(f"[proxyips] {len(out)} proxy server IPs, {metrics['proxyips_held']} held for review")
    return sorted(out, key=lambda x: tuple(int(p) for p in x.split(".")))
