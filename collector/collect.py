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
import collections
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
import cdn  # noqa: E402
import hashlib  # noqa: E402
import socket  # noqa: E402
from fingerprint import FINGERPRINT_VERSION, classify  # noqa: E402
from hostutil import (  # noqa: E402
    Matcher,
    extract_urls,
    normalize_host,
    platform_apex,
    read_list,
)

ROOT = Path(__file__).resolve().parent.parent
TODAY = dt.date.today()
# Per-run counters of every check performed (published to docs/latest-run.md).
METRICS: collections.Counter = collections.Counter()
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


# ------------------------------------------------------- popularity guard

POPULAR: dict[str, int] = {}   # registrable domain -> Tranco rank


def load_popular(settings: dict, state: dict) -> None:
    """Domain popularity from the Tranco research ranking (top
    `popular_list_size`). Used only for sites the collector *discovers*;
    curated lists are unaffected. Refreshed weekly, cached in
    data/popular-domains.txt so a Tranco outage never disables the guards."""
    size = settings.get("popular_list_size", 100000)
    cache = ROOT / "data" / "popular-domains.txt"
    fresh = days_since(state.get("popular_fetched")) < 7 and cache.exists()
    if not fresh:
        try:
            data, _ = http_get("https://tranco-list.eu/top-1m.csv.zip", timeout=90,
                               max_bytes=60_000_000)
            import zipfile
            z = zipfile.ZipFile(io.BytesIO(data))
            lines = z.read(z.namelist()[0]).decode("utf-8", "replace").splitlines()[:size]
            ranked = [l.split(",", 1) for l in lines if "," in l]
            if len(ranked) < size // 2:
                raise ValueError(f"only {len(ranked)} domains parsed")
            cache.write_text("".join(f"{d.strip().lower()} {r}\n" for r, d in ranked))
            state["popular_fetched"] = date_str(TODAY)
            log(f"[popular] Tranco top {len(ranked)} refreshed")
        except Exception as e:  # noqa: BLE001
            log(f"[popular] refresh failed ({e}); using cache")
    if cache.exists():
        for line in cache.read_text().splitlines():
            d, _, r = line.partition(" ")
            if r.isdigit():
                POPULAR[d] = int(r)
    if not POPULAR:
        log("[popular] no ranking available: popularity guards inactive this run")


def popular_rank(host: str, platforms: set[str]) -> tuple[str, int] | None:
    """(domain, rank) if host belongs to a ranked site. Subdomains of shared
    free-hosting platforms (user.github.io) belong to one author, so the
    platform's own rank doesn't count."""
    if platform_apex(host, platforms) or host in cdn.CDN_HOSTS:
        return None
    parts = host.split(".")
    for i in range(len(parts) - 1):
        d = ".".join(parts[i:])
        if d in POPULAR:
            return d, POPULAR[d]
    return None


# --------------------------------------------------------------- discovery

class Candidates:
    """Discovered URLs, keyed by the feed entry they would produce.

    kind = "host" -> whole-domain entry (domains.txt)
           "url"  -> path entry on a shared host, e.g. sites.google.com/view/x
           "cdn"  -> a file in a GitHub repo / npm package served by a public CDN
    """

    def __init__(self, allow: Matcher, platforms: set[str],
                 url_platforms: dict[str, re.Pattern], cdn_owner_allow: set[str]):
        self.allow, self.platforms, self.url_platforms = allow, platforms, url_platforms
        self.cdn_owner_allow = cdn_owner_allow
        self.items: dict[str, dict] = {}
        # Unknown hosts whose links look like GitHub/npm CDN paths:
        # host -> [(url, style, source)]. Resolved by detect_new_cdns().
        self.cdn_shapes: dict[str, list[tuple[str, str, str]]] = {}
        self.cdn_ignore: set[str] = set()

    def _put(self, key: str, kind: str, url: str, source: str, priority: int, **extra) -> None:
        cur = self.items.get(key)
        if cur is None or priority > cur["priority"]:
            self.items[key] = {"kind": kind, "check_url": url, "source": source,
                               "priority": priority, **extra}

    def add(self, url: str, source: str, priority: int = 1, require_hint: bool = False) -> None:
        METRICS["links_examined"] += 1
        if "://" not in url:
            url = "https://" + url
        try:
            parts = urllib.parse.urlsplit(url)
        except ValueError:
            return
        host = normalize_host(parts.hostname or "")
        if not host:
            METRICS["links_dropped_invalid"] += 1
            return
        raw_host = (parts.hostname or "").lower()

        # 1. Shared file CDNs (jsDelivr, unpkg, esm.sh, statically, githack).
        #    Handled before the allowlist, which protects these hosts as a whole.
        ref = cdn.parse(url)
        if ref is not None:
            if not cdn.ENTRY_EXT.search(ref.file):
                METRICS["cdn_links_not_entry_file"] += 1
                return
            if cdn.TEST_PATH.search(ref.file) or cdn.TEST_PATH.search(ref.repo):
                METRICS["cdn_links_test_fixture"] += 1
                return
            if ref.owner.lower() in self.cdn_owner_allow:
                METRICS["cdn_links_allowlisted_owner"] += 1
                return
            METRICS["cdn_links_candidate"] += 1
            self._put("cdn:" + ref.key, "cdn", url, source, priority,
                      cdn_kind=ref.kind, owner=ref.owner, repo=ref.repo)
            return
        if raw_host in cdn.CDN_HOSTS:
            METRICS["cdn_links_unparsed"] += 1
            return

        # 1b. Unknown host, but the link looks like a GitHub/npm CDN path
        #     (/gh/owner/repo@ref/..., /npm/pkg@ver/..., /owner/repo/main/x.svg).
        #     Held for new-CDN detection; never treated as a whole-host block.
        #     The allowlist doesn't apply here: CDN handling is path-level only,
        #     and new *.jsdelivr.net-style hostnames are the likeliest mirrors.
        if raw_host not in self.cdn_ignore:
            style = cdn.infer_style(urllib.parse.unquote(parts.path))
            if style:
                METRICS["cdn_shape_links"] += 1
                self.cdn_shapes.setdefault(raw_host, []).append((url, style, source))
                return

        # 2. Path-level platforms (Google Sites, Apps Script, ...).
        rx = self.url_platforms.get(raw_host) or self.url_platforms.get(host)
        if rx is not None:
            m = rx.match(urllib.parse.unquote(parts.path))
            if not m:
                METRICS["url_platform_links_unmatched"] += 1
                return
            METRICS["url_platform_links_candidate"] += 1
            self._put(raw_host + m.group(0).rstrip("/"), "url", url, source, priority)
            return

        # 3. Whole hosts.
        if self.allow.matches(host):
            METRICS["links_dropped_allowlist"] += 1
            return
        if NOISE.matches(host):
            METRICS["links_dropped_noise"] += 1
            return
        if host in self.platforms:
            METRICS["links_dropped_platform_apex"] += 1
            return
        if require_hint and not (platform_apex(host, self.platforms) or HINT_RE.search(url)):
            METRICS["links_dropped_no_hint"] += 1
            return
        METRICS["host_links_candidate"] += 1
        self._put(host, "host", url, source, priority)


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
                METRICS["github_search_requests"] += 1
                METRICS["github_repos_returned"] += len(items)
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
    # Whole organisations (framework authors such as MercuryWorkshop and
    # Titanium Network): their repos' homepages/Pages are often live services.
    for org in g.get("orgs", []):
        try:
            data, _ = http_get(f"https://api.github.com/users/{org}/repos?per_page=100&sort=pushed",
                               headers=gh_headers(), timeout=30)
            org_repos = json.loads(data)
        except Exception:  # noqa: BLE001
            try:
                q = urllib.parse.urlencode({"q": f"user:{org}", "per_page": 100})
                data, _ = http_get(f"https://api.github.com/search/repositories?{q}",
                                   headers=gh_headers(), timeout=30)
                org_repos = json.loads(data).get("items", [])
                time.sleep(pause)
            except Exception as e:  # noqa: BLE001
                log(f"[github] org {org}: {e}")
                continue
        METRICS["github_org_repos_listed"] += len(org_repos)
        for r in org_repos:
            repos.setdefault(r["full_name"], r)
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
    METRICS["github_readmes_scanned"] += len(todo)
    METRICS["github_repos_unique"] += len(repos)
    log(f"[github] scanned {len(todo)} READMEs")


