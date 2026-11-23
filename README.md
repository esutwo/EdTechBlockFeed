# EdTechBlockFeed

An automatically maintained **FortiGate threat feed of gaming and "unblocked games" sites**, built for K-12 networks.

Students reach games through sites that are quick to stand up and change often: GitHub Pages, Cloudflare Pages, Vercel or Netlify mirrors, custom domains made to look like schools, and npm packages served from jsDelivr. FortiGuard often rates these as Education, Information Technology, Personal Websites or Unrated, not as Games, so a category block misses them. This repo pulls together curated community blocklists, discovers new sites on its own, checks them live, and publishes plain-text files that a FortiGate polls.

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
        set resource "https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/domains.txt"
        set refresh-rate 15
    next
    edit "EdTech Threat Feed Domains"
        set type category
        set category 193
        set resource "https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/domains.txt"
        set refresh-rate 15
    next
    edit "EdTech Threat Feed CDNs"
        set type category
        set category 192
        set resource "https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/urls.txt"
        set refresh-rate 15
    next
end
```

Notes on the URL feed:

* `set category` is required. Without it, FortiOS rejects the entry with *"Must configure category"*. Use any number from 192 to 221 that isn't already used by another remote feed. It's the ID the web filter uses for this remote category.
* `set type url` is not valid (*"command parse error"*). Type `set type ?` at that prompt to see the types your firmware supports.
* To confirm a feed loaded, open *Security Fabric → External Connectors → (feed) → View Entries*. The entry count should match [`docs/latest-run.md`](docs/latest-run.md).

Then, on student policies:

* **DNS filter profile:** under *FortiGuard Category Based Filter → Remote Categories*, set `EdTech-Games-Domains` to **Block** (or Redirect to Block Portal).
* **Web filter profile:** under *FortiGuard Category Based Filter → Remote Categories*, set `EdTech-Games-URLs` to **Block**.
  * Optional: to block the domain list in the web filter too (it catches devices that get around your DNS, for example with DNS-over-HTTPS), add a second `type category` feed (another category number) pointing at `domains.txt`, and block it here as well.
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

Feed contents come from the projects below. Each keeps its own license, and attribution is given here.

| Source | License |
|---|---|
| [JosuhaSanhueza/BlockList](https://github.com/JosuhaSanhueza/BlockList) | CC BY-NC-SA 4.0 (non-commercial use) |
| [CasCas2/school-gaming-dns-blocklist](https://github.com/CasCas2/school-gaming-dns-blocklist) | CC0 |
| [dkorunic/browser-games-blocklist](https://github.com/dkorunic/browser-games-blocklist) | not stated |
| [nuneze54/Network-Lists](https://github.com/nuneze54/Network-Lists) | not stated |
| [gjohnpaull/adguard-games-blocklist](https://github.com/gjohnpaull/adguard-games-blocklist) | not stated |
| [UT1 blacklists, Université Toulouse Capitole](https://dsi.ut-capitole.fr/blacklists/) | CC BY-SA 4.0 |
| [AdguardTeam/HostlistsRegistry](https://github.com/AdguardTeam/HostlistsRegistry) (gaming services) | GPL-3.0 |
| marcuccione, bridgerhung, panamastem, mmcohen-tech lists; apsbartlettb gist | see each repo |

