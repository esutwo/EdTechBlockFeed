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

    if not ("Authorization" in gh_headers()):
        log("[cdn] code search skipped (needs GITHUB_TOKEN)")
        return
    for q in c.get("code_search_queries", []):
        for page in range(1, c.get("code_search_pages", 1) + 1):
            url = "https://api.github.com/search/code?" + urllib.parse.urlencode(
                {"q": q, "per_page": 100, "page": page})
            try:
                data, _ = http_get(url, headers=gh_headers(), timeout=60)
                items = json.loads(data).get("items", [])
            except Exception as e:  # noqa: BLE001
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
        for url, *_ in samples:
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

    def check(kv):
        k, e = kv
        return k, classify(e["check_url"], timeout=timeout, ua=UA, cdn=e["kind"] == "cdn")

    redirected: list[tuple[str, str, str]] = []
    with cf.ThreadPoolExecutor(settings.get("verify_workers", 32)) as ex:
        for k, res in ex.map(check, todo):
            e = entries[k]
            e["last_checked"] = date_str(TODAY)
            e["attempts"] = e.get("attempts", 0) + 1
            e["evidence"] = res.evidence[:200]
            METRICS[f"verify_{e['kind']}_{res.verdict}"] += 1
            # A Google Sites / Apps Script page listed by a student link list is
            # a bypass by definition; their content rarely fingerprints.
            if (res.verdict == "alive" and e["kind"] == "url"
                    and e["source"].startswith("aggregator:")):
                res.verdict = "listed"
            if res.verdict in ("game", "proxy", "loader", "listed"):
                e.update(status="confirmed", category=res.verdict,
                         last_alive=date_str(TODAY), attempts=0)
                if e["kind"] == "host":
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
        tmp = Candidates(cands.allow, cands.platforms, cands.url_platforms, cands.cdn_owner_allow)
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


def build_cdn_lines(entries: dict, settings: dict) -> tuple[set[str], dict]:
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
    return lines, {"gh_owners_owner_level": owner_level, "gh_repos_repo_level": repo_level,
                   "npm_packages": len(npm), "url_lines": len(lines)}


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
    if not args.no_discovery:
        discover_github(cfg, cands, state)
        discover_aggregators(cfg, cands)
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
    cdn_lines, cdn_stats = build_cdn_lines(entries, settings)
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

    stats = {
        "domains_txt_entries": len(all_lines),
        "domains_priority_entries": len(pri_lines),
        "urls_entries": len(url_lines),
        "lists": {n: len(h) for n, (_, h, _) in lists.items()},
        "discovered_confirmed": len(disc_hosts) + len(disc_urls) + sum(
            1 for e in entries.values() if e["kind"] == "cdn" and e["status"] == "confirmed"),
        "cdn": cdn_stats,
        "discovered_pending": sum(1 for e in entries.values() if e["status"] == "pending"),
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
        ("CDN owners expanded (repo listings)", g("cdn_owners_expanded")),
        ("CDN owner repositories listed", g("cdn_owner_repos_listed")),
        ("CDN entry files found in owner repos", g("cdn_owner_entry_files_found")),
        ("GitHub code searches for loader files", g("cdn_code_search_requests")),
        ("Loader-candidate files from code search", g("cdn_code_search_files")),
        ("Links examined by the filters", g("links_examined")),
        ("  dropped: allowlist", g("links_dropped_allowlist")),
        ("  dropped: known non-game service", g("links_dropped_noise")),
        ("  dropped: bare hosting-platform domain", g("links_dropped_platform_apex")),
        ("  dropped: README link with no game/bypass hint", g("links_dropped_no_hint")),
        ("  dropped: CDN file that isn't a page (js/css/img)", g("cdn_links_not_entry_file")),
        ("  dropped: CDN owner on allowlist", g("cdn_links_allowlisted_owner")),
        ("  dropped: CDN file in a test/fixture folder", g("cdn_links_test_fixture")),
        ("Links with a CDN path shape on unknown hosts", g("cdn_shape_links")),
        ("Unknown hosts tested for being a new CDN/mirror", g("cdn_shape_hosts")),
        ("  live checks on those hosts", g("cdn_detect_checks")),
        ("  new CDNs/mirrors confirmed this run", g("cdn_detect_confirmed")),
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
              f"| CDN mirror hosts covered | {len(cdn.MIRRORS):,} |", "",
              "## Tracked discoveries", "", "| Entry type | Status | Count |", "|---|---|---:|"]
    lines += [f"| {k} | {st} | {n:,} |" for (k, st), n in sorted(by.items())]
    lines += ["", "## Lists", "", "| List | Entries |", "|---|---:|"]
    lines += [f"| {n} | {c:,} |" for n, c in sorted(stats["lists"].items())]
    d = ROOT / "docs"
    d.mkdir(exist_ok=True)
    (d / "latest-run.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
