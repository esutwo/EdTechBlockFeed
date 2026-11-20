# How the feed is built

The collector (`collector/collect.py`) runs in GitHub Actions hourly during school hours (weekdays 6am–5pm Central) and every 4 hours otherwise. Each run goes through the five stages below, and every check in them is counted. The counts from the most recent run are published automatically in **[latest-run.md](latest-run.md)**.

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

### 2f. New CDN and mirror detection

Students move to whichever CDN hostname isn't blocked yet: alternate jsDelivr hostnames (`quantil.`, `originfastly.`), third-party jsDelivr clones (`cdn.jsdmirror.com`, `jsd.onmicrosoft.cn`, `cdn.staticdelivr.com`) and new services. The collector looks for them on every run, using links it has already downloaded:

| Check | What it does |
|---|---|
| Path shape | Any link on a host we don't track whose path looks like a file CDN is held aside instead of being treated as a normal site. The shapes are `/gh/<owner>/<repo>@<ref>/…`, `/npm/<pkg>@<ver>/…`, `/<pkg>@<ver>/x.html`, and `/<owner>/<repo>/main/x.svg`. The allowlist doesn't apply here, because new `*.jsdelivr.net` hostnames are the likeliest mirrors. |
| Owner evidence | The host is tested only if its links reference **2 or more different owners or packages**, or **any owner we've already confirmed**. A single site that happens to have a CDN-like path isn't enough. |
| Loader confirmation | Up to 3 sample links (confirmed owners first) are fetched. If one serves a loader, game or proxy, the host is **confirmed**. |
| Activation | A confirmed host is registered as a mirror straight away. Every owner, repo and package entry in `urls.txt` is written for it from that run on, and its links are processed as CDN files. |
| Safety | A shaped host is **never** blocked as a whole domain, whether or not it's confirmed. Getting it wrong can only make blocking narrower. |
| Notification | Confirmed hosts are listed in `review/new-cdns.txt`, with *suspect* and *watch* hosts below them. A **GitHub issue** labelled `new-cdn` is opened once per host, with a to-do list: add it to the Chrome URL blocklist, and make it permanent in `seeds/cdn-mirrors.txt`. |

Counted in latest-run.md under *GitHub repository searches* through *new CDNs/mirrors confirmed this run*.

---

## Stage 3: Filtering

Every candidate link from Stage 2 passes through these checks, in order. The first matching rule decides what happens to it.

