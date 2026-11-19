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
# Every CDN host has a URL *style*. The style says which GitHub / npm path
# prefixes it serves, so a new mirror only needs a host + style
# (seeds/cdn-mirrors.txt, or automatic detection in collect.py).
STYLES: dict[str, dict[str, list[str]]] = {
    # jsDelivr and its clones: /gh/owner/repo@ref/file, /combine/gh/..., /npm/pkg@v/file
    "jsdelivr": {"gh": ["gh/", "combine/gh/"], "npm": ["npm/"]},
    # statically: /gh/owner/repo@ref/file
    "statically": {"gh": ["gh/"], "npm": []},
    # esm.sh: /gh/owner/repo@ref/file and /pkg@v/file
    "esm": {"gh": ["gh/"], "npm": [""]},
    # unpkg: /pkg@v/file
    "unpkg": {"gh": [], "npm": [""]},
    # githack: /owner/repo/ref/file
    "githack": {"gh": [""], "npm": []},
}
BUILTIN_MIRRORS = {
    "cdn.jsdelivr.net": "jsdelivr",
    "fastly.jsdelivr.net": "jsdelivr",
    "gcore.jsdelivr.net": "jsdelivr",
    "testingcf.jsdelivr.net": "jsdelivr",
    "esm.sh": "esm",
    "cdn.statically.io": "statically",
    "raw.githack.com": "githack",
    "rawcdn.githack.com": "githack",
    "unpkg.com": "unpkg",
}
MIRRORS: dict[str, str] = dict(BUILTIN_MIRRORS)   # host -> style (extended at runtime)
CDN_HOSTS: set[str] = set(MIRRORS)


def register(host: str, style: str) -> None:
    """Add a mirror host (from seeds/cdn-mirrors.txt or auto-detection)."""
    if style in STYLES:
        MIRRORS[host.lower()] = style
        CDN_HOSTS.add(host.lower())


def mirrors(kind: str) -> list[tuple[str, str]]:
    """(host, path prefix) pairs serving GitHub ("gh") or npm content."""
    return [(h, pre) for h, st in sorted(MIRRORS.items()) for pre in STYLES[st][kind]]


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

    return parse_path(MIRRORS[host], path)


def parse_path(style: str, path: str) -> CdnRef | None:
    """Parse a URL path (no leading slash) according to a mirror style."""
    st = STYLES[style]
    if style == "githack":
        m = re.match(rf"({_OWNER})/({_REPO})/[^/]+/(.+)", path)
        return CdnRef("gh", m.group(1), m.group(2), m.group(3)) if m else None
    for pre in st["gh"]:
        if pre and path.lower().startswith(pre):
            gh_path = path[len(pre):].split(",", 1)[0]  # combine: first file only
            m = re.match(rf"({_OWNER})/({_REPO})(?:@[^/]*)?(?:/(.*))?$", gh_path)
            if not m:
                return None
            return CdnRef("gh", m.group(1), m.group(2), (m.group(3) or "").rstrip("/"))
    for pre in st["npm"]:
        if pre and not path.lower().startswith(pre):
            continue
        npm_path = path[len(pre):]
        if pre == "" and re.match(r"(?:combine/)?gh/", npm_path):
            return None
        m = re.match(rf"({_PKG})(?:@[^/]*)?(?:/(.*))?$", npm_path, re.I)
        if m:
            return CdnRef("npm", m.group(1).lower(), "", (m.group(2) or "").rstrip("/"))
    return None


_SHAPES = [
    # (style, regex on the path). Order matters: most specific first.
    ("jsdelivr", re.compile(rf"^(?:combine/)?gh/{_OWNER}/{_REPO}(?:@[^/]+)?/.+", re.I)),
    ("jsdelivr", re.compile(rf"^npm/{_PKG}@[^/]+/.+", re.I)),
    ("unpkg", re.compile(rf"^{_PKG}@\d[^/]*/.+\.(?:svg|html?)$", re.I)),
    ("githack", re.compile(rf"^{_OWNER}/{_REPO}/(?:main|master|gh-pages|[0-9a-f]{{7,40}})/.+\.(?:svg|html?)$", re.I)),
]


def infer_style(path: str) -> str | None:
    """Does a URL path on an unknown host look like a GitHub/npm CDN path?"""
    path = path.lstrip("/")
    for style, rx in _SHAPES:
        if rx.match(path):
            return style
    return None


def entry_lines(kind: str, owner: str, repo: str = "", style: str = "prefix") -> list[str]:
    """FortiGate URL-list lines covering an owner, repo, or npm package on
    every mirror. style="prefix" emits 'host/path/'; "wildcard" appends '*'."""
    out = []
    if kind == "gh":
        names = {owner, owner.lower()}
        for host, pre in mirrors("gh"):
            for o in sorted(names):
                if repo:
                    for r in sorted({repo, repo.lower()}):
                        out += [f"{host}/{pre}{o}/{r}/", f"{host}/{pre}{o}/{r}@"]
                else:
                    out.append(f"{host}/{pre}{o}/")
    else:  # npm package
        for host, pre in mirrors("npm"):
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
