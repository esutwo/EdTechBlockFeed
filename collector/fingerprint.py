"""Live fingerprinting: is this URL an unblocked-games (or web proxy) site?"""
from __future__ import annotations

import gzip
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

# Strong signals: one is enough.
GAME_STRONG = [
    r"unblocked[\s_-]*games", r"\bubg\s*\d*\b", r"games?[\s_-]*unblocked",
    r"gamedistribution\.com", r"createUnityInstance", r"UnityLoader\.js",
    r"\bruffle(\.js|-rs|\.rs)?\b", r"eaglercraft", r"emulatorjs", r"gn-?math",
    r"html5\s+games", r"play\s+free\s+(online\s+)?games", r"\b3kh0\b",
    r"selenite", r"games\.json", r"/games/[a-z0-9-]+/index\.html",
    r"truffled", r"frogie'?s\s+arcade", r"chromebook\s+games",
    r"games\s+for\s+school",
]
# Weak signals: need two distinct ones (or one plus a games <title>).
GAME_WEAK = [
    r"retro[\s-]?bowl", r"slope(\s+game|-game|\b)", r"cookie[\s-]?clicker",
    r"drift[\s-]?hunters", r"subway[\s-]?surfers", r"geometry[\s-]?dash",
    r"1v1\.lol", r"snow[\s-]?rider", r"basketball[\s-]?stars", r"bitlife",
    r"moto[\s-]?x3m", r"\brun[\s-]?3\b", r"\bfnaf\b", r"five nights at freddy",
    r"tunnel[\s-]?rush", r"minecraft", r"crazygames", r"poki\.com", r"\by8\.com",
    r"\bkizi\b", r"\bfriv\b", r"\bpapa'?s\b", r"stickman", r"\bbloons?\b",
    r"\bhole\.io\b", r"\bpaper\.io\b", r"\bsurviv\.io\b", r"\bkrunker\b",
    r"\bshell[\s-]?shockers\b", r"\bsmash[\s-]?karts\b", r"\btemple[\s-]?run\b",
    r"\bhappy[\s-]?wheels\b", r"\b2048\b", r"\bflappy\b", r"\bpacman\b",
    r"\bsuper[\s-]?mario\b", r"\bpokemon\b", r"\bn64\b|\bgba\b|\bnes\b",
    r"\bgame[\s-]?(library|catalog|list)\b", r"\bplay\s+now\b", r"\bleaderboard\b",
    r"\bgames\b",
]
PROXY = [
    r"__uv\$config", r"uv\.config\.js", r"uv\.bundle\.js", r"uv\.sw\.js",
    r"scramjet", r"/wisp/", r"bare-?mux", r"epoxy-?transport", r"libcurl-?transport",
    r"rammerhead", r"holy\s*unblocker", r"interstellar", r"/bare/v[1-3]/",
    r"titanium\s*network", r"\bultraviolet\b",
]
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_GS = [re.compile(p, re.I) for p in GAME_STRONG]
_GW = [re.compile(p, re.I) for p in GAME_WEAK]
_PX = [re.compile(p, re.I) for p in PROXY]


@dataclass
class Result:
    verdict: str  # game | proxy | alive | dead
    evidence: str = ""
    final_url: str = ""


def _fetch(url: str, timeout: float, ua: str) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": ua, "Accept": "text/html,*/*", "Accept-Encoding": "gzip",
        "Accept-Language": "en-US,en;q=0.9"})
    ctx = ssl.create_default_context()
    try:
        r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    except urllib.error.HTTPError as e:
        r = e
    with r:
        body = r.read(800_000)
        if r.headers.get("Content-Encoding") == "gzip":
            try:
                body = gzip.decompress(body)
            except Exception:  # noqa: BLE001  truncated gzip
                pass
        return r.status if hasattr(r, "status") else r.code, r.geturl(), body.decode("utf-8", "replace")


def score(text: str) -> Result | None:
    title_m = TITLE_RE.search(text)
    title = (title_m.group(1).strip() if title_m else "")[:120]
    px = sorted({m.group(0).lower() for r in _PX if (m := r.search(text))})
    gs = sorted({m.group(0).lower() for r in _GS if (m := r.search(text))})
    gw = sorted({m.group(0).lower() for r in _GW if (m := r.search(text))})
    title_game = bool(re.search(r"\bgames?\b|arcade|unblocked|\bubg\b", title, re.I))
    specific = [w for w in gw if w not in ("games", "play now", "leaderboard")]
    ev = f"title={title!r} strong={gs[:4]} weak={gw[:5]} proxy={px[:3]}"
    if gs or len(gw) >= 3 or (title_game and specific):
        return Result("game", ev)
    if px:
        return Result("proxy", ev)
    return None


def classify(url: str, *, timeout: float = 10, ua: str = "Mozilla/5.0") -> Result:
    try:
        status, final, text = _fetch(url, timeout, ua)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
            ssl.SSLError, OSError, ValueError) as e:
        return Result("dead", f"{type(e).__name__}: {str(e)[:80]}")
    if status >= 400:
        if status in (401, 403, 429, 503):  # often Cloudflare challenge: alive
            return Result("alive", f"HTTP {status}")
        return Result("dead", f"HTTP {status}")
    r = score(text)
    if r:
        r.evidence = f"{final} {r.evidence}"
        r.final_url = final
        return r
    # Thin SPA shells: look at the first couple of same-origin scripts.
    scripts = re.findall(r"""<script[^>]+src=["']([^"']+)["']""", text, re.I)[:3]
    combined = text
    for s in scripts:
        su = urllib.parse.urljoin(final, s)
        if urllib.parse.urlsplit(su).hostname != urllib.parse.urlsplit(final).hostname:
            continue
        try:
            _, _, js = _fetch(su, timeout, ua)
            combined += "\n" + js[:400_000]
        except Exception:  # noqa: BLE001
            continue
    r = score(combined)
    if r:
        r.evidence = f"{final} (via scripts) {r.evidence}"
        r.final_url = final
        return r
    t = TITLE_RE.search(text)
    return Result("alive", f"{final} HTTP {status} title={(t.group(1).strip()[:80] if t else '')!r}")

