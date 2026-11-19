# How the feed is built

The collector (`collector/collect.py`) runs every 2 hours in GitHub Actions. Each run goes through the five stages below, and every check in them is counted. The counts from the most recent run are published automatically in **[latest-run.md](latest-run.md)**.

```
 1. COLLECT                2. DISCOVER                     3. FILTER            4. VERIFY (live)         5. PUBLISH
 ───────────               ───────────                     ─────────            ────────────────         ─────────
 14 curated lists   ──┐    GitHub repo search  ──┐
                      │    README link scan      │
                      │    Student link lists    ├──► links ──► 8 filter  ──► fetch + fingerprint ──► domains.txt
                      │    Certificate logs      │              checks         (game / proxy /          domains-priority.txt
                      │    CDN owner expansion   │                              loader / listed)        urls.txt
                      │    CDN code search     ──┘                                    │
                      └──────────────────────────────────────────────────────────────┴──► (trusted lists skip live checks)
```

---

## Stage 1: Curated lists

**What:** downloads 14 community-maintained gaming blocklists (`config/sources.toml → [[lists]]`).

| Check | What it does |
|---|---|
| Download | Fetches each list. If a list is unreachable, the last good copy in `data/lists/` is used, so an outage never empties the feed. |
| Format parsing | Understands five formats: hosts file (`0.0.0.0 x`), adblock (`\|\|x^`), plain domains, the UT1 university tarball, and AdGuard's services JSON. |
| Rule rejection (adblock) | Skips exception rules (`@@`), cosmetic and regex rules, and rules that only target one path (`\|\|host/path`), which can't be expressed as a whole-domain block. |
| Normalization | Lowercases, strips schemes, ports, paths and `www.`, converts international names to ASCII, and rejects IP addresses, whole-TLD rules (`\|\|games^`) and malformed names. |
| Trust tier | **Trusted** lists go straight to the feed. **Untrusted** lists (currently one stale gist) are sent to Stage 4 to be checked live first. |

Counted in latest-run.md as *Curated lists downloaded* and *List entries parsed and normalized*.

---

## Stage 2: Discovery

These sources find sites that no list carries yet. Everything found here becomes a *candidate link*, and none of it reaches the feed without passing Stages 3 and 4.

### 2a. GitHub repository search

| Check | What it does |
|---|---|
| Topic searches | Repositories tagged `unblocked-games`, `unblockedforschool`, `unblockers-for-school`, `gn-math`, `eaglercraft`, `browser-games` and 6 more, pushed in the last 120 days. |
| Keyword searches | 3 free-text searches, such as *"unblocked games"* in names and descriptions. |
| Homepage harvest | Each repository's *website* field, and its GitHub Pages address, become candidates. |
| README link scan | The README of every repository that changed since the last run (up to 300 per run) is scanned for links. |
| Hint filter (README only) | A README link is kept only if it's on a free-hosting platform, or its URL contains a game or bypass word (`game`, `unbl`, `ubg`, `arcade`, `math`, `proxy` and others). This drops thousands of unrelated documentation links. |

### 2b. Student link lists ("aggregators")

Nine pages that students pass around, each listing hundreds to thousands of live mirror links (`config/sources.toml → [aggregators]`). Every link on every page becomes a candidate.

### 2c. Certificate Transparency

Every HTTPS site needs a public certificate, so a search of the public certificate logs (crt.sh) for names containing `unblocked`, `ubg`, `gn-math`, `eaglercraft` and similar finds new sites within hours of their creation. Certificates older than 45 days are ignored. crt.sh is often slow, so this source is best-effort.

### 2d. CDN loaders: owner expansion