| # | Check | Result |
|---|---|---|
| 1 | **Shared CDN?** Recognizes every known GitHub/npm file CDN host: 9 built in (jsDelivr's cdn, fastly, gcore and testingcf hostnames, unpkg, esm.sh, statically, and two githack hosts), plus `seeds/cdn-mirrors.txt` and any auto-detected mirrors (2f), in 5 URL styles. | Becomes a **CDN file** candidate, tracked by owner, repo and file. |
| 1′ | **CDN-shaped link on a host we don't track?** | Held for new-CDN detection (2f). Never becomes a whole-host candidate. |
| 1a | ↳ Is the file something you can open as a page (`.svg`, `.html`)? | If not (`.js`, `.css`, images), dropped. Legitimate sites load these from CDNs every day. |
| 1b | ↳ Is it in a test or fixture folder (`tests/`, `LayoutTests/`, `fixtures/`, `xss*`, fuzzing corpora)? | Dropped. Browser and SVG test suites contain scripted SVGs on purpose. |
| 1c | ↳ Is the owner on `seeds/cdn-owner-allow.txt` (Bootstrap, jQuery, Simple Icons, Devicon, Font Awesome, and others)? | Dropped. |
| 2 | **Path-level platform?** Google Sites, Google Apps Script and CodeHS (`seeds/url-platforms.txt`). | Becomes a **URL** candidate, cut to the part that identifies one site, for example `sites.google.com/view/<name>` or `script.google.com/macros/s/<id>`. |
| 3 | **Allowlist?** `seeds/allow.txt`: core infrastructure, `.edu`, `.gov`, `.mil`, and classroom tools. | Dropped. The allowlist wins over every source. |
| 4 | **Known non-game service?** 76 services that show up in READMEs (badges, Discord, Patreon, documentation sites). | Dropped. |
| 5 | **Bare hosting platform or CDN network?** For example `pages.dev`, `github.io`, `akamaihd.net` or `edgesuite.net` itself. | Dropped. Individual subdomains, such as one game's CDN hostname, are fine, but the network as a whole is never blocked. |
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
| **alive** | Reachable, but nothing matched. The candidate goes to the automatic retry queue, `review/pending.txt` on the `state` branch, and is re-checked daily. After 3 checks without a match it is rejected. |
| **dead** | DNS failure, connection error, or HTTP 404/410/5xx. After 3 dead checks the candidate is rejected. |

### Extra checks during verification

| Check | What it does |
|---|---|
| Script follow-through | Pages that are only a thin loading shell get their first 3 same-site scripts fetched and fingerprinted too. |
| Popularity guard (discovered sites only) | Uses the Tranco research ranking of the top 100,000 domains, refreshed weekly. A discovered site in the **top 10,000** (for example `nytimes.com`) is never blocked automatically. It goes to `review/held.txt` for a person to decide. Curated lists aren't affected. |
| Homepage guard (established sites) | For a ranked but less popular site (10,000–100,000), a game page deep inside it (`site.com/games/x`) only blocks the whole domain if the **homepage** is a game or proxy site too. Unranked, obscure domains skip this on purpose, because disguised bypass sites hide their games behind a decoy homepage. Free-hosting subdomains (`user.github.io`) count as the author's own site. |
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

### Publish safety check

Before anything is committed, `collector/check_feed.py` reads every output file and **fails the run** if it finds:

* a domain covered by `seeds/allow.txt`;
* a hosting platform or CDN network as a whole (`pages.dev`, `edgesuite.net`, `akamaihd.net` and so on, from `seeds/platforms.txt`); or
* any of about 30 **critical domains hard-coded in the checker**: Google (`google.com`, `googleapis.com`, `gstatic.com`, `gvt1/2/3.com` for Chrome and ChromeOS updates and Play Store, `ggpht.com`, `1e100.net`), Android (`android.com`), YouTube, Microsoft 365 including its sign-in content (`msauth.net`, `msftauth.net`), Apple, GitHub, jsDelivr, unpkg, Cloudflare, AWS, the **Amplify** curriculum and assessment platform (`*.amplify.com`), and the `.edu` and `.gov` TLDs.

Because the critical list lives in code rather than in `allow.txt`, a mistaken edit to the allowlist still can't publish a feed that breaks Chromebooks. A failed check stops the workflow before the commit step, so the FortiGates keep pulling the last good feed, and the failure shows up in GitHub Actions.

<a id="cdn-loaders"></a>
### CDN loader entries

A single loader is reachable through many CDN addresses, so each confirmed finding is written for **every mirror**:

| Finding | Entries written |
|---|---|
| GitHub owner with **≥ 2** confirmed loader repos (`owner_promote_min`) | **Owner level**: `<mirror>/gh/<owner>/` on every GitHub-serving mirror, plus the `/combine/gh/` form on each jsDelivr-style mirror, `esm.sh/gh/`, statically, and the githack hosts. That's 24 entries with the current 16 mirror hosts, doubled if the owner name has capitals, so both spellings match. Every current and future repo from that owner is covered. |
| GitHub owner with 1 confirmed repo | **Repo level**: the same mirrors, for that repo only, in both `repo/` and `repo@` forms (to cover pinned versions). |
| npm package | **Package level**: `<mirror>/npm/<pkg>` on every jsDelivr-style mirror, plus `unpkg.com/<pkg>` and `esm.sh/<pkg>` and its aliases, in both `/` and `@` forms. |

The mirror list grows on its own (2f), so entries for owners already in the feed are rewritten for a new mirror on the run that detects it.

`url_entry_style` in `config/sources.toml` switches entries between prefix form (`.../gh/owner/`) and wildcard form (`.../gh/owner/*`), depending on how your FortiOS version matches URL-list entries.

---

## Daily review

Each school day at 7:13 AM Central, a scheduled Claude review session goes through `review/held.txt`, the confirmed and suspect hosts in `review/new-cdns.txt`, and any open `new-cdn` issues. For each one it visits the site, decides block, dismiss, allow or mirror, records the decision with a reason in the matching seed file, and opens **one pull request** for a person to approve. It never merges anything itself. Nothing changes in the feed until the PR is merged.

## Human controls

| File | Effect |
|---|---|
| `seeds/confirmed.txt` | Domains always in the feed. |
| `seeds/confirmed-urls.txt` | URL entries always in the feed. |
| `seeds/allow.txt` | Domains never in the feed. Wins over everything. |
| `seeds/cdn-owner-allow.txt` | GitHub owners and npm packages never turned into CDN entries. |
| `seeds/cdn-mirrors.txt` | Extra CDN mirror hosts and their URL style. Make an auto-detected mirror permanent here, or add `<host> ignore` to reject one. |
| `seeds/platforms.txt` | Hosting platforms that are never blocked as a whole. |
| `seeds/url-platforms.txt` | Hosts that are blocked by path, with a pattern for the part to keep. |
| `review/held.txt` | **The only list that needs a person.** Sites held by the popularity or homepage guard, plus blocked sites whose game fingerprint disappeared. For each one: block (`seeds/confirmed.txt`), dismiss (`seeds/review-dismissed.txt`) or allow (`seeds/allow.txt`). |
| `seeds/review-dismissed.txt` | Held sites a reviewer decided not to block. The collector stops re-checking them. |
| `review/pending.txt` (on the `state` branch) | Automatic retry queue: alive but no fingerprint yet, or unreachable. Re-checked daily, and dropped after 3 failed checks. No action needed. |
| `state` branch | The collector's working state (`data/state.json`, list caches, popularity ranking, retry queue). It's overwritten every run, so `main`'s history only records feed changes. |
| `review/new-cdns.txt` | Auto-detected CDN mirrors (confirmed, suspect, watch). Each confirmed one also gets a GitHub issue. |
| `docs/latest-run.md` | The numbers from the last run. |
