# Latest collector run

Run: 2026-11-20 00:47 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 86,937 |
| GitHub repository searches | 28 |
| GitHub repositories examined | 1,539 |
| README files scanned for links | 156 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,622 |
| Certificate Transparency queries | 9 |
| Certificates examined | 8 |
| CDN owners expanded (repo listings) | 40 |
| CDN owner repositories listed | 887 |
| CDN entry files found in owner repos | 1,069 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 100 |
| Links examined by the filters | 35,115 |
|   dropped: allowlist | 14,019 |
|   dropped: known non-game service | 509 |
|   dropped: bare hosting-platform domain | 4 |
|   dropped: README link with no game/bypass hint | 9,238 |
|   dropped: CDN file that isn't a page (js/css/img) | 24 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 0 |
| Links with a CDN path shape on unknown hosts | 2 |
| Unknown hosts tested for being a new CDN/mirror | 2 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 6 |
| Discovered sites held for review: established site, only a sub-page is a game | 2 |
| Live checks performed this run | 2,455 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 616 |
| cdn | dead | 228 |
| cdn | game | 38 |
| cdn | loader | 41 |
| cdn | proxy | 32 |
| host | alive | 811 |
| host | dead | 601 |
| host | game | 78 |
| host | loader | 5 |
| host | proxy | 1 |
| url | alive | 4 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,597 |
| `domains-priority.txt` entries | 24,478 |
| `urls.txt` entries | 2,996 |
| CDN owners blocked at owner level | 30 |
| CDN repos blocked at repo level | 19 |
| npm packages blocked | 6 |
| CDN mirror hosts covered | 16 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 728 |
| cdn | pending | 844 |
| host | confirmed | 825 |
| host | pending | 6,582 |
| url | confirmed | 55 |
| url | pending | 8 |

## Lists

| List | Entries |
|---|---:|
| adguard-services-gaming | 231 |
| bridgerhung-games | 150 |
| cascas2-classroom | 54 |
| cascas2-lite | 44 |
| cascas2-mega | 141 |
| dkorunic-browser-games | 1,000 |
| game-proxy-gist | 393 |
| gjohnpaull-games | 35,636 |
| josuha-games | 12,764 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,552 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
