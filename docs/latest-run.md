# Latest collector run

Run: 2026-11-19 21:25 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 86,937 |
| GitHub repository searches | 28 |
| GitHub repositories examined | 1,538 |
| README files scanned for links | 300 |
| Student link-list pages scanned | 9 |
| Links harvested from link lists | 6,930 |
| Certificate Transparency queries | 9 |
| Certificates examined | 8 |
| CDN owners expanded (repo listings) | 3 |
| CDN owner repositories listed | 15 |
| CDN entry files found in owner repos | 6 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 100 |
| Links examined by the filters | 14,621 |
|   dropped: allowlist | 2,661 |
|   dropped: known non-game service | 340 |
|   dropped: bare hosting-platform domain | 4 |
|   dropped: README link with no game/bypass hint | 3,592 |
|   dropped: CDN file that isn't a page (js/css/img) | 1 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 2 |
| Links with a CDN path shape on unknown hosts | 10 |
| Unknown hosts tested for being a new CDN/mirror | 3 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 22 |
| Discovered sites held for review: established site, only a sub-page is a game | 0 |
| Live checks performed this run | 1,292 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 5 |
| cdn | game | 1 |
| cdn | loader | 87 |
| cdn | proxy | 6 |
| host | alive | 957 |
| host | dead | 134 |
| host | game | 80 |
| host | loader | 2 |
| host | proxy | 7 |
| url | alive | 7 |
| url | game | 6 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,468 |
| `domains-priority.txt` entries | 24,349 |
| `urls.txt` entries | 3,208 |
| CDN owners blocked at owner level | 21 |
| CDN repos blocked at repo level | 24 |
| npm packages blocked | 6 |
| CDN mirror hosts covered | 16 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 617 |
| cdn | pending | 650 |
| host | confirmed | 749 |
| host | pending | 6,405 |
| url | confirmed | 51 |
| url | pending | 12 |

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
