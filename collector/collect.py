#!/usr/bin/env python3
"""EdTechBlockFeed collector.

Pulls curated gaming blocklists, discovers new unblocked-games sites (GitHub,
link aggregators, Certificate Transparency), fingerprints discovered hosts
live, and writes FortiGate-readable threat feed files.

Standard library only. Run from the repository root:

    python3 collector/collect.py            # full run
    python3 collector/collect.py --no-discovery --no-verify   # lists only
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import io
import json
import os
import re
import sys
import tarfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fingerprint import classify  # noqa: E402
from hostutil import (  # noqa: E402
    Matcher,
    extract_urls,
    normalize_host,
    platform_apex,
    read_list,
)

ROOT = Path(__file__).resolve().parent.parent
TODAY = dt.date.today()
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36 EdTechBlockFeed"
)

# Hosts that show up in READMEs/aggregators but are never game sites.
NOISE = Matcher([
    "*.shields.io", "*.discord.gg", "*.discordapp.com", "*.twitter.com", "*.x.com",
    "*.tiktok.com", "*.instagram.com", "*.facebook.com", "*.patreon.com", "*.ko-fi.com",
    "*.buymeacoffee.com", "*.npmjs.com", "*.npmjs.org", "*.vercel.com", "*.netlify.com",
    "*.heroku.com", "*.render.com", "*.railway.app", "*.replit.com", "*.codesandbox.io",
    "*.gitlab.com", "*.bitbucket.org", "*.mozilla.org", "*.w3.org", "*.w3schools.com",
    "*.stackoverflow.com", "*.medium.com", "*.paypal.com", "*.paypal.me", "*.cash.app",
    "*.opensource.org", "*.creativecommons.org", "*.choosealicense.com", "*.gnu.org",
    "*.titaniumnetwork.org", "*.nodejs.org", "*.python.org", "*.docker.com",
    "*.readthedocs.io", "*.gitbook.io", "*.notion.so", "*.linktr.ee", "*.twitch.tv",
    "*.steampowered.com", "*.imgur.com", "*.giphy.com", "*.tenor.com", "*.forms.gle",
    "*.goo.gl", "*.bit.ly", "*.t.co", "*.example.com", "*.localhost", "*.mit-license.org",
    "*.spdx.org", "*.vitejs.dev", "*.reactjs.org", "*.react.dev", "*.nextjs.org",
    "*.astro.build", "*.svelte.dev", "*.tailwindcss.com", "*.fontawesome.com",
    "*.fonts.google.com", "*.analytics.google.com", "*.googletagmanager.com",
    "*.skillicons.dev", "*.readme-typing-svg.demolab.com", "*.komarev.com",
    "*.star-history.com", "*.api.star-history.com", "*.contrib.rocks", "*.repobeats.axiom.co",
    "*.wakatime.com", "*.github-readme-stats.vercel.app", "*.github-profile-trophy.vercel.app",
])


# A README link is only a candidate if it's on a free-hosting platform or its
# URL looks game/bypass related (keeps verification budget for likely hits).
HINT_RE = re.compile(
    r"game|gms|unbl|ubg|arcade|play|math|fun|hub|vault|proxy|nova|nebula|lunar|"
    r"astro|shadow|void|doge|space|ghost|emerald|selenite|eagler|retro|bowl|slope|"
    r"school|class|edu|learn|study|bypass|kahoot|blooket|tab|portal|bored|chill|"
    r"poki|crazy|friv|kizi|y8|io\b", re.I)


# --------------------------------------------------------------------------- io

def log(*a):
    print(*a, file=sys.stderr, flush=True)


def http_get(url: str, *, timeout: float = 30, max_bytes: int = 50_000_000,
             headers: dict | None = None) -> tuple[bytes, str]:
    """GET url, return (body, final_url). Raises on HTTP/network error."""
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(max_bytes + 1)
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data[:max_bytes], r.geturl()


def date_str(d: dt.date) -> str:
    return d.isoformat()


def days_since(s: str | None) -> int:
    if not s:
        return 10**6
    return (TODAY - dt.date.fromisoformat(s)).days


# ------------------------------------------------------------------- lists

def parse_list(data: bytes, fmt: str) -> list[str]:
    if fmt == "ut1":
        out: list[str] = []
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for m in tf.getmembers():
                if m.isfile() and m.name.endswith("/domains"):
                    f = tf.extractfile(m)
                    if f:
                        out.extend(f.read().decode("utf-8", "replace").splitlines())
        lines = out
    elif fmt == "adguard-services":
        lines = []
        for svc in json.loads(data).get("blocked_services", []):
            if svc.get("group") == "gaming":
                lines.extend(svc.get("rules", []))
    else:
        lines = data.decode("utf-8", "replace").splitlines()
    hosts = []
    for line in lines:
        if fmt == "adblock":
            line = line.strip()
            if line.startswith("@@") or not line.startswith("||"):
                continue  # exceptions, cosmetic and regex rules
            if "/" in re.split(r"[\^$]", line[2:], maxsplit=1)[0]:
                continue  # path rule: can't express as a whole-domain block
        h = normalize_host(line)
        if h:
            hosts.append(h)
    return hosts


def fetch_lists(cfg: dict) -> dict[str, tuple[str, set[str], bool]]:
    """Return {list_name: (tier, hosts)}. Falls back to the cached copy in
    data/lists/ when a source is unreachable."""
    cache_dir = ROOT / "data" / "lists"
    cache_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for src in cfg.get("lists", []):
        name, tier = src["name"], src.get("tier", "general")
        cache = cache_dir / f"{name}.txt"
        hosts: set[str] = set()
        try:
            data, _ = http_get(src["url"], timeout=90)
            hosts = set(parse_list(data, src.get("format", "domains")))
            if not hosts:
                raise ValueError("parsed 0 hosts")
            new_text = "\n".join(sorted(hosts)) + "\n"
            if not cache.exists() or cache.read_text() != new_text:
                cache.write_text(new_text)
            log(f"[list] {name}: {len(hosts)} hosts")
        except Exception as e:  # noqa: BLE001
            if cache.exists():
                hosts = set(cache.read_text().split())
                log(f"[list] {name}: FETCH FAILED ({e}); using cache ({len(hosts)})")
            else:
                log(f"[list] {name}: FETCH FAILED ({e}); no cache")
        result[name] = (tier, hosts, src.get("trusted", True))
    return result


# --------------------------------------------------------------- discovery

class Candidates:
    """Discovered URLs, keyed by the feed entry they would produce."""

    def __init__(self, allow: Matcher, platforms: set[str], url_platforms: dict[str, int]):
        self.allow, self.platforms, self.url_platforms = allow, platforms, url_platforms
        self.items: dict[str, dict] = {}  # key -> {kind, check_url, source, priority}

    def add(self, url: str, source: str, priority: int = 1, require_hint: bool = False) -> None:
        if "://" not in url:
            url = "https://" + url
        try:
            parts = urllib.parse.urlsplit(url)
        except ValueError:
            return
        host = normalize_host(parts.hostname or "")
        if not host or self.allow.matches(host) or NOISE.matches(host):
            return
        if host in self.platforms:
            return  # bare platform apex
        if require_hint and not (platform_apex(host, self.platforms) or HINT_RE.search(url)):
            return
        if host in self.url_platforms:
            segs = [s for s in parts.path.split("/") if s][: self.url_platforms[host]]
            if len(segs) < self.url_platforms[host]:
                return
            key, kind = host + "/" + "/".join(segs), "url"
        else:
            if self.allow.matches(host):
                return
            key, kind = host, "host"
        cur = self.items.get(key)
        if cur is None or priority > cur["priority"]:
            self.items[key] = {"kind": kind, "check_url": url, "source": source,
                               "priority": priority}


def gh_headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def discover_github(cfg: dict, cands: Candidates, state: dict) -> None:
    g = cfg.get("github", {})
    if not g:
        return
    authed = "Authorization" in gh_headers()
    pause = 2.2 if authed else 6.5  # search API: 30/min authed, 10/min anon
    since = date_str(TODAY - dt.timedelta(days=g.get("pushed_within_days", 120)))
    queries = [f"topic:{t} pushed:>{since}" for t in g.get("topics", [])]
    queries += [f"{q} pushed:>{since}" for q in g.get("queries", [])]
    repos: dict[str, dict] = {}
    for q in queries:
        for page in range(1, g.get("max_pages", 5) + 1):
            url = ("https://api.github.com/search/repositories?"
                   + urllib.parse.urlencode({"q": q, "sort": "updated", "order": "desc",
                                             "per_page": 100, "page": page}))
            try:
                data, _ = http_get(url, headers=gh_headers(), timeout=30)
                items = json.loads(data).get("items", [])
            except urllib.error.HTTPError as e:
                log(f"[github] {q!r} p{page}: HTTP {e.code}")
                if e.code in (403, 429):
                    time.sleep(60)
                break
            except Exception as e:  # noqa: BLE001
                log(f"[github] {q!r} p{page}: {e}")
                break
            finally:
                time.sleep(pause)
            for r in items:
                if not r.get("fork") or r.get("homepage"):
                    repos[r["full_name"]] = r
            if len(items) < 100:
                break
    log(f"[github] {len(repos)} repos from {len(queries)} queries")

    seen = state.setdefault("repos", {})
    readme_budget = g.get("max_readmes", 300)
    todo = []
    for full, r in repos.items():
        src = f"github:{full}"
        if r.get("homepage"):
            cands.add(r["homepage"].strip(), src, priority=3)
        if r.get("has_pages"):
            owner, name = full.split("/", 1)
            if name.lower() == f"{owner.lower()}.github.io":
                cands.add(f"https://{owner.lower()}.github.io/", src, priority=3)
            else:
                cands.add(f"https://{owner.lower()}.github.io/{name}/", src, priority=3)
        if seen.get(full) != r.get("pushed_at"):
            todo.append(r)
    todo.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    todo = todo[:readme_budget]

    def readme(r):
        full, br = r["full_name"], r.get("default_branch") or "main"
        for fn in ("README.md", "readme.md", "README.MD", "README"):
            try:
                data, _ = http_get(f"https://raw.githubusercontent.com/{full}/{br}/{fn}",
                                   timeout=20, max_bytes=2_000_000)
                return r, data.decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                continue
        return r, ""

    with cf.ThreadPoolExecutor(8) as ex:
        for r, text in ex.map(readme, todo):
            for u in extract_urls(text):
                cands.add(u, f"github-readme:{r['full_name']}", priority=1, require_hint=True)
            seen[r["full_name"]] = r.get("pushed_at")
    log(f"[github] scanned {len(todo)} READMEs")


def discover_aggregators(cfg: dict, cands: Candidates) -> None:
    for url in cfg.get("aggregators", {}).get("urls", []):
        try:
            data, _ = http_get(url, timeout=30, max_bytes=5_000_000)
        except Exception as e:  # noqa: BLE001
            log(f"[aggregator] {url}: {e}")
            continue
        n = 0
        for u in extract_urls(data.decode("utf-8", "replace")):
            cands.add(u, f"aggregator:{url}", priority=2)
            n += 1
        log(f"[aggregator] {url}: {n} links")


def discover_ct(cfg: dict, cands: Candidates) -> None:
    ct = cfg.get("ct", {})
    if not ct.get("enabled"):
        return
    cutoff = TODAY - dt.timedelta(days=45)

    def one(kw):
        url = ("https://crt.sh/?" + urllib.parse.urlencode(
            {"q": f"%{kw}%", "output": "json", "exclude": "expired"}))
        for attempt in range(3):
            try:
                data, _ = http_get(url, timeout=60, max_bytes=100_000_000)
                return kw, json.loads(data or b"[]")
            except Exception as e:  # noqa: BLE001
                err = e
                time.sleep(5 * (attempt + 1))
        log(f"[ct] {kw}: {err}")
        return kw, []

    with cf.ThreadPoolExecutor(3) as ex:
        for kw, rows in ex.map(one, ct.get("keywords", [])):
            n = 0
            for row in rows:
                try:
                    if dt.date.fromisoformat(row.get("not_before", "")[:10]) < cutoff:
                        continue
                except ValueError:
                    continue
                for name in str(row.get("name_value", "")).split("\n"):
                    h = normalize_host(name)
                    if h and kw.replace("-", "") in h.replace("-", ""):
                        cands.add(f"https://{h}/", f"ct:{kw}", priority=2)
                        n += 1
            log(f"[ct] {kw}: {len(rows)} certs, {n} names")


# ------------------------------------------------------------ verification

def verify(cands: Candidates, state: dict, settings: dict, do_verify: bool) -> None:
    """Merge candidates into state and fingerprint a budgeted batch."""
    entries = state.setdefault("entries", {})
    for key, c in cands.items.items():
        e = entries.get(key)
        if e is None:
            entries[key] = {"kind": c["kind"], "check_url": c["check_url"],
                            "source": c["source"], "first_seen": date_str(TODAY),
                            "last_seen": date_str(TODAY), "status": "new",
                            "attempts": 0, "priority": c["priority"]}
        else:
            e["last_seen"] = date_str(TODAY)
            if c["priority"] > e.get("priority", 0):
                e.update(check_url=c["check_url"], source=c["source"], priority=c["priority"])
    if not do_verify:
        return

    def due(e):
        st = e["status"]
        if st == "new":
            return True
        if st == "pending":
            return days_since(e.get("last_checked")) >= 1 and e["attempts"] < 4
        if st == "confirmed":
            return days_since(e.get("last_checked")) >= settings.get("reverify_after_days", 7)
        if st == "rejected":
            return days_since(e.get("last_checked")) >= 30 and days_since(e["last_seen"]) <= 3
        return False

    todo = [(k, e) for k, e in entries.items() if due(e)]
    order = {"new": 0, "pending": 1, "confirmed": 2, "rejected": 3}
    todo.sort(key=lambda kv: (order[kv[1]["status"]], -kv[1].get("priority", 0),
                              kv[1].get("last_checked") or ""))
    todo = todo[: settings.get("verify_max_hosts", 400)]
    log(f"[verify] checking {len(todo)} of {len(entries)} tracked entries")
    timeout = settings.get("verify_timeout", 10)

    def check(kv):
        k, e = kv
        url = e["check_url"] if e["kind"] == "url" else e["check_url"]
        return k, classify(url, timeout=timeout, ua=UA)

    redirected: list[tuple[str, str, str]] = []
    with cf.ThreadPoolExecutor(settings.get("verify_workers", 32)) as ex:
        for k, res in ex.map(check, todo):
            e = entries[k]
            e["last_checked"] = date_str(TODAY)
            e["attempts"] = e.get("attempts", 0) + 1
            e["evidence"] = res.evidence[:200]
            if res.verdict in ("game", "proxy"):
                e.update(status="confirmed", category=res.verdict,
                         last_alive=date_str(TODAY), attempts=0)
                redirected.append((res.final_url, k, res.verdict))
            elif res.verdict == "dead":
                if e["status"] != "confirmed":
                    e["status"] = "rejected" if e["attempts"] >= 3 else "pending"
            else:  # alive but no fingerprint
                if e["status"] == "confirmed":
                    e["last_alive"] = date_str(TODAY)  # keep; flag for review
                    e["needs_review"] = True
                else:
                    e["status"] = "rejected" if e["attempts"] >= 3 else "pending"


    # A confirmed site that redirected elsewhere: the landing host is a game
    # site too (often a custom domain behind a github.io/pages.dev mirror).
    for final, origin, verdict in redirected:
        tmp = Candidates(cands.allow, cands.platforms, cands.url_platforms)
        tmp.add(final, f"redirect:{origin}", priority=2)
        for key, c in tmp.items.items():
            if key not in entries or entries[key]["status"] != "confirmed":
                entries[key] = {"kind": c["kind"], "check_url": final, "source": c["source"],
                                "first_seen": date_str(TODAY), "last_seen": date_str(TODAY),
                                "status": "confirmed", "category": verdict, "attempts": 0,
                                "last_checked": date_str(TODAY), "last_alive": date_str(TODAY),
                                "priority": 2, "evidence": f"redirect target of {origin}"}


def age_out(state: dict, settings: dict) -> None:
    entries = state.get("entries", {})
    max_age = settings.get("discovered_max_age_days", 60)
    for k in list(entries):
        e = entries[k]
        if e["status"] == "confirmed" and days_since(e.get("last_alive")) > max_age:
            del entries[k]
        elif e["status"] in ("rejected", "pending", "new") and days_since(e["last_seen"]) > 90:
            del entries[k]


# ------------------------------------------------------------------ output

_2LD = {"co.uk", "org.uk", "ac.uk", "com.au", "net.au", "org.au", "co.nz", "com.br",
        "co.jp", "co.in", "com.mx", "co.za", "com.tr", "it.com", "us.com", "uk.com",
        "eu.com", "com.de", "co.com", "in.net", "br.com", "cn.com", "jp.net"}


def is_registrable(host: str) -> bool:
    labels = host.split(".")
    if len(labels) == 2:
        return True
    return len(labels) == 3 and ".".join(labels[1:]) in _2LD


def build_domain_lines(hosts: set[str], allow: Matcher, platforms: set[str],
                       wildcards: bool) -> list[str]:
    clean = set()
    for h in hosts:
        if allow.matches(h) or h in platforms or NOISE.matches(h):
            continue
        clean.add(h)
    lines = set()
    wild = set()
    if wildcards:
        wild = {h for h in clean if is_registrable(h) and not platform_apex(h, platforms)}
    for h in clean:
        # drop subdomains already covered by a wildcard of their parent
        parts = h.split(".")
        if any(".".join(parts[i:]) in wild for i in range(1, len(parts) - 1)):
            continue
        lines.add(h)
    lines |= {f"*.{h}" for h in wild}
    return sorted(lines, key=lambda x: (x.lstrip("*.").split(".")[::-1], x))


def write_feed(path: Path, lines: list[str], max_lines: int) -> list[str]:
    """Write one entry per line (no comments: FortiGate expects bare entries),
    splitting into path, path-2, ... Only rewrites files whose content changed."""
    chunks = [lines[i:i + max_lines] for i in range(0, len(lines), max_lines)] or [[]]
    written = []
    for i, chunk in enumerate(chunks, 1):
        p = path if i == 1 else path.with_name(f"{path.stem}-{i}{path.suffix}")
        body = "\n".join(chunk) + ("\n" if chunk else "")
        if not p.exists() or p.read_text() != body:
            p.write_text(body)
        written.append(p.name)
    j = len(chunks) + 1
    while (extra := path.with_name(f"{path.stem}-{j}{path.suffix}")).exists():
        extra.unlink()
        j += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-discovery", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--no-ct", action="store_true")
    args = ap.parse_args()

    cfg = tomllib.loads((ROOT / "config" / "sources.toml").read_text())
    settings = cfg.get("settings", {})
    allow = Matcher(read_list(ROOT / "seeds" / "allow.txt"))
    platforms = {h for h in (normalize_host(x) for x in read_list(ROOT / "seeds" / "platforms.txt")) if h}
    url_platforms = {}
    for line in read_list(ROOT / "seeds" / "url-platforms.txt"):
        parts = line.split()
        if parts and (h := normalize_host(parts[0])):
            url_platforms[h] = int(parts[1]) if len(parts) > 1 else 1

    state_path = ROOT / "data" / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    lists = fetch_lists(cfg)

    cands = Candidates(allow, platforms, url_platforms)
    if not args.no_discovery:
        discover_github(cfg, cands, state)
        discover_aggregators(cfg, cands)
        if not args.no_ct:
            discover_ct(cfg, cands)
        log(f"[discovery] {len(cands.items)} candidate entries")

    # Untrusted lists feed discovery; trusted lists go straight to the feed.
    if not args.no_discovery:
        for name, (_, hosts, trusted) in lists.items():
            if not trusted:
                for h in hosts:
                    cands.add(f"https://{h}/", f"list:{name}", priority=2)
    listed = set().union(*(h for _, h, t in lists.values() if t)) if lists else set()
    for k in [k for k, c in cands.items.items() if c["kind"] == "host" and k in listed]:
        del cands.items[k]

    verify(cands, state, settings, not args.no_verify)
    age_out(state, settings)

    # ---- assemble
    confirmed_seed = set()
    for line in read_list(ROOT / "seeds" / "confirmed.txt"):
        if h := normalize_host(line):
            confirmed_seed.add(h)
    entries = state.get("entries", {})
    disc_hosts = {k for k, e in entries.items() if e["kind"] == "host" and e["status"] == "confirmed"}
    disc_urls = {k for k, e in entries.items() if e["kind"] == "url" and e["status"] == "confirmed"}
    priority_lists = set().union(*(h for t, h, tr in lists.values() if tr and t == "priority")) if lists else set()

    wild = settings.get("emit_wildcards", True)
    all_lines = build_domain_lines(confirmed_seed | listed | disc_hosts, allow, platforms, wild)
    pri_lines = build_domain_lines(confirmed_seed | priority_lists | disc_hosts, allow, platforms, wild)

    url_lines = set(disc_urls)
    for line in read_list(ROOT / "seeds" / "confirmed-urls.txt"):
        url_lines.add(re.sub(r"^https?://", "", line).rstrip("/"))

    out = ROOT / "fortigate"
    out.mkdir(exist_ok=True)
    max_lines = settings.get("max_lines_per_file", 100000)
    f1 = write_feed(out / "domains.txt", all_lines, max_lines)
    f2 = write_feed(out / "domains-priority.txt", pri_lines, max_lines)
    f3 = write_feed(out / "urls.txt", sorted(url_lines), max_lines)

    # ---- review queue for humans / the daily triage agent
    rev = ROOT / "review"
    rev.mkdir(exist_ok=True)
    pend = sorted((k, e) for k, e in entries.items()
                  if e["status"] == "pending" or e.get("needs_review"))
    lines = ["# Discovered entries that are alive but did not match a game/proxy fingerprint,",
             "# or confirmed entries whose fingerprint disappeared. Move real game sites",
             "# into seeds/confirmed.txt; add false positives to seeds/allow.txt.",
             "# entry\tstatus\tfirst_seen\tsource\tcheck_url\tevidence"]
    for k, e in pend:
        lines.append("\t".join([k, e["status"], e["first_seen"], e["source"],
                                e["check_url"], e.get("evidence", "")]))
    (rev / "pending.txt").write_text("\n".join(lines) + "\n")

    stats = {
        "domains_txt_entries": len(all_lines),
        "domains_priority_entries": len(pri_lines),
        "urls_entries": len(url_lines),
        "lists": {n: len(h) for n, (_, h, _) in lists.items()},
        "discovered_confirmed": len(disc_hosts) + len(disc_urls),
        "discovered_pending": sum(1 for e in entries.values() if e["status"] == "pending"),
        "discovered_rejected": sum(1 for e in entries.values() if e["status"] == "rejected"),
        "files": f1 + f2 + f3,
    }
    state["last_run"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    state["stats"] = stats
    state_path.parent.mkdir(exist_ok=True)
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    log(json.dumps(stats, indent=2))
    if summ := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summ, "a") as f:
            f.write("## Feed stats\n```json\n" + json.dumps(stats, indent=2) + "\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