def discover_aggregators(cfg: dict, cands: Candidates) -> None:
    for url in cfg.get("aggregators", {}).get("urls", []):
        try:
            data, _ = http_get(url, timeout=30, max_bytes=5_000_000)
        except Exception as e:  # noqa: BLE001
            log(f"[aggregator] {url}: {e}")
            continue
        n = 0
        METRICS["aggregator_pages_fetched"] += 1
        for u in extract_urls(data.decode("utf-8", "replace")):
            cands.add(u, f"aggregator:{url}", priority=2)
            n += 1
        METRICS["aggregator_links_harvested"] += n
        log(f"[aggregator] {url}: {n} links")


def discover_ct(cfg: dict, cands: Candidates) -> None:
    ct = cfg.get("ct", {})
    if not ct.get("enabled"):
        return
    cutoff = TODAY - dt.timedelta(days=45)
    # Fail fast: crt.sh is often unreachable from CI runners; one short probe
    # instead of minutes of retries per keyword.
    try:
        http_get("https://crt.sh/?q=example.com&output=json&exclude=expired",
                 timeout=ct.get("probe_timeout", 20), max_bytes=200_000)
    except urllib.error.HTTPError:
        pass  # reachable, just unhappy with the probe query
    except Exception as e:  # noqa: BLE001
        METRICS["ct_unreachable"] += 1
        log(f"[ct] crt.sh unreachable ({str(e)[:60]}); skipped this run")
        return

    def one(kw):
        url = ("https://crt.sh/?" + urllib.parse.urlencode(
            {"q": f"%{kw}%", "output": "json", "exclude": "expired"}))
        for attempt in range(3):
            try:
                data, _ = http_get(url, timeout=60, max_bytes=100_000_000)
                return kw, json.loads(data or b"[]")
            except Exception as e:  # noqa: BLE001
                err = e
                if not isinstance(e, urllib.error.HTTPError):
                    break  # network-level failure: retrying won't help this run
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
            METRICS["ct_queries"] += 1
            METRICS["ct_certificates_examined"] += len(rows)
            METRICS["ct_names_matched"] += n
            log(f"[ct] {kw}: {len(rows)} certs, {n} names")


def discover_cdn(cfg: dict, cands: Candidates, state: dict) -> None:
    """Find more CDN loaders: expand known owners' repos, and code-search
    GitHub for files with the loader signature."""
    c = cfg.get("cdn", {})
    entries = state.get("entries", {})
    owners_state = state.setdefault("cdn_owners", {})
    known = {}
    for e in entries.values():
        if e["kind"] == "cdn" and e["status"] == "confirmed" and e.get("cdn_kind") == "gh":
            known.setdefault(e["owner"].lower(), e["owner"])
    due = [o for lo, o in known.items()
           if days_since(owners_state.get(lo, {}).get("last_expanded")) >= c.get("owner_expand_days", 1)]
    due = due[: c.get("owner_expand_max", 40)]

    search_lock = __import__("threading").Lock()

    def list_repos(owner):
        try:
            data, _ = http_get(f"https://api.github.com/users/{owner}/repos?per_page=100&sort=pushed",
                               headers=gh_headers(), timeout=30)
            return json.loads(data)
        except Exception:  # noqa: BLE001
            pass
        # Fallback: the search API (also works where /users/ is restricted).
        with search_lock:  # search API: 30 requests/minute
            time.sleep(2.2)
            q = urllib.parse.urlencode({"q": f"user:{owner}", "sort": "updated", "per_page": 100})
            data, _ = http_get(f"https://api.github.com/search/repositories?{q}",
                               headers=gh_headers(), timeout=30)
            return json.loads(data).get("items", [])

    def expand(owner):
        out = []
        try:
            repos = list_repos(owner)
        except Exception as e:  # noqa: BLE001
            return owner, None, str(e)
        for r in repos[: c.get("owner_repos_max", 40)]:
            full, br = r["full_name"], r.get("default_branch") or "main"
            try:
                d, _ = http_get(f"https://data.jsdelivr.com/v1/packages/gh/{full}@{br}?structure=flat",
                                timeout=30)
                files = [f["name"] for f in json.loads(d).get("files", [])]
            except Exception:  # noqa: BLE001
                continue
            for f in cdn.entry_files(files, c.get("files_per_repo", 6)):
                out.append(f"https://cdn.jsdelivr.net/gh/{full}@{br}/{f}")
        return owner, (len(repos), out), None

    with cf.ThreadPoolExecutor(6) as ex:
        for owner, res, err in ex.map(expand, due):
            METRICS["cdn_owners_expanded"] += 1
            if res is None:
                log(f"[cdn] expand {owner}: {err}")
                continue
            nrepos, urls = res
            METRICS["cdn_owner_repos_listed"] += nrepos
            METRICS["cdn_owner_entry_files_found"] += len(urls)
            for u in urls:
                cands.add(u, f"owner-expand:{owner}", priority=2)
            owners_state[owner.lower()] = {"last_expanded": date_str(TODAY), "repos": nrepos}
    log(f"[cdn] expanded {len(due)} of {len(known)} known owners")

    # GitHub's code search API needs a user token: the automatic Actions
    # GITHUB_TOKEN gets no results. CODE_SEARCH_TOKEN is a fine-grained,
    # read-only personal access token stored as a repository secret.
    cs_token = os.environ.get("CODE_SEARCH_TOKEN")
    cs_headers = gh_headers()
    if cs_token:
        cs_headers["Authorization"] = f"Bearer {cs_token}"
    elif "Authorization" not in cs_headers:
        log("[cdn] code search skipped (no token)")
        return
    for q in c.get("code_search_queries", []):
        for page in range(1, c.get("code_search_pages", 1) + 1):
            url = "https://api.github.com/search/code?" + urllib.parse.urlencode(
                {"q": q, "per_page": 100, "page": page})
            try:
                data, _ = http_get(url, headers=cs_headers, timeout=60)
                items = json.loads(data).get("items", [])
            except urllib.error.HTTPError as e:
                # 401 = token expired or revoked; 403/422 = token not accepted.
                METRICS["cdn_code_search_errors"] += 1
                log(f"[cdn] code search {q!r}: HTTP {e.code}"
                    + (" - CODE_SEARCH_TOKEN expired or revoked?" if e.code == 401 else ""))
                items = []
            except Exception as e:  # noqa: BLE001
                METRICS["cdn_code_search_errors"] += 1
                log(f"[cdn] code search {q!r}: {e}")
                items = []
            finally:
                time.sleep(7)  # code search: 10 requests/minute
            METRICS["cdn_code_search_requests"] += 1
            METRICS["cdn_code_search_files"] += len(items)
            for it in items:
                full = it.get("repository", {}).get("full_name")
                if full and it.get("path"):
                    cands.add(f"https://cdn.jsdelivr.net/gh/{full}/{it['path']}", "code-search", priority=1)
            log(f"[cdn] code search {q!r} p{page}: {len(items)} files")
            if len(items) < 100:
                break