Students increasingly avoid domains entirely. They put a game or proxy *loader* file in a GitHub repository and open it through a free public CDN, for example `cdn.jsdelivr.net/gh/<owner>/<repo>@main/index.svg`. See [CDN loaders](#cdn-loaders) below.

| Check | What it does |
|---|---|
| Owner listing | For every GitHub owner with at least one confirmed loader, all of their repositories are listed (newest 40, once a day, up to 40 owners per run). |
| Repository file listing | jsDelivr's file API lists the files in each repository. |
| Entry-file selection | Up to 6 files per repository that could be opened as a page are picked: `index.*` first, then `.svg`, then `.html`. Scripts, styles and images are ignored. |

### 2e. CDN loaders: GitHub code search

Six code searches for the loader signature: a full-screen SVG (`position:fixed`, `inset:0`, `100vw`) that embeds HTML through `<foreignObject>` and loads an `<iframe>` or `<script>`. Each matching file becomes a candidate. This is how owners nobody has reported yet are found.

Counted in latest-run.md under *GitHub repository searches* through *Loader-candidate files from code search*.

---

## Stage 3: Filtering

Every candidate link from Stage 2 passes through these checks, in order. The first matching rule decides what happens to it.

| # | Check | Result |
|---|---|---|
| 1 | **Shared CDN?** Recognizes 12 GitHub-backed and 6 npm-backed CDN address formats (jsDelivr and its fastly, gcore and testingcf mirrors, unpkg, esm.sh, statically, githack). | Becomes a **CDN file** candidate, tracked by owner, repo and file. |
| 1a | ↳ Is the file something you can open as a page (`.svg`, `.html`)? | If not (`.js`, `.css`, images), dropped. Legitimate sites load these from CDNs every day. |
| 1b | ↳ Is it in a test or fixture folder (`tests/`, `LayoutTests/`, `fixtures/`, `xss*`, fuzzing corpora)? | Dropped. Browser and SVG test suites contain scripted SVGs on purpose. |
| 1c | ↳ Is the owner on `seeds/cdn-owner-allow.txt` (Bootstrap, jQuery, Simple Icons, Devicon, Font Awesome, and others)? | Dropped. |
| 2 | **Path-level platform?** Google Sites, Google Apps Script and CodeHS (`seeds/url-platforms.txt`). | Becomes a **URL** candidate, cut to the part that identifies one site, for example `sites.google.com/view/<name>` or `script.google.com/macros/s/<id>`. |
| 3 | **Allowlist?** `seeds/allow.txt`: core infrastructure, `.edu`, `.gov`, `.mil`, and classroom tools. | Dropped. The allowlist wins over every source. |
| 4 | **Known non-game service?** 76 services that show up in READMEs (badges, Discord, Patreon, documentation sites). | Dropped. |
| 5 | **Bare hosting platform?** For example `pages.dev` or `github.io` itself. | Dropped. Individual subdomains are fine, but the platform as a whole is never blocked. |
| 6 | **README hint** (README links only; see 2a). | Dropped if there's no hint. |
| 7 | **Already on a trusted list?** | Skips the live check, because it's already in the feed. |
| 8 | Everything else | Becomes a **host** candidate. |

Counted in latest-run.md as *Links examined by the filters* and the *dropped:* rows.

---

## Stage 4: Live verification

Each candidate is fetched the way a browser would, and the content is fingerprinted. Up to 1,500 hosts or URLs and 1,500 CDN files are checked per run, newest first, using 32 parallel workers with a 10-second timeout.

### Fingerprints

| Verdict | What it looks for |
|---|---|
| **game** | Any one *strong* signal: "unblocked games", GameDistribution, Unity WebGL loaders, Ruffle (Flash), EmulatorJS, Eaglercraft, gn-math, `games.json` game catalogs, "games for school" and others (20 patterns). **Or** three or more *weak* signals, such as well-known titles (Retro Bowl, Slope, Cookie Clicker, Geometry Dash, 1v1.lol, Bitlife and others; 42 patterns). **Or** a game-like page title plus one specific title. |
| **proxy** | Web-proxy frameworks: Ultraviolet (`__uv$config`, `uv.bundle.js`), Scramjet, Wisp, bare-server, bare-mux, Epoxy and libcurl transports, Rammerhead, Interstellar, Holy Unblocker (15 patterns). |
| **loader** (SVG, anywhere) | An SVG that embeds HTML (`<foreignObject>` with an XHTML body), contains something active (`<iframe>`, `<script>`, `srcdoc`, `atob()`, `document.write`, `window.open`, `location.*`, dynamic `import()`), **and** either covers the whole screen or actively navigates or decodes. A script inside an SVG that redirects or writes the page also counts. Real icons and logos never do this. |
| **loader** (HTML, CDN files only) | A full-screen `<iframe>`, `document.write(atob(...))`, a large `srcdoc` payload, an `about:blank` pop-up cloak, or a **tab cloak**: a page whose title copies a school tool (Google Classroom, Docs, Clever, Canvas, Schoology, IXL, GoGuardian and 15 others) but is served from a CDN, where no real one lives. |
| **listed** | A Google Sites or Apps Script page that appears on a student link list. These pages render their content inside Google's sandbox, so they rarely fingerprint, but being on a bypass list is enough evidence. |
| **alive** | Reachable, but nothing matched. The candidate goes to `review/pending.txt` for a human or the daily review task. |
| **dead** | DNS failure, connection error, or HTTP 404/410/5xx. After 3 dead checks the candidate is rejected. |

### Extra checks during verification

| Check | What it does |
|---|---|
| Script follow-through | Pages that are only a thin loading shell get their first 3 same-site scripts fetched and fingerprinted too. |
| Redirect capture | When a confirmed site redirects to a different domain (often a custom domain behind a github.io mirror), the landing domain is added too. |
| Cloudflare tolerance | 401, 403, 429 and 503 responses count as *alive*, not *dead*, because they're usually bot challenges. |
| Re-verification | Confirmed entries are re-checked every 7 days. One that stops matching stays in the feed but is flagged for review. |
| Aging | A confirmed discovery that hasn't been alive for 60 days is removed. Unconfirmed candidates not seen for 90 days are forgotten. |

Counted in latest-run.md under *Live check results*, by entry type and verdict.

---

## Stage 5: Publishing

| File | Built from |
|---|---|
| `fortigate/domains.txt` | Hand-confirmed seeds + all trusted lists + confirmed discovered hosts, minus the allowlist and bare platforms. Registrable domains are written as both `example.com` and `*.example.com`, and subdomains already covered by a wildcard are dropped. |
| `fortigate/domains-priority.txt` | The same, but only the lists focused on unblocked games (no general gaming category lists). |
| `fortigate/urls.txt` | Hand-confirmed URL seeds + confirmed Google Sites and Apps Script URLs + **CDN loader entries** (below). |

Files are split at 100,000 lines (`domains-2.txt` and so on), and are only rewritten when their contents change.

<a id="cdn-loaders"></a>
### CDN loader entries

A single loader is reachable through many CDN addresses, so each confirmed finding is written for **every mirror**:

| Finding | Entries written |
|---|---|
| GitHub owner with **≥ 2** confirmed loader repos (`owner_promote_min`) | **Owner level**: `cdn.jsdelivr.net/gh/<owner>/` plus the same on fastly, gcore and testingcf, the `/combine/gh/` form of each, `esm.sh/gh/`, `cdn.statically.io/gh/`, `raw.githack.com/` and `rawcdn.githack.com/`. That's 12 entries, doubled if the owner name has capitals, so both spellings match. Every current and future repo from that owner is covered. |
| GitHub owner with 1 confirmed repo | **Repo level**: the same 12 mirrors, for that repo only, in both `repo/` and `repo@` forms (to cover pinned versions). |
| npm package | **Package level**: `cdn.jsdelivr.net/npm/<pkg>` on all 4 jsDelivr hosts, `unpkg.com/<pkg>` and `esm.sh/<pkg>`, in both `/` and `@` forms. |

`url_entry_style` in `config/sources.toml` switches entries between prefix form (`.../gh/owner/`) and wildcard form (`.../gh/owner/*`), depending on how your FortiOS version matches URL-list entries.

---

## Human controls

| File | Effect |
|---|---|
| `seeds/confirmed.txt` | Domains always in the feed. |
| `seeds/confirmed-urls.txt` | URL entries always in the feed. |
| `seeds/allow.txt` | Domains never in the feed. Wins over everything. |
| `seeds/cdn-owner-allow.txt` | GitHub owners and npm packages never turned into CDN entries. |
| `seeds/platforms.txt` | Hosting platforms that are never blocked as a whole. |
| `seeds/url-platforms.txt` | Hosts that are blocked by path, with a pattern for the part to keep. |
| `review/pending.txt` | What the job couldn't decide: alive but no fingerprint. |
| `docs/latest-run.md` | The numbers from the last run. |
