"""Hostname parsing, normalization and allow/platform matching helpers."""
from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit

_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
# URLs inside free text (READMEs, HTML, JSON)
URL_RE = re.compile(r"""https?://[^\s"'<>()\[\]{}`\\|^]+""", re.I)


def normalize_host(raw: str) -> str | None:
    """Return a clean lowercase hostname, or None if it isn't one.

    Accepts bare hosts, URLs, hosts-file lines, adblock rules and "*.x" forms.
    """
    s = raw.strip().lower()
    if not s or s.startswith(("#", "!", "[")):
        return None
    # adblock: ||example.com^ / ||example.com^$third-party
    if s.startswith("||"):
        s = s[2:]
        s = re.split(r"[\^$/]", s, maxsplit=1)[0]
    # hosts file: "0.0.0.0 example.com" / "127.0.0.1 example.com # comment"
    parts = s.split()
    if len(parts) >= 2 and _is_ip(parts[0]):
        s = parts[1]
    else:
        s = parts[0]
    if "://" in s:
        s = urlsplit(s).hostname or ""
    s = s.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in s:
        s = s.rsplit("@", 1)[1]
    s = s.split(":", 1)[0]  # port
    s = s.lstrip("*.").strip(".")
    if s.startswith("www."):
        # keep www-less form; wildcard emission covers www
        s = s[4:]
    if not s or len(s) > 253 or "." not in s or _is_ip(s):
        return None
    try:
        s = s.encode("idna").decode("ascii") if not s.isascii() else s
    except UnicodeError:
        return None
    labels = s.split(".")
    if not all(_LABEL.match(l) for l in labels):
        return None
    if labels[-1].isdigit() or len(labels[-1]) < 2:
        return None
    return s


def _is_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def read_list(path: Path) -> list[str]:
    """Read a seed/config list: one entry per line, '#' comments allowed."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line.lower())
    return out


class Matcher:
    """Matches hosts against entries.

    "example.com"        -> exact host only
    "*.example.com"      -> example.com and every subdomain
    """

    def __init__(self, entries: list[str]):
        self.exact: set[str] = set()
        self.suffix: set[str] = set()
        for e in entries:
            if e.startswith("*.") or e.startswith("."):
                bare = e.lstrip("*.").strip()
                h = normalize_host(bare) if "." in bare else (
                    bare if _LABEL.match(bare) else None)  # TLD-level, e.g. *.edu
                if h:
                    self.suffix.add(h)
            else:
                h = normalize_host(e)
                if h:
                    self.exact.add(h)

    def matches(self, host: str) -> bool:
        if host in self.exact or host in self.suffix:
            return True
        parts = host.split(".")
        for i in range(1, len(parts)):
            if ".".join(parts[i:]) in self.suffix:
                return True
        return False


def platform_apex(host: str, platforms: set[str]) -> str | None:
    """If host is under a shared-hosting platform, return that platform suffix."""
    parts = host.split(".")
    for i in range(len(parts) - 1):
        cand = ".".join(parts[i:])
        if cand in platforms:
            return cand
    return None


def extract_urls(text: str) -> list[str]:
    out = []
    for m in URL_RE.findall(text):
        out.append(m.rstrip(".,;:!*_~'\")]>"))
    return out