def discover_urlscan(cfg: dict, cands: Candidates, state: dict) -> None:
    """Search urlscan.io's public scan index for pages that load the proxy
    frameworks' files or carry "unblocked games" titles. Every hit still has
    to pass the live fingerprint (results include phishing kits built on the
    same proxy code, and wildcard-DNS noise)."""
    u = cfg.get("urlscan", {})
    if not u.get("enabled"):
        return
    last = state.get("urlscan_last")
    if last:
        age_h = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(last)).total_seconds() / 3600
        if age_h < u.get("interval_hours", 6):
            log(f"[urlscan] skipped (last run {age_h:.1f}h ago)")
            return
    skip = Matcher(["*." + d for d in u.get("skip_domains", [])])
    headers = {"Accept": "application/json"}
    if key := os.environ.get("URLSCAN_API_KEY"):
        headers["API-Key"] = key
    per_apex: collections.Counter = collections.Counter()
    max_apex = u.get("max_per_domain", 3)
    for q in u.get("queries", []):
        full = f"{q} AND date:>now-{u.get('days', 3)}d"
        url = "https://urlscan.io/api/v1/search/?" + urllib.parse.urlencode({"q": full, "size": 100})
        try:
            data, _ = http_get(url, headers=headers, timeout=60)
            results = json.loads(data).get("results", [])
        except urllib.error.HTTPError as e:
            log(f"[urlscan] {q!r}: HTTP {e.code}")
            if e.code == 429:
                break
            continue
        except Exception as e:  # noqa: BLE001
            log(f"[urlscan] {q!r}: {e}")
            continue
        finally:
            time.sleep(2)
        METRICS["urlscan_queries"] += 1
        METRICS["urlscan_results"] += len(results)
        n = 0
        for r in results:
            page = r.get("page", {})
            dom = normalize_host(page.get("domain", "") or "")
            labels = dom.split(".") if dom else []
            generated = (len(labels) > 6 or any(a == b for a, b in zip(labels, labels[1:])))
            phishy = any(w in dom for w in u.get("skip_keywords", []))
            if not dom or skip.matches(dom) or generated or phishy:
                METRICS["urlscan_skipped_noise"] += 1
                continue
            apex = dom if platform_apex(dom, cands.platforms) else registrable(dom)
            if per_apex[apex] >= max_apex:
                continue
            per_apex[apex] += 1
            cands.add(page.get("url") or f"https://{dom}/", f"urlscan:{q[:40]}", priority=2)
            n += 1
        log(f"[urlscan] {q!r}: {len(results)} results, {n} candidates")
    state["urlscan_last"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def requeue_harvested(cands: Candidates, state: dict) -> None:
    """Script URLs collected from confirmed game/proxy pages on the previous
    run (engine files on CDN mirrors). Known mirrors become CDN candidates;
    CDN-shaped links on unknown hosts feed new-mirror detection."""
    links = state.pop("harvested_links", [])
    for u, src in links:
        cands.add(u, src, priority=2)
    METRICS["harvested_links_requeued"] += len(links)


def _mirror_reference(style: str, path: str) -> str | None:
    """The same path on the reference host for a mirror style."""
    ref = {"jsdelivr": "cdn.jsdelivr.net", "statically": "cdn.statically.io",
           "esm": "esm.sh", "unpkg": "unpkg.com", "githack": "raw.githack.com"}.get(style)
    return f"https://{ref}/{path}" if ref else None


def _same_content(a: str, b: str) -> bool:
    try:
        da, _ = http_get(a, timeout=20, max_bytes=3_000_000)
        db, _ = http_get(b, timeout=20, max_bytes=3_000_000)
    except Exception:  # noqa: BLE001
        return False
    return len(da) > 200 and hashlib.sha256(da).digest() == hashlib.sha256(db).digest()


def detect_new_cdns(cfg: dict, cands: Candidates, state: dict) -> None:
    """Spot GitHub/npm file CDNs (or mirrors of one) we don't know yet.

    A host qualifies when its links have a CDN path shape AND they reference
    >= 2 different owners/packages or an owner we've already confirmed; it is
    confirmed when a sampled link serves a loader/game/proxy. Confirmed hosts
    are registered as mirrors immediately (so entries are written for them),
    recorded in review/new-cdns.txt, and optionally reported as a GitHub issue.
    """
    c = cfg.get("cdn", {})
    det = state.setdefault("cdn_detected", {})
    known_owners = {e["owner"].lower() for e in state.get("entries", {}).values()
                    if e["kind"] == "cdn" and e["status"] == "confirmed"}
    known_owners |= {o for o, r in state.get("engine_owners", {}).items()
                     if r.get("status") == "confirmed"}
    for host, links in sorted(cands.cdn_shapes.items()):
        METRICS["cdn_shape_hosts"] += 1
        refs = []
        for url, style, source in links:
            path = urllib.parse.unquote(urllib.parse.urlsplit(url).path).lstrip("/")
            r = cdn.parse_path(style, path)
            if r:
                refs.append((url, style, source, r))
        owners = {r.owner.lower() for *_, r in refs}
        overlap = owners & known_owners
        style = collections.Counter(st for _, st, _, _ in refs).most_common(1)[0][0] if refs else links[0][1]
        rec = det.setdefault(host, {"first_seen": date_str(TODAY), "status": "watch"})
        rec.update(last_seen=date_str(TODAY), style=style, links=len(links),
                   owners=len(owners), known_owner_overlap=len(overlap),
                   sample=links[0][0][:200])
        if rec["status"] == "confirmed":
            continue
        if len(owners) < 2 and not overlap:
            continue  # stays "watch": too little evidence to test
        if days_since(rec.get("last_checked")) < 1:
            continue
        # Live-check up to 3 samples, known owners first.
        samples = sorted(refs, key=lambda x: x[3].owner.lower() not in overlap)[:3]
        rec["last_checked"] = date_str(TODAY)
        rec["status"] = "suspect"
        for url, st, _src, _r in samples:
            # Strongest proof: the host serves byte-identical files to the
            # reference CDN for the same path, i.e. it is a mirror.
            path = urllib.parse.urlsplit(url).path.lstrip("/")
            ref = _mirror_reference(st, path)
            if ref and _same_content(url, ref):
                METRICS["cdn_detect_checks"] += 1
                rec.update(status="confirmed", confirmed=date_str(TODAY),
                           evidence=f"{url[:160]} is byte-identical to {ref[:120]}")
                break
        for url, *_ in (samples if rec["status"] != "confirmed" else []):
            METRICS["cdn_detect_checks"] += 1
            res = classify(url, timeout=15, ua=UA, cdn=True)
            if res.verdict in ("loader", "game", "proxy"):
                rec.update(status="confirmed", confirmed=date_str(TODAY),
                           evidence=f"{url[:160]} -> {res.verdict}: {res.evidence[-120:]}")
                break
            rec["evidence"] = f"{url[:160]} -> {res.verdict}"
        if rec["status"] == "confirmed":
            METRICS["cdn_detect_confirmed"] += 1
            cdn.register(host, style)
            log(f"[cdn] NEW CDN/mirror detected: {host} ({style}), {len(owners)} owners")
            for url, _, source in links:      # now parseable as CDN links
                cands.add(url, source, priority=2)
            if c.get("open_issues", True):
                open_issue_for_cdn(host, rec)


def open_issue_for_cdn(host: str, rec: dict) -> None:
    """Open a GitHub issue for a newly detected CDN (Actions only, once)."""
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo or not tok or rec.get("issue"):
        return
    body = (f"The collector detected a new GitHub/npm file CDN or mirror serving loaders:\n\n"
            f"* **Host:** `{host}`\n* **URL style:** `{rec['style']}`\n"
            f"* **Links seen:** {rec['links']} across {rec['owners']} owners/packages "
            f"({rec['known_owner_overlap']} already confirmed)\n"
            f"* **Evidence:** `{rec.get('evidence', '')}`\n\n"
            "It is already active: owner/repo/package entries in `fortigate/urls.txt` now "
            "include this host.\n\n**To do**\n"
            f"- [ ] Add `{host}` to the Chrome URL blocklist for student OUs (Google Admin)\n"
            f"- [ ] Make it permanent: add `{host} {rec['style']}` to `seeds/cdn-mirrors.txt` "
            f"(or `{host} ignore` if this is a false positive)\n\n"
            "_Opened automatically by the feed collector._")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues", method="POST",
        data=json.dumps({"title": f"New CDN mirror detected: {host}", "body": body,
                         "labels": ["new-cdn"]}).encode(),
        headers={**gh_headers(), "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rec["issue"] = json.loads(r.read()).get("html_url", "opened")
            METRICS["cdn_issues_opened"] += 1
    except Exception as e:  # noqa: BLE001
        log(f"[cdn] could not open issue for {host}: {e}")


# ------------------------------------------------------ shadowing & engines

SHADOW_TARGETS = ("pages.dev", "vercel.app", "github.io", "netlify.app", "b-cdn.net",
                  "azurewebsites.net", "cloudfront.net", "herokuapp.com", "onrender.com",
                  "fly.dev", "amazonaws.com", "elasticbeanstalk.com", "firebaseapp.com",
                  "web.app", "workers.dev", "surge.sh", "glitch.me", "replit.app")
ENGINE_HINT = re.compile(r"ubg|unbl|proxy|game|arcade|gn-?math|selenite|eagler|scram|\buv\b|"
                         r"achroma|nebula|interstellar|doge|shadow|void|lunar|astro", re.I)


def _resolve(h: str):
    try:
        canon, _aliases, ips = socket.gethostbyname_ex(h)
        return canon.lower().rstrip("."), set(ips)
    except Exception:  # noqa: BLE001
        return None, set()


def shadow_signals(host: str, platforms: set[str]) -> list[str]:
    """Signs a subdomain of an unrelated domain was hijacked or shadowed:
    a CNAME onto free hosting, the CNAME-name trick used by shadowing kits
    (target label = hostname with dots as hyphens), or the subdomain pointing
    at different servers than its parent domain."""
    if platform_apex(host, platforms) or is_registrable(host):
        return []
    canon, ips = _resolve(host)
    sig = []
    if canon and canon != host:
        if any(canon == t or canon.endswith("." + t) for t in SHADOW_TARGETS):
            sig.append(f"cname->{canon}")
        if canon.split(".")[0] == host.replace(".", "-"):
            sig.append("cname-name-is-hostname")
    apex = registrable(host)
    if ips and apex != host and not host.startswith("www."):
        _c, apex_ips = _resolve(apex)
        if apex_ips and not (ips & apex_ips):
            sig.append("different-servers-than-parent")
    return sig


def learn_from_scripts(page: str, scripts: list, state: dict, owner_allow: set[str]) -> None:
    """From a confirmed game/proxy page's script URLs: (1) GitHub owners whose
    code it loads from CDN mirrors (its engine), and (2) every CDN-shaped
    script URL, re-queued next run so unknown mirrors get detected."""
    harvested = state.setdefault("harvested_links", [])
    by_owner: dict[str, set] = {}
    for u in scripts:
        host = (urllib.parse.urlsplit(u).hostname or "").lower()
        ref = cdn.parse(u)
        if ref and ref.kind == "gh":
            by_owner.setdefault(ref.owner, set()).add(host)
        elif host not in cdn.CDN_HOSTS and cdn.infer_style(urllib.parse.urlsplit(u).path):
            if len(harvested) < 3000 and [u, f"page-script:{page}"] not in harvested:
                harvested.append([u, f"page-script:{page}"])
    eng = state.setdefault("engine_owners", {})
    for owner, hosts in by_owner.items():
        if owner.lower() in owner_allow:
            continue
        r = eng.setdefault(owner.lower(), {"name": owner, "sites": [], "max_mirrors": 0,
                                           "first_seen": date_str(TODAY), "status": "watch"})
        if page not in r["sites"]:
            r["sites"] = (r["sites"] + [page])[-20:]
        r["max_mirrors"] = max(r["max_mirrors"], len(hosts))
        r["last_seen"] = date_str(TODAY)
        # Legit sites never load one library through a chain of 3+ mirrors;
        # a fallback chain is how bypass sites survive CDN blocks.
        if r["status"] != "confirmed" and (
                r["max_mirrors"] >= 3 or (len(r["sites"]) >= 2 and ENGINE_HINT.search(owner))):
            r["status"] = "confirmed"
            r["evidence"] = (f"loaded via {r['max_mirrors']} CDN mirrors"
                             if r["max_mirrors"] >= 3 else f"loaded by {len(r['sites'])} confirmed sites")
            METRICS["engine_owners_confirmed"] += 1
            log(f"[engine] {owner}: {r['evidence']} (first on {page})")


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
            e = entries[key]
        else:
            e["last_seen"] = date_str(TODAY)
        for f in ("cdn_kind", "owner", "repo"):
            if f in c:
                e[f] = c[f]
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
    # CDN files are cheap single fetches; give them their own budget so a big
    # host backlog can't starve them.
    cdn_todo = [kv for kv in todo if kv[1]["kind"] == "cdn"][: settings.get("verify_max_cdn", 1500)]
    todo = [kv for kv in todo if kv[1]["kind"] != "cdn"][: settings.get("verify_max_hosts", 400)] + cdn_todo
    log(f"[verify] checking {len(todo)} of {len(entries)} tracked entries")
    timeout = settings.get("verify_timeout", 10)

    platforms = cands.platforms
    top = settings.get("popular_guard_top", 10000)

    def check(kv):
        k, e = kv
        res = classify(e["check_url"], timeout=timeout, ua=UA, cdn=e["kind"] == "cdn")
        root = None
        # Homepage guard for established sites (ranked, but below the top
        # tier): a game page deep inside (example.com/games/x) only blocks the
        # whole host if the homepage is a game/proxy site too. Unranked
        # domains skip this on purpose: disguised bypass sites hide their
        # games behind a decoy homepage.
        pr = popular_rank(k, platforms) if e["kind"] == "host" else None
        if (pr and pr[1] > top and res.verdict in ("game", "proxy", "loader")
                and urllib.parse.urlsplit(e["check_url"]).path not in ("", "/")):
            root = classify(f"https://{k}/", timeout=timeout, ua=UA)
        res.shadow = shadow_signals(k, platforms) if (e["kind"] == "host" and res.verdict != "dead") else []
        return k, res, root

    def hold(e, reason, metric):
        METRICS[metric] += 1
        e.update(status="pending", needs_review=True, hold=reason,
                 evidence=(f"HELD: {reason} | " + e.get("evidence", "").split(" | ")[-1])[:300])

    def too_popular(k):
        pr = popular_rank(k, platforms)
        return pr if pr and pr[1] <= top else None

    # CDN mirror hosts are handled per file, never as whole hosts.
    for k, e in entries.items():
        if e["kind"] == "host" and k in cdn.CDN_HOSTS and e["status"] != "dismissed":
            e.update(status="dismissed", needs_review=False, resolution="CDN mirror host")
            e.pop("hold", None)

    # Top-tier guard, applied retroactively to anything already confirmed.
    for k, e in entries.items():
        if e["kind"] == "host" and e["status"] == "confirmed" and (pr := too_popular(k)):
            hold(e, f"{pr[0]} is a top-{top} site (Tranco #{pr[1]}); confirm manually",
                 "discovery_held_popular")

    redirected: list[tuple[str, str, str]] = []
    with cf.ThreadPoolExecutor(settings.get("verify_workers", 32)) as ex:
        for k, res, root in ex.map(check, todo):
            e = entries[k]
            e["last_checked"] = date_str(TODAY)
            e["attempts"] = e.get("attempts", 0) + 1
            e["evidence"] = res.evidence[:200]
            e["last_verdict"] = res.verdict
            if getattr(res, "page_hash", ""):
                e["page_hash"] = res.page_hash
            if getattr(res, "title", ""):
                e["title"] = res.title[:120]
            if getattr(res, "sw", False):
                e["sw"] = True
            METRICS[f"verify_{e['kind']}_{res.verdict}"] += 1
            if getattr(res, "shadow", None):
                e["shadow"] = res.shadow
                METRICS["shadow_signals_found"] += 1
            if res.verdict in ("game", "proxy", "loader") and getattr(res, "scripts", None):
                learn_from_scripts(k, res.scripts, state, cands.cdn_owner_allow)
            # Alive, no fingerprint, but a student list / scan index points at
            # it and DNS looks shadowed: a person should look (masked proxies
            # often show nothing until a device is authorized).
            strong = [x for x in (getattr(res, "shadow", None) or []) if x.startswith("cname")]
            if (res.verdict == "alive" and e["kind"] == "host" and strong
                    and e["source"].startswith(("aggregator:", "urlscan:")) and e["status"] != "confirmed"):
                hold(e, "possible domain shadowing (" + ", ".join(strong) + "), no fingerprint yet",
                     "discovery_held_shadowing")
                continue
            # A Google Sites / Apps Script page listed by a student link list is
            # a bypass by definition; their content rarely fingerprints.
            if (res.verdict == "alive" and e["kind"] == "url"
                    and e["source"].startswith("aggregator:")):
                res.verdict = "listed"
            if res.verdict in ("game", "proxy", "loader") and e["kind"] == "host":
                if pr := too_popular(k):
                    hold(e, f"{pr[0]} is a top-{top} site (Tranco #{pr[1]}); confirm manually",
                         "discovery_held_popular")
                    continue
                if root is not None and root.verdict not in ("game", "proxy", "loader", "dead"):
                    hold(e, "established site: game content only at a sub-page, homepage "
                            "is not a game site", "discovery_held_homepage")
                    continue
            if res.verdict in ("game", "proxy", "loader", "listed"):
                e.update(status="confirmed", category=res.verdict,
                         last_alive=date_str(TODAY), attempts=0)
                e.pop("hold", None)
                if e["kind"] == "host":
                    redirected.append((res.final_url, k, res.verdict))
            elif res.verdict == "dead":
                if e["status"] != "confirmed":
                    e["status"] = "rejected" if e["attempts"] >= 3 else "pending"
            else:  # alive but no fingerprint
                if e["status"] == "confirmed" and e.get("category") in ("clone", "impersonation", "listed"):
                    e["last_alive"] = date_str(TODAY)  # confirmed by page identity, not markup
                elif e["status"] == "confirmed":
                    e["last_alive"] = date_str(TODAY)  # keep; flag for review
                    e["needs_review"] = True
                else:
                    e["status"] = "rejected" if e["attempts"] >= 3 else "pending"


    # A confirmed site that redirected elsewhere: the landing host is a game
    # site too (often a custom domain behind a github.io/pages.dev mirror).
    for final, origin, verdict in redirected:
        tmp = Candidates(cands.allow, cands.platforms, cands.url_platforms, cands.cdn_owner_allow)
        tmp.add(final, f"redirect:{origin}", priority=2)
        for key, c in tmp.items.items():
            if c["kind"] == "host" and too_popular(key):
                METRICS["discovery_held_popular"] += 1
                continue
            if key not in entries or entries[key]["status"] != "confirmed":
                entries[key] = {"kind": c["kind"], "check_url": final, "source": c["source"],
                                "first_seen": date_str(TODAY), "last_seen": date_str(TODAY),
                                "status": "confirmed", "category": verdict, "attempts": 0,
                                "last_checked": date_str(TODAY), "last_alive": date_str(TODAY),
                                "priority": 2, "evidence": f"redirect target of {origin}"}


def resolve_stalled(cfg: dict, state: dict, platforms: set[str]) -> None:
    """Decide stalled sites (alive, no fingerprint) that came from dedicated
    student bypass lists, using evidence other than page markup:
      1. clone: byte-identical (whitespace-normalized) to a confirmed bypass
         page, or the same page served by >= min_cluster hosts from those lists
      2. impersonation: title names a known service (Coursera, IXL, NASA...)
         but the site is a subdomain of an unrelated domain
      3. otherwise, if there is a second signal (shadowing CNAME, a service
         worker, a cloaked title), hold it for review
    Only subdomains of unranked domains (or free-hosting subdomains) qualify;
    whole domains and popular sites are never blocked by these rules."""
    c = cfg.get("stalled", {})
    if not c.get("enabled", True):
        return
    entries = state.get("entries", {})
    trusted = tuple(c.get("trusted_sources", []))
    min_cluster = c.get("min_cluster", 3)
    services = {k.lower(): v for k, v in c.get("impersonated_services", {}).items()}
    svc_re = re.compile(r"\b(" + "|".join(re.escape(k) for k in services) + r")\b", re.I) if services else None

    def eligible(k, e):
        return (e["kind"] == "host" and e["source"].startswith(trusted)
                and (platform_apex(k, platforms) or not is_registrable(k))
                and popular_rank(k, platforms) is None)

    def stalled(e):
        return (e["status"] in ("pending", "rejected", "new") and not e.get("hold")
                and e.get("last_verdict") == "alive")

    confirmed_hashes = {e["page_hash"] for e in entries.values()
                        if e["kind"] == "host" and e["status"] == "confirmed" and e.get("page_hash")
                        and e.get("category") in ("game", "proxy", "loader")}
    clusters: dict[str, set] = {}
    for k, e in entries.items():
        if e.get("page_hash") and eligible(k, e) and (stalled(e) or e["status"] == "confirmed"):
            clusters.setdefault(e["page_hash"], set()).add(k)

    def confirm(k, e, category, why, metric):
        METRICS[metric] += 1
        e.update(status="confirmed", category=category, last_alive=date_str(TODAY),
                 attempts=0, evidence=(f"{why} | " + e.get("evidence", ""))[:300])
        e.pop("hold", None)

    spam = re.compile(r"casino|kazino|казино|\bbet\b|betting|slot|gacor|toto|poker|"
                      r"gambl|porn|xxx|sex|escort|viagra|loan", re.I)
    for k, e in entries.items():
        if not (stalled(e) and eligible(k, e)):
            continue
        h, title = e.get("page_hash", ""), e.get("title", "")
        if spam.search(title):
            continue  # SEO spam on hijacked subdomains: not this feed's scope
        if h and h in confirmed_hashes:
            confirm(k, e, "clone", "clone of a confirmed bypass page", "stalled_confirmed_clone")
        elif h and len(clusters.get(h, ())) >= min_cluster:
            confirm(k, e, "clone", f"same page served by {len(clusters[h])} hosts from student "
                                   "bypass lists", "stalled_confirmed_clone")
        elif svc_re and (m := svc_re.search(title)):
            owners = services[m.group(1).lower()]
            if not any(k == o or k.endswith("." + o) for o in owners):
                confirm(k, e, "impersonation", f"title impersonates {m.group(1)} on an unrelated "
                                               "domain", "stalled_confirmed_impersonation")
        else:
            second = [s for s in (e.get("shadow") or []) if s.startswith("cname")]
            if e.get("sw"):
                second.append("registers a service worker")
            if second:
                METRICS["stalled_held_second_signal"] += 1
                e.update(status="pending", needs_review=True,
                         hold="stalled bypass-list site with " + ", ".join(second))


def age_out(state: dict, settings: dict) -> None:
    entries = state.get("entries", {})
    max_age = settings.get("discovered_max_age_days", 60)
    for k in list(entries):
        e = entries[k]
        if e["status"] == "confirmed" and days_since(e.get("last_alive")) > max_age:
            del entries[k]
        elif (e["status"] in ("rejected", "pending", "new", "dismissed")
              and days_since(e["last_seen"]) > 90):
            del entries[k]


# ------------------------------------------------------------------ output

_2LD = {"co.uk", "org.uk", "ac.uk", "com.au", "net.au", "org.au", "co.nz", "com.br",
        "co.jp", "co.in", "com.mx", "co.za", "com.tr", "it.com", "us.com", "uk.com",
        "eu.com", "com.de", "co.com", "in.net", "br.com", "cn.com", "jp.net"}


def registrable(host: str) -> str:
    """Approximate registrable domain (eTLD+1) without a public-suffix list."""
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in _2LD:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def is_registrable(host: str) -> bool:
    labels = host.split(".")
    if len(labels) == 2:
        return True
    return len(labels) == 3 and ".".join(labels[1:]) in _2LD


def build_domain_lines(hosts: set[str], allow: Matcher, platforms: set[str],
                       wildcards: bool) -> list[str]:
    clean = set()
    for h in hosts:
        if allow.matches(h) or h in platforms or NOISE.matches(h) or h in cdn.CDN_HOSTS:
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


def build_cdn_lines(entries: dict, settings: dict, state: dict | None = None,
                    owner_allow: set[str] | None = None) -> tuple[set[str], dict]:
    """Owner-level entries once an owner has >= owner_promote_min confirmed
    loader repos; repo-level entries otherwise; npm package-level entries."""
    style = settings.get("url_entry_style", "prefix")
    promote = settings.get("owner_promote_min", 2)
    gh: dict[str, dict] = {}
    npm: set[str] = set()
    for e in entries.values():
        if e["kind"] != "cdn" or e["status"] != "confirmed":
            continue
        if e.get("cdn_kind") == "gh":
            o = gh.setdefault(e["owner"].lower(), {"name": e["owner"], "repos": set()})
            o["repos"].add(e["repo"])
        else:
            npm.add(e["owner"])
    lines: set[str] = set()
    owner_level = repo_level = 0
    for o in gh.values():
        if len({r.lower() for r in o["repos"]}) >= promote:
            lines.update(cdn.entry_lines("gh", o["name"], style=style))
            owner_level += 1
        else:
            for r in o["repos"]:
                lines.update(cdn.entry_lines("gh", o["name"], r, style=style))
                repo_level += 1
    for pkg in npm:
        lines.update(cdn.entry_lines("npm", pkg, style=style))
    # Owner-level blocks from seeds/cdn-owners-block.txt ("gh <owner>" or
    # "npm <package>") and from engine owners learned from confirmed pages.
    extra: set[tuple[str, str]] = set()
    for line in read_list(ROOT / "seeds" / "cdn-owners-block.txt"):
        parts = line.split()
        if len(parts) == 2 and parts[0] in ("gh", "npm"):
            extra.add((parts[0], parts[1]))
    engines = 0
    for o, r in (state or {}).get("engine_owners", {}).items():
        if r.get("status") == "confirmed" and o not in (owner_allow or set()):
            extra.add(("gh", r["name"]))
            engines += 1
    for kind, name in extra:
        if name.lower() in (owner_allow or set()):
            continue
        lines.update(cdn.entry_lines(kind, name, style=style))
    return lines, {"gh_owners_owner_level": owner_level, "gh_repos_repo_level": repo_level,
                   "npm_packages": len(npm), "engine_owners": engines,
                   "seeded_owner_blocks": len(extra) - engines, "url_lines": len(lines)}


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
    url_platforms: dict[str, re.Pattern] = {}
    for line in (ROOT / "seeds" / "url-platforms.txt").read_text().splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and not parts[0].startswith("#"):
            url_platforms[parts[0].lower()] = re.compile(parts[1].strip(), re.I)
    cdn_owner_allow = set(read_list(ROOT / "seeds" / "cdn-owner-allow.txt"))
    # Held items a reviewer decided not to block (not game sites, or already
    # covered by a curated list). Exact entry keys, as shown in review/held.txt.
    dismissed = set(read_list(ROOT / "seeds" / "review-dismissed.txt"))

    state_path = ROOT / "data" / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    # Extra CDN mirrors: seeds/cdn-mirrors.txt, then previously auto-detected.
    cdn_ignore = set()
    for line in read_list(ROOT / "seeds" / "cdn-mirrors.txt"):
        parts = line.split()
        if len(parts) == 2:
            if parts[1] == "ignore":
                cdn_ignore.add(parts[0])
            else:
                cdn.register(parts[0], parts[1])
    for host, rec in state.get("cdn_detected", {}).items():
        if rec.get("status") == "confirmed" and host not in cdn_ignore:
            cdn.register(host, rec["style"])

    lists = fetch_lists(cfg)

    cands = Candidates(allow, platforms, url_platforms, cdn_owner_allow)
    cands.cdn_ignore = cdn_ignore
    # New signatures: re-check discovered sites the collector had given up on.
    if state.get("fp_version") != FINGERPRINT_VERSION:
        for e in state.get("entries", {}).values():
            if e["status"] in ("pending", "rejected") and not e.get("hold"):
                e.update(status="new", attempts=0)
                METRICS["requeued_for_new_fingerprints"] += 1
        state["fp_version"] = FINGERPRINT_VERSION
    if not args.no_discovery:
        requeue_harvested(cands, state)
        discover_github(cfg, cands, state)
        discover_aggregators(cfg, cands)
        discover_urlscan(cfg, cands, state)
        if not args.no_ct:
            discover_ct(cfg, cands)
        discover_cdn(cfg, cands, state)
        detect_new_cdns(cfg, cands, state)
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

    # A held item is resolved once a reviewer blocks it (seeds/confirmed.txt),
    # allows it (seeds/allow.txt) or dismisses it: stop re-checking it.
    decided_block = {h for h in (normalize_host(x) for x in read_list(ROOT / "seeds" / "confirmed.txt")) if h}
    for k, e in state.get("entries", {}).items():
        if e.get("hold") and e["status"] == "pending" and (k in decided_block or allow.matches(k)):
            e.update(status="dismissed", needs_review=False,
                     resolution="blocked by reviewer" if k in decided_block else "allowlisted")
            e.pop("hold", None)
            METRICS["review_resolved_applied"] += 1
    for k, e in state.get("entries", {}).items():
        if k.lower() in dismissed and e["status"] != "dismissed":
            e.update(status="dismissed", needs_review=False)
            e.pop("hold", None)
            METRICS["review_dismissed_applied"] += 1
    load_popular(settings, state)
    verify(cands, state, settings, not args.no_verify)
    resolve_stalled(cfg, state, platforms)
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
    cdn_lines, cdn_stats = build_cdn_lines(entries, settings, state, cdn_owner_allow)
    url_lines |= cdn_lines
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
    held = sorted((k, e) for k, e in entries.items()
                  if (e["status"] == "pending" and e.get("hold"))
                  or (e["status"] == "confirmed" and e.get("needs_review")))
    pend = sorted((k, e) for k, e in entries.items()
                  if e["status"] == "pending" and not e.get("hold"))
    hl = ["# NEEDS A HUMAN DECISION. Sites the collector found and fingerprinted as",
          "# games/proxies, but did not block automatically (popular or established",
          "# site), plus blocked sites whose game fingerprint has disappeared.",
          "# For each entry, do one of:",
          "#   block    -> add the entry (hostname) to seeds/confirmed.txt",
          "#   dismiss  -> add the entry, exactly as shown, to seeds/review-dismissed.txt",
          "#               (not a game site, or already covered by a curated list)",
          "#   allow    -> add it to seeds/allow.txt (a service students need; this also",
          "#               keeps curated lists from ever blocking it)",
          "# entry\theld_since\treason\tcheck_url\tevidence"]
    for k, e in held:
        reason = e.get("hold") or "blocked, but the game fingerprint no longer matches"
        ev = e.get("evidence", "").split(" | ", 1)[-1]
        hl.append("\t".join([k, e["first_seen"], reason, e["check_url"], ev]))
    (rev / "held.txt").write_text("\n".join(hl) + "\n")
    lines = ["# Automatic retry queue (no action needed). Discovered entries that are",
             "# alive but don't match a game/proxy fingerprint yet, or were unreachable.",
             "# Each is re-checked daily; after 3 failed checks it is rejected and dropped.",
             "# Items that need a person are in review/held.txt.",
             "# entry\tstatus\tfirst_seen\tsource\tcheck_url\tevidence"]
    for k, e in pend:
        lines.append("\t".join([k, e["status"], e["first_seen"], e["source"],
                                e["check_url"], e.get("evidence", "")]))
    (rev / "pending.txt").write_text("\n".join(lines) + "\n")
    det = state.get("cdn_detected", {})
    nl = ["# Hosts whose links look like a GitHub/npm file CDN (automatic detection).",
          "# confirmed = serving loaders; already active as a mirror in urls.txt.",
          "#   Make permanent in seeds/cdn-mirrors.txt; add to the Chrome URL blocklist.",
          "# suspect   = CDN-shaped links to several owners, but no loader confirmed yet.",
          "# watch     = CDN-shaped links seen, too few owners to test yet.",
          "# host\tstatus\tstyle\tfirst_seen\tlinks\towners\tknown_owners\tissue\tevidence"]
    order = {"confirmed": 0, "suspect": 1, "watch": 2}
    for h, r in sorted(det.items(), key=lambda kv: (order.get(kv[1]["status"], 9), kv[0])):
        nl.append("\t".join(str(x) for x in [h, r["status"], r.get("style", ""), r["first_seen"],
                  r.get("links", 0), r.get("owners", 0), r.get("known_owner_overlap", 0),
                  r.get("issue", ""), r.get("evidence", r.get("sample", ""))]))
    (rev / "new-cdns.txt").write_text("\n".join(nl) + "\n")
    # Domain shadowing / subdomain takeover view.
    sl = ["# Domain shadowing and subdomain takeover signals (informational).",
          "# Blocked or held sites on subdomains of unrelated domains whose DNS looks",
          "# hijacked, and parent domains with several such subdomains (bursts).",
          "# Consider notifying the domain's owner; held ones are in review/held.txt.",
          "# host\tstatus\tsignals\tsource"]
    burst: dict[str, set] = {}
    for k, e in sorted(entries.items()):
        if e["kind"] != "host" or e["status"] not in ("confirmed", "pending"):
            continue
        if e.get("shadow"):
            sl.append("\t".join([k, e["status"], ",".join(e["shadow"]), e["source"][:60]]))
        if (not platform_apex(k, platforms) and not is_registrable(k)
                and days_since(e.get("first_seen")) <= 14):
            burst.setdefault(registrable(k), set()).add(k)
    sl += ["", "# Parent domains with 3+ discovered subdomains in the last 14 days:",
           "# parent\tsubdomains\texamples"]
    for apex, subs in sorted(burst.items(), key=lambda kv: -len(kv[1])):
        if len(subs) >= 3 and any(entries[x]["status"] == "confirmed" for x in subs):
            sl.append("\t".join([apex, str(len(subs)), " ".join(sorted(subs)[:5])]))
    (rev / "shadowing.txt").write_text("\n".join(sl) + "\n")

    stats = {
        "domains_txt_entries": len(all_lines),
        "domains_priority_entries": len(pri_lines),
        "urls_entries": len(url_lines),
        "lists": {n: len(h) for n, (_, h, _) in lists.items()},
        "discovered_confirmed": len(disc_hosts) + len(disc_urls) + sum(
            1 for e in entries.values() if e["kind"] == "cdn" and e["status"] == "confirmed"),
        "cdn": cdn_stats,
        "discovered_pending": sum(1 for e in entries.values() if e["status"] == "pending"),
        "review_held": len(held),
        "discovered_rejected": sum(1 for e in entries.values() if e["status"] == "rejected"),
        "files": f1 + f2 + f3,
    }
    state["last_run"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for name, (_, h, _) in lists.items():
        METRICS["list_entries_parsed"] += len(h)
    METRICS["lists_fetched"] = len(lists)
    stats["checks"] = dict(sorted(METRICS.items()))
    state["stats"] = stats
    write_run_report(stats, entries)
    state_path.parent.mkdir(exist_ok=True)
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    log(json.dumps(stats, indent=2))
    if summ := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summ, "a") as f:
            f.write("## Feed stats\n```json\n" + json.dumps(stats, indent=2) + "\n```\n")
    return 0


def write_run_report(stats: dict, entries: dict) -> None:
    """docs/latest-run.md: what the last run checked, in plain numbers."""
    m = stats["checks"]
    by = collections.Counter((e["kind"], e["status"]) for e in entries.values())
    g = lambda k: m.get(k, 0)  # noqa: E731
    verified = sum(v for k, v in m.items() if k.startswith("verify_"))
    rows = [
        ("Curated lists downloaded", g("lists_fetched")),
        ("List entries parsed and normalized", g("list_entries_parsed")),
        ("GitHub repository searches", g("github_search_requests")),
        ("GitHub repositories examined", g("github_repos_unique")),
        ("README files scanned for links", g("github_readmes_scanned")),
        ("Student link-list pages scanned", g("aggregator_pages_fetched")),
        ("Links harvested from link lists", g("aggregator_links_harvested")),
        ("Certificate Transparency queries", g("ct_queries")),
        ("Certificates examined", g("ct_certificates_examined")),
        ("  certificate-log source unreachable this run (skipped)", g("ct_unreachable")),
        ("CDN owners expanded (repo listings)", g("cdn_owners_expanded")),
        ("CDN owner repositories listed", g("cdn_owner_repos_listed")),
        ("CDN entry files found in owner repos", g("cdn_owner_entry_files_found")),
        ("GitHub code searches for loader files", g("cdn_code_search_requests")),
        ("Loader-candidate files from code search", g("cdn_code_search_files")),
        ("  code searches that failed (check CODE_SEARCH_TOKEN)", g("cdn_code_search_errors")),
        ("Links examined by the filters", g("links_examined")),
        ("  dropped: allowlist", g("links_dropped_allowlist")),
        ("  dropped: known non-game service", g("links_dropped_noise")),
        ("  dropped: bare hosting-platform domain", g("links_dropped_platform_apex")),
        ("  dropped: README link with no game/bypass hint", g("links_dropped_no_hint")),
        ("  dropped: CDN file that isn't a page (js/css/img)", g("cdn_links_not_entry_file")),
        ("  dropped: CDN owner on allowlist", g("cdn_links_allowlisted_owner")),
        ("  dropped: CDN file in a test/fixture folder", g("cdn_links_test_fixture")),
        ("urlscan.io searches (proxy framework files, page titles)", g("urlscan_queries")),
        ("  urlscan.io results examined", g("urlscan_results")),
        ("  skipped as wildcard-DNS noise", g("urlscan_skipped_noise")),
        ("Repositories listed from watched GitHub orgs", g("github_org_repos_listed")),
        ("Script URLs from confirmed pages re-queued for mirror detection", g("harvested_links_requeued")),
        ("Game engines (GitHub owners) newly confirmed from page scripts", g("engine_owners_confirmed")),
        ("Sites with domain-shadowing DNS signals", g("shadow_signals_found")),
        ("Sites re-queued after a fingerprint upgrade", g("requeued_for_new_fingerprints")),
        ("Links with a CDN path shape on unknown hosts", g("cdn_shape_links")),
        ("Unknown hosts tested for being a new CDN/mirror", g("cdn_shape_hosts")),
        ("  live checks on those hosts", g("cdn_detect_checks")),
        ("  new CDNs/mirrors confirmed this run", g("cdn_detect_confirmed")),
        ("Discovered sites held for review: top-ranked domain", g("discovery_held_popular")),
        ("Discovered sites held for review: established site, only a sub-page is a game", g("discovery_held_homepage")),
        ("Discovered sites held for review: possible domain shadowing", g("discovery_held_shadowing")),
        ("Stalled bypass-list sites blocked as clones of known bypass pages", g("stalled_confirmed_clone")),
        ("Stalled bypass-list sites blocked for impersonating a known service", g("stalled_confirmed_impersonation")),
        ("Stalled bypass-list sites held for review (second signal)", g("stalled_held_second_signal")),
        ("Live checks performed this run", verified),
    ]
    lines = ["# Latest collector run", "",
             f"Run: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
             "Generated automatically by `collector/collect.py`. "
             "See [how-it-works.md](how-it-works.md) for what each check does.", "",
             "## Checks performed", "", "| Check | Count |", "|---|---:|"]
    lines += [f"| {k} | {v:,} |" for k, v in rows]
    lines += ["", "## Live check results", "", "| Entry type | Result | Count |", "|---|---|---:|"]
    for k in sorted(x for x in m if x.startswith("verify_")):
        _, kind, verdict = k.split("_", 2)
        lines.append(f"| {kind} | {verdict} | {m[k]:,} |")
    lines += ["", "## Feed output", "", "| Item | Count |", "|---|---:|",
              f"| `domains.txt` entries | {stats['domains_txt_entries']:,} |",
              f"| `domains-priority.txt` entries | {stats['domains_priority_entries']:,} |",
              f"| `urls.txt` entries | {stats['urls_entries']:,} |",
              f"| CDN owners blocked at owner level | {stats['cdn']['gh_owners_owner_level']:,} |",
              f"| CDN repos blocked at repo level | {stats['cdn']['gh_repos_repo_level']:,} |",
              f"| npm packages blocked | {stats['cdn']['npm_packages']:,} |",
              f"| Game engines blocked at owner level (learned + seeded) | {stats['cdn'].get('engine_owners', 0) + stats['cdn'].get('seeded_owner_blocks', 0):,} |",
              f"| CDN mirror hosts covered | {len(cdn.MIRRORS):,} |",
              f"| Waiting for a human decision (`review/held.txt`) | {stats.get('review_held', 0):,} |", "",
              "## Tracked discoveries", "", "| Entry type | Status | Count |", "|---|---|---:|"]
    lines += [f"| {k} | {st} | {n:,} |" for (k, st), n in sorted(by.items())]
    lines += ["", "## Lists", "", "| List | Entries |", "|---|---:|"]
    lines += [f"| {n} | {c:,} |" for n, c in sorted(stats["lists"].items())]
    d = ROOT / "docs"
    d.mkdir(exist_ok=True)
    (d / "latest-run.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
