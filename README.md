# EdTechBlockFeed

An automatically maintained **FortiGate threat feed of gaming and "unblocked games" sites**, built for K-12 networks.

Students reach games through sites that are quick to stand up and change often: GitHub Pages, Cloudflare Pages, Vercel or Netlify mirrors, custom domains made to look like schools, and npm packages served from jsDelivr. FortiGuard often rates these as Education, Information Technology, Personal Websites or Unrated, not as Games, so a category block misses them. This repo pulls together curated community blocklists, discovers new sites on its own, checks them live, and publishes plain-text files that a FortiGate polls.

## Feed files

| File | FortiGate feed type | Contents |
|---|---|---|
| [`fortigate/domains.txt`](fortigate/domains.txt) | Domain Name | **Main feed.** Every gaming domain: unblocked-games sites, discovered mirrors, the UT1 games category, and platform games (Steam, Roblox, Epic and others). |
| [`fortigate/domains-priority.txt`](fortigate/domains-priority.txt) | Domain Name | Unblocked and school-bypass game sites only. Use it on smaller FortiGates that can't hold the main feed. |
| [`fortigate/urls.txt`](fortigate/urls.txt) | URL List | URL-level entries for hosts that can't be blocked whole, such as `sites.google.com/view/...` and `cdn.jsdelivr.net/npm/<pkg>`. |

Raw URLs to give the FortiGate:

```
https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/domains.txt
https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/domains-priority.txt
https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/urls.txt
```

File format: one entry per line, with no comments, schemes or paths (except in `urls.txt`). Registrable domains appear twice, as `example.com` and `*.example.com`, so subdomains match too. If a list grows past `max_lines_per_file` (100,000), it is split into `domains-2.txt`, `domains-3.txt` and so on. Add one connector per part.

## FortiGate setup

```
config system external-resource
    edit "EdTech-Games-Domains"
        set type domain
        set resource "https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/domains.txt"
        set refresh-rate 15
    next
    edit "EdTech-Games-URLs"
        set type url
        set resource "https://raw.githubusercontent.com/esutwo/EdTechBlockFeed/main/fortigate/urls.txt"
        set refresh-rate 15
    next
end
```

Then:

* **DNS filter** (student profiles): under *FortiGuard Category Based Filter → Remote Categories*, set `EdTech-Games-Domains` to **Block** (or Redirect to Block Portal).
* **Web filter** (student profiles): under *FortiGuard Category Based Filter → Remote Categories*, set both `EdTech-Games-Domains` and `EdTech-Games-URLs` to **Block**.
* The FortiGate's management interface needs outbound HTTPS to `raw.githubusercontent.com`.
* Entry limits depend on the model. Check *Security Fabric → External Connectors → (feed) → View Entries* and the event log after the first pull. If the main feed is too large for a smaller box, use `domains-priority.txt` instead.

The feed is rebuilt every 2 hours. A refresh rate of 15–60 minutes on the FortiGate is enough.

## How it works

`.github/workflows/update-feed.yml` runs `collector/collect.py` every 2 hours (and on any change to `seeds/`, `config/` or `collector/`). The script uses only the Python standard library and has no third-party dependencies.

1. **Curated lists** (`config/sources.toml → [[lists]]`) are downloaded and normalized from hosts, adblock, plain-domain, UT1 tarball and AdGuard services formats. If a source is down, the last good copy in `data/lists/` is used.
2. **Discovery** finds hosts that no list has yet:
   * **GitHub**: repositories tagged `unblocked-games`, `unblockedforschool`, `gn-math`, `eaglercraft` and similar, plus keyword searches. The collector harvests each repo's homepage, its GitHub Pages URL, and links in its README.
   * **Link aggregators**: lists that students circulate, such as yourworstnightmare1/proxy-list, ByePassHub and the unblocked-sites gists.
   * **Certificate Transparency** (crt.sh): new certificates whose names contain `unblocked`, `ubg`, `gn-math` and similar. This is best-effort, because crt.sh is often slow.
3. **Live verification**: each discovered host is fetched and fingerprinted. Game signals include `unblocked games`, Unity WebGL loaders, Ruffle, EmulatorJS, Eaglercraft, GameDistribution, `games.json`, and well-known titles. Proxy signals include Ultraviolet, Scramjet, Wisp, bare-server and Rammerhead.
   * A match goes into the feed.
   * If a match redirects to another domain, that landing domain is added too.
   * A site that is alive but has no fingerprint goes to `review/pending.txt`.
   * A site that is dead three times in a row is dropped.
4. **Aging**: discovered hosts are re-checked weekly and removed after 60 days without a match. List hosts stay in the feed for as long as a list carries them.
5. **Safety filters**: `seeds/allow.txt` overrides every source. Shared hosting platforms in `seeds/platforms.txt` (github.io, pages.dev and so on) are never blocked as a whole, but their individual subdomains are.

## Day-to-day maintenance

| To... | Edit |
|---|---|
| Block a site right now | Add it to `seeds/confirmed.txt` and commit. The workflow runs on push. |
| Block a path on a shared host | Add `host/path` to `seeds/confirmed-urls.txt` |
| Unblock / fix a false positive | Add it to `seeds/allow.txt` (`example.com` exact, `*.example.com` with subdomains) |
| Add a blocklist or aggregator page | `config/sources.toml` |
| See what needs a human look | `review/pending.txt` |
| See run stats | `data/state.json → stats`, or the Actions run summary |

`seeds/allow.txt` already exempts core infrastructure (Google, Microsoft, GitHub, CDNs), `.edu`, `.gov` and `.mil`, and classroom tools that look like games (Kahoot, Blooket, Gimkit, Quizizz, Prodigy, IXL, Khan Academy, Code.org, Scratch, Desmos and others). Remove a line to block that site.

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

The collector code in this repo is MIT licensed (see `LICENSE`).
