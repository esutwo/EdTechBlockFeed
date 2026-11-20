# Latest collector run

Run: 2026-11-20 10:06 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 86,972 |
| GitHub repository searches | 28 |
| GitHub repositories examined | 1,544 |
| README files scanned for links | 91 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,622 |
| Certificate Transparency queries | 9 |
| Certificates examined | 8 |
| CDN owners expanded (repo listings) | 11 |
| CDN owner repositories listed | 162 |
| CDN entry files found in owner repos | 219 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 0 |
| Links examined by the filters | 49,602 |
|   dropped: allowlist | 22,765 |
|   dropped: known non-game service | 811 |
|   dropped: bare hosting-platform domain | 2 |
|   dropped: README link with no game/bypass hint | 15,571 |
|   dropped: CDN file that isn't a page (js/css/img) | 2 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 0 |
| Links with a CDN path shape on unknown hosts | 10 |
| Unknown hosts tested for being a new CDN/mirror | 6 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 3 |
| Discovered sites held for review: established site, only a sub-page is a game | 0 |
| Live checks performed this run | 1,631 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 101 |
| cdn | dead | 4 |
| cdn | game | 8 |
| cdn | loader | 10 |
| cdn | proxy | 8 |
| host | alive | 378 |
| host | dead | 1,112 |
| host | game | 5 |
| host | loader | 4 |
| url | loader | 1 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,637 |
| `domains-priority.txt` entries | 24,518 |
| `urls.txt` entries | 2,781 |
| CDN owners blocked at owner level | 34 |
| CDN repos blocked at repo level | 15 |
| npm packages blocked | 6 |
| CDN mirror hosts covered | 16 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 754 |
| cdn | pending | 949 |
| host | confirmed | 831 |
| host | pending | 6,585 |
| url | confirmed | 56 |
| url | pending | 7 |

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
| josuha-games | 12,799 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,552 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
