"""Shared-CDN handling: GitHub- and npm-backed file CDNs.

Students host game/proxy "loaders" (usually a full-screen SVG or an HTML file)
in a GitHub repo or npm package and open it through a public CDN such as
cdn.jsdelivr.net/gh/<owner>/<repo>@main/index.svg. The CDN hostname can't be
blocked, so these are tracked per owner / repo / package and published as
URL-list entries for every mirror that serves the same content.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

# --- mirrors -----------------------------------------------------------------
# Hosts that serve any public GitHub repo, and the path prefix they use.
GH_MIRRORS = [
    ("cdn.jsdelivr.net", "gh/"),
    ("fastly.jsdelivr.net", "gh/"),
    ("gcore.jsdelivr.net", "gh/"),
    ("testingcf.jsdelivr.net", "gh/"),
    ("cdn.jsdelivr.net", "combine/gh/"),
    ("fastly.jsdelivr.net", "combine/gh/"),
    ("gcore.jsdelivr.net", "combine/gh/"),
    ("testingcf.jsdelivr.net", "combine/gh/"),
    ("esm.sh", "gh/"),
    ("cdn.statically.io", "gh/"),
    ("raw.githack.com", ""),
    ("rawcdn.githack.com", ""),
]
# Hosts that serve any public npm package.
NPM_MIRRORS = [
    ("cdn.jsdelivr.net", "npm/"),
    ("fastly.jsdelivr.net", "npm/"),
    ("gcore.jsdelivr.net", "npm/"),
    ("testingcf.jsdelivr.net", "npm/"),
    ("unpkg.com", ""),
    ("esm.sh", ""),
]
CDN_HOSTS = {h for h, _ in GH_MIRRORS} | {h for h, _ in NPM_MIRRORS}
_JSD = {"cdn.jsdelivr.net", "fastly.jsdelivr.net", "gcore.jsdelivr.net", "testingcf.jsdelivr.net"}

_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
_REPO = r"[A-Za-z0-9._-]{1,100}"
_PKG = r"(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*"


@dataclass(frozen=True)
class CdnRef:
    kind: str      # "gh" | "npm"
    owner: str     # gh owner, or npm package name
    repo: str      # gh repo ("" for npm)
    file: str      # path inside repo/package ("" if none)

    @property
    def key(self) -> str:
        if self.kind == "gh":
            return f"gh/{self.owner}/{self.repo}/{self.file}".rstrip("/")
        return f"npm/{self.owner}/{self.file}".rstrip("/")

    def check_url(self) -> str:
        """Canonical URL used for live verification (jsDelivr, latest ref)."""
        if self.kind == "gh":
            return f"https://cdn.jsdelivr.net/gh/{self.owner}/{self.repo}/{self.file}"
        return f"https://cdn.jsdelivr.net/npm/{self.owner}/{self.file}"


def parse(url: str) -> CdnRef | None:
    """Recognise a GitHub/npm CDN URL on any known mirror."""
    if "://" not in url:
        url = "https://" + url
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    host = (p.hostname or "").lower()
    path = urllib.parse.unquote(p.path).lstrip("/")
    if host not in CDN_HOSTS or not path:
        return None

    gh_path = None
    if host in _JSD or host in ("esm.sh", "cdn.statically.io"):
        m = re.match(r"(?:combine/)?gh/(.*)", path)
        if m:
            gh_path = m.group(1).split(",", 1)[0]  # combine: first file only
    elif host in ("raw.githack.com", "rawcdn.githack.com"):
        # /<owner>/<repo>/<ref>/<file>
        m = re.match(rf"({_OWNER})/({_REPO})/[^/]+/(.*)", path)
        if m:
            return CdnRef("gh", m.group(1), m.group(2), m.group(3))
        return None
    if gh_path is not None:
        m = re.match(rf"({_OWNER})/({_REPO}?)(?:@[^/]*)?(?:/(.*))?$", gh_path)
        if not m or not m.group(2):
            return None
        repo = m.group(2)
        return CdnRef("gh", m.group(1), repo, (m.group(3) or "").rstrip("/"))

    # npm forms
    npm_path = None
    if host in _JSD:
        m = re.match(r"npm/(.*)", path)
        npm_path = m.group(1) if m else None
    elif host in ("unpkg.com", "esm.sh"):
        npm_path = path
    if npm_path is None:
        return None
    m = re.match(rf"({_PKG})(?:@[^/]*)?(?:/(.*))?$", npm_path, re.I)
    if not m:
        return None
    return CdnRef("npm", m.group(1).lower(), "", (m.group(2) or "").rstrip("/"))


def entry_lines(kind: str, owner: str, repo: str = "", style: str = "prefix") -> list[str]:
    """FortiGate URL-list lines covering an owner, repo, or npm package on
    every mirror. style="prefix" emits 'host/path/'; "wildcard" appends '*'."""
    out = []
    if kind == "gh":
        names = {owner, owner.lower()}
        for host, pre in GH_MIRRORS:
            for o in sorted(names):
                if repo:
                    for r in sorted({repo, repo.lower()}):
                        out += [f"{host}/{pre}{o}/{r}/", f"{host}/{pre}{o}/{r}@"]
                else:
                    out.append(f"{host}/{pre}{o}/")
    else:  # npm package
        for host, pre in NPM_MIRRORS:
            out += [f"{host}/{pre}{owner}/", f"{host}/{pre}{owner}@"]
    if style == "wildcard":
        out = [l + "*" for l in out]
    return out


ENTRY_EXT = re.compile(r"\.(svg|html?|xhtml)$", re.I)
# Test suites and fixtures (browser engines, SVG libraries) contain SVGs with
# scripts on purpose; they're never loaders.
TEST_PATH = re.compile(
    r"(^|/)(tests?|LayoutTests|web-platform-tests|fixtures?|__tests__|specs?|testdata|"
    r"test-?data|test-?cases|xss\w*|payloads?|fuzz\w*|corpus)(/|$)", re.I)


def entry_files(files: list[str], limit: int = 6) -> list[str]:
    """Pick the files in a repo listing most likely to be a loader."""
    cands = [f.lstrip("/") for f in files if ENTRY_EXT.search(f)]
    cands = [f for f in cands if f.count("/") <= 4 and "node_modules" not in f
             and not TEST_PATH.search(f)]

    def rank(f: str):
        name = f.rsplit("/", 1)[-1].lower()
        return (0 if name.startswith("index.") else 1,
                0 if f.lower().endswith(".svg") else 1,
                f.count("/"), len(f))
    return sorted(cands, key=rank)[:limit]
