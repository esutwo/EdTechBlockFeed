# ESU #2 Threat Block Feeds

An automatically maintained **Network threat feed of gaming and "unblocked games" sites**, built for K-12 networks. Originally designed for Fortigate systems, but the feeds will work with any NGFW that can make use of text based third party feeds.

Students reach games through sites that are quick to stand up and change often: GitHub Pages, Cloudflare Pages, Vercel or Netlify mirrors, custom domains made to look like schools, and npm packages served from jsDelivr. FortiGuard often rates these as Education, Information Technology, Personal Websites or Unrated, not as Games, so a category block misses them. This repo pulls together curated community blocklists, discovers new sites on its own, checks them live, and publishes plain-text files that a FortiGate polls.

## Use this feed

**Any ESU, district, school or library is welcome to use these feeds, free.** You don't need to run anything: point your firewall at the published files below. They're rebuilt hourly during the school day and reviewed every school morning.

1. Add the feed URLs from [Feed files](#feed-files) to your firewall as external threat feeds (FortiGate steps below; Sophos and other NGFWs that accept plain-text domain and URL lists work too).
2. Start in **monitor** mode for a few days, then switch to **block**.
3. Please credit **"EdTech Block Feed by ESU 2"** when you describe or document it. Found a false positive or a site we missed? Open an issue.

The feeds are licensed CC BY-NC-SA 4.0 (free, noncommercial use with attribution). The collector code is source-available under PolyForm Strict 1.0.0. See [Licensing](#licensing).

## Feed files

| File | FortiGate feed type | Contents |
|---|---|---|
| [`fortigate/domains.txt`](fortigate/domains.txt) | Domain Name | **Main feed.** Every gaming domain: unblocked-games sites, discovered mirrors, the UT1 games category, and platform games (Steam, Roblox, Epic and others). |
| [`fortigate/domains-priority.txt`](fortigate/domains-priority.txt) | Domain Name | Unblocked and school-bypass game sites only. Use it on smaller FortiGates that can't hold the main feed. |
| [`fortigate/urls.txt`](fortigate/urls.txt) | FortiGuard Category (URL list) | Path-level entries for hosts that can't be blocked whole: **CDN loaders** (game and proxy loaders hosted in GitHub repos or npm packages and opened through jsDelivr, unpkg, esm.sh, statically or githack, written for every mirror and blocked per owner, repo or package), plus Google Sites and Apps Script pages. |

Raw URLs to give the FortiGate:

```
https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/domains.txt
https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/domains-priority.txt
https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/urls.txt
```

File format: one entry per line, with no comments, schemes or paths (except in `urls.txt`). Registrable domains appear twice, as `example.com` and `*.example.com`, so subdomains match too. If a list grows past `max_lines_per_file` (100,000), it is split into `domains-2.txt`, `domains-3.txt` and so on. Add one connector per part.

## FortiGate setup

The two kinds of feed use **different threat-feed types**:

| File | Threat feed type | Used in |
|---|---|---|
| `domains.txt` / `domains-priority.txt` | **Domain Name** (`set type domain`) | DNS filter |
| `urls.txt` | **FortiGuard Category** (`set type category`), which is the URL-list type | Web filter |

FortiOS has no "URL" feed type. A Domain Name feed only matches whole hostnames, so `urls.txt` won't work as one.

```
config system external-resource
    edit "EdTech Threat Feed Domains"
        set type domain
        set category 199
        set resource "https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/domains.txt"
        set refresh-rate 15
    next
    edit "EdTech Threat Feed Domains WF"
        set type category
        set category 200
        set resource "https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/domains.txt"
        set refresh-rate 15
    next
    edit "EdTech Threat Feed CDNs"
        set type category
        set category 201
        set resource "https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/urls.txt"
        set refresh-rate 15
    next
end
```

| Feed | Type | Used in | Required? |
|---|---|---|---|
| `EdTech Threat Feed Domains` | Domain Name | DNS filter | Yes |
| `EdTech Threat Feed Domains WF` | FortiGuard Category | Web filter (catches devices that get around your DNS, e.g. DNS-over-HTTPS) | Recommended |
| `EdTech Threat Feed CDNs` | FortiGuard Category | Web filter | Yes (needs deep inspection; see below) |

Notes:

* **Every feed needs `set category` and a unique name.** Without a category, FortiOS rejects the entry with *"Must configure category"* (this applies to Domain Name feeds too). Use any number from 192 to 221 that isn't already used by another remote feed; `show system external-resource` lists the ones in use. The number is the ID the DNS and web filter profiles use for that remote category. Two `edit` blocks with the same name overwrite each other.
* `set type url` is not valid (*"command parse error"*). Type `set type ?` at that prompt to see the types your firmware supports.
* To confirm a feed loaded, open *Security Fabric → External Connectors → (feed) → View Entries*. The entry count should match [`docs/latest-run.md`](docs/latest-run.md).

Then, on student policies:

* **DNS filter profile:** under *FortiGuard Category Based Filter → Remote Categories*, set `EdTech Threat Feed Domains` to **Block** (or Redirect to Block Portal).
* **Web filter profile:** under *FortiGuard Category Based Filter → Remote Categories*, set `EdTech Threat Feed CDNs` and `EdTech Threat Feed Domains WF` to **Block**.
* **Deep SSL inspection is recommended for `urls.txt`.** Every entry in it is a path on a shared host, such as `cdn.jsdelivr.net/gh/<owner>/` or `sites.google.com/view/<name>`. With certificate-only inspection the FortiGate sees only the hostname of an HTTPS request, never the path, so these entries can't match. The domain feeds work either way.
* The FortiGate's management interface needs outbound HTTPS to `raw.githubusercontent.com`.
* Entry limits depend on the model. Check *Security Fabric → External Connectors → (feed) → View Entries* and the event log after the first pull. If the main feed is too large for a smaller box, use `domains-priority.txt` instead.

The feed is rebuilt **hourly during school hours** (weekdays 6am–5pm Central) and every 4 hours otherwise. A FortiGate refresh rate of 10–15 minutes keeps up with it.

**`urls.txt` matching:** CDN entries are written as path prefixes, such as `cdn.jsdelivr.net/gh/<owner>/`, so that one entry covers every repo and file beneath it. After the first pull, test one by opening a file under a listed owner, for example a `.svg` from an owner in the feed. If it isn't blocked even with deep inspection on, set `url_entry_style = "wildcard"` in `config/sources.toml`, which writes `.../gh/<owner>/*` instead.

## How it works

Hourly during school hours, and every 4 hours otherwise, `.github/workflows/update-feed.yml` runs `collector/collect.py`. It also runs whenever `seeds/`, `config/` or `collector/` changes. The collector uses only the Python standard library. Each run has five stages:

Before every publish, a safety check fails the run if any allowlisted, CDN-network or hard-coded critical domain (Google/ChromeOS, Microsoft 365, Apple, GitHub and others) is in the output. When that happens, the FortiGates keep the last good feed.

1. **Collect** 14 curated gaming blocklists, normalized from 5 formats.
2. **Discover** new sites from GitHub repo searches and READMEs, 9 student link lists, certificate logs, repositories of known CDN-loader owners, and GitHub code search for loader files. It also **detects new CDN mirrors** by their link shape, confirming them when they serve identical files, and activates them automatically. **urlscan.io** searches find pages that load the web-proxy frameworks' files, and blocked pages teach the collector which **game engines** (GitHub owners loaded through mirror fallback chains) to block on every CDN.
3. **Filter** every link through 8 ordered checks: CDN recognition, path-level platforms, allowlist, non-game services, bare hosting platforms, README hints, test fixtures and already-listed sites.
4. **Verify** each candidate live, fingerprinting it as a game site, web proxy, SVG/HTML loader or tab-cloaked page.
5. **Publish** the three feed files, writing CDN findings for every mirror.

**[docs/how-it-works.md](docs/how-it-works.md)** breaks down every check, with each pattern and threshold. **[docs/latest-run.md](docs/latest-run.md)** is regenerated on every run, and shows how many checks ran, what each one found, and what went into the feed.

## Day-to-day maintenance

| To... | Edit |
|---|---|
| Block a site right now | Add it to `seeds/confirmed.txt` and commit. The workflow runs on push. |
| Block a path on a shared host | Add `host/path` to `seeds/confirmed-urls.txt` |
| Unblock / fix a false positive | Add it to `seeds/allow.txt` (`example.com` exact, `*.example.com` with subdomains) |
| Stop a GitHub owner / npm package being turned into CDN entries | Add it, lowercase, to `seeds/cdn-owner-allow.txt` |
| Handle a newly detected CDN mirror (GitHub issue labelled `new-cdn`) | Already active. Add it to the Chrome URL blocklist, and make it permanent in `seeds/cdn-mirrors.txt` (or `<host> ignore`) |
| Change when a CDN owner is blocked as a whole | `owner_promote_min` in `config/sources.toml` (default 2 confirmed repos) |
| Add a blocklist or aggregator page | `config/sources.toml` |
| See what needs a human decision | [`review/held.txt`](review/held.txt): block (`seeds/confirmed.txt`), dismiss (`seeds/review-dismissed.txt`) or allow (`seeds/allow.txt`). A daily review opens a PR with proposed decisions. |
| See the automatic retry queue | `review/pending.txt` on the [`state` branch](../../tree/state). No action needed. |
| See run stats | [`docs/latest-run.md`](docs/latest-run.md), or the Actions run summary |

`seeds/allow.txt` already exempts Google and ChromeOS services that some community lists include by mistake (`gvt1/2/3.com` for Chrome updates and Play Store, `android.com`, `ggpht.com`, Google analytics and ad domains), core infrastructure (Google, Microsoft, GitHub, CDNs), `.edu`, `.gov` and `.mil`, and classroom tools that look like games (Kahoot, Blooket, Gimkit, Quizizz, Prodigy, IXL, Khan Academy, Code.org, Scratch, Desmos and others). Remove a line to block that site.

Run it locally:

```bash
python3 collector/collect.py                       # full run
python3 collector/collect.py --no-discovery --no-verify   # lists only, ~5 seconds
```

## Measuring FortiGuard coverage (optional)

`tools/fortiguard_coverage.py` asks your FortiGate (REST API, read-only token) how FortiGuard rates a sample of the feed. It reports what percentage is already rated **Games** and what percentage the feed adds on top. It also writes `review/fortiguard-coverage.csv`, which you can use to batch re-rating requests to FortiGuard.

```bash
FGT_HOST=10.0.0.1 FGT_TOKEN=... python3 tools/fortiguard_coverage.py --sample 500 --insecure
```

## Sources and licenses

The feed is built from four kinds of source. Everything is configured in `config/sources.toml`, and every run reports what each source contributed in [`docs/latest-run.md`](docs/latest-run.md).

### 1. Curated blocklists (downloaded every run)

| Source | Tier | License |
|---|---|---|
| [JosuhaSanhueza/BlockList](https://github.com/JosuhaSanhueza/BlockList) (games) | priority | CC BY-NC-SA 4.0 (non-commercial use) |
| [CasCas2/school-gaming-dns-blocklist](https://github.com/CasCas2/school-gaming-dns-blocklist) (mega, classroom, lite) | priority | CC0 |
| [dkorunic/browser-games-blocklist](https://github.com/dkorunic/browser-games-blocklist) | priority | not stated |
| [nuneze54/Network-Lists](https://github.com/nuneze54/Network-Lists) (games) | priority | not stated |
| [marcuccione/pihole-browser-games-blocklist](https://github.com/marcuccione/pihole-browser-games-blocklist) | priority | not stated |
| [bridgerhung/adblock](https://github.com/bridgerhung/adblock) (games) | priority | not stated |
| [panamastem/Pihole-BlockLists-OnlineMinigames](https://github.com/panamastem/Pihole-BlockLists-OnlineMinigames) | priority | not stated |
| [mmcohen-tech/parsa-blocklists](https://github.com/mmcohen-tech/parsa-blocklists) (online games) | priority | MIT |
| [apsbartlettb Game Proxy Blocklist gist](https://gist.github.com/apsbartlettb/26220978c466cdbe0aaed9c63680ea27) | priority, **live-checked first** (stale, many hijacked hosts) | not stated |
| [gjohnpaull/adguard-games-blocklist](https://github.com/gjohnpaull/adguard-games-blocklist) | general | not stated |
| [UT1 blacklists, Université Toulouse Capitole](https://dsi.ut-capitole.fr/blacklists/) (games) | general | CC BY-SA 4.0 |
| [AdguardTeam/HostlistsRegistry](https://github.com/AdguardTeam/HostlistsRegistry) (gaming services) | general | GPL-3.0 |

Whole-platform entries, whole-TLD rules and anything on the allowlist are stripped from these lists. The publish safety check then refuses any release that still contains a protected domain.

### 2. Discovery sources (find sites no list has yet)

Every site found here is fetched and fingerprinted live before it's blocked.

| Source | What it finds | Detail |
|---|---|---|
| **GitHub repository search** | Unblocked-games and proxy projects, with their homepages, GitHub Pages and README links | 14 topics (`unblocked-games`, `unblockedforschool`, `unblockers-for-school`, `school-unblocker`, `gn-math`, `eaglercraft`, `scramjet` and others) plus 3 keyword searches |
| **GitHub organizations** | Services run by the authors of the main web-proxy frameworks | [titaniumnetwork-dev](https://github.com/titaniumnetwork-dev) and [MercuryWorkshop](https://github.com/MercuryWorkshop): every repository's homepage and Pages site |
| **GitHub code search** | Owners nobody has posted yet, through files with the loader signature (full-screen SVGs that embed an iframe or script) | 6 searches. Uses the `CODE_SEARCH_TOKEN` secret. |
| **CDN owner expansion** | New repositories and loader files from GitHub owners already confirmed | GitHub API plus the [jsDelivr data API](https://www.jsdelivr.com/docs/data.jsdelivr.com) |
| **Student link lists** | Mirror links students pass around | [yourworstnightmare1/proxy-list](https://github.com/yourworstnightmare1/proxy-list) (`links.txt`, `unsorted_links.txt`), [wea-f/ByePassHub](https://github.com/wea-f/ByePassHub), [eddy-22 gist](https://gist.github.com/eddy-22/2cdfadfa539cdaccfd0a9e31bf98e6d6), [Carter54git/Ultimate-Catalog-Of-Web-Game-Ports](https://github.com/Carter54git/Ultimate-Catalog-Of-Web-Game-Ports), [bns34/Unblocked-Sites](https://github.com/bns34/Unblocked-Sites), [task4z/unblockedgames](https://github.com/task4z/unblockedgames), [0800WebDev/UBGdir](https://github.com/0800WebDev/UBGdir) |
| **[urlscan.io](https://urlscan.io/) search** | Pages, scanned by anyone, that load proxy framework files or are titled "unblocked games" | 5 searches every 6 hours. Uses the `URLSCAN_API_KEY` secret. |
| **Certificate Transparency** ([crt.sh](https://crt.sh/)) | Brand-new hostnames containing `unblocked`, `ubg`, `gn-math`, `eaglercraft` and others | 9 keywords. Best-effort, and skipped automatically when crt.sh is unreachable. |
| **Pages already blocked** | Game engines (GitHub owners loaded through CDN mirror fallback chains), unknown CDN mirrors, and redirect targets | Script URLs and redirects recorded during live checks |

### 3. Detection and reference intelligence

| Source | Used for |
|---|---|
| [Titanium Network](https://github.com/titaniumnetwork-dev) and [MercuryWorkshop](https://github.com/MercuryWorkshop) framework code (Ultraviolet, Scramjet, bare-mux, Wisp, Epoxy, libcurl-transport), [Rammerhead](https://github.com/binary-person/rammerhead), MasqrProject | Proxy fingerprints: default file paths, code globals and page element IDs |
| [Tranco list](https://tranco-list.eu/) (top 100,000 domains, refreshed weekly) | Popularity guards: discovery never blocks a major site over one game page |
| Published domain-shadowing and subdomain-takeover research ([urlscan.io](https://urlscan.io/blog/2026/04/15/ProxyingTrust/), [Infoblox via Cybersecurity News](https://cybersecuritynews.com/illegal-gambling-websites/amp/), [Brandefense](https://brandefense.io/blog/subdomain-takeover-detection/)) | DNS shadowing signals: CNAME onto free hosting, CNAMEs named after the hostname, subdomain bursts |

### 4. Human decisions

`seeds/` holds hand-confirmed blocks (`confirmed.txt`, `confirmed-urls.txt`, `cdn-owners-block.txt`), the allowlist (`allow.txt`), dismissed review items, and known CDN mirrors. The **daily review** (a scheduled Claude session each school morning) proposes changes to these files as a pull request for a person to approve.

**Not used, by design:** Discord servers, link-dispenser bots and Discord listing sites (Disboard, Discord Me). Using them would mean joining student communities under a false identity and breaking Discord's terms. Their links still reach the feed when they're shared publicly, and engine and framework blocking catches new domains no matter how they're handed out.

## Licensing

| Part | Files | License |
|---|---|---|
| **The feeds** | `fortigate/`, `review/`, `docs/latest-run.md` | [CC BY-NC-SA 4.0](LICENSE-FEED.md): free for any organization to use on its own networks, with attribution, noncommercially |
| **The collector** | Everything else (`collector/`, `tools/`, `config/`, `seeds/`, `.github/`, documentation) | [PolyForm Strict 1.0.0](LICENSE-CODE.md): readable and usable for noncommercial purposes; **no modification, derivative works or redistribution** |
| **Third-party data** | Incorporated into the feeds | Each source's own license; see [THIRD_PARTY.md](THIRD_PARTY.md) |

Copyright (c) 2026 ESU 2. For commercial use, or permission to modify or host the collector, contact ESU 2.
