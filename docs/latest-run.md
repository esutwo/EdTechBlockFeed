# Latest collector run

Run: 2026-11-20 21:53 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,001 |
| GitHub repository searches | 28 |
| GitHub repositories examined | 1,555 |
| README files scanned for links | 74 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,639 |
| Certificate Transparency queries | 9 |
| Certificates examined | 6 |
| CDN owners expanded (repo listings) | 2 |
| CDN owner repositories listed | 0 |
| CDN entry files found in owner repos | 0 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 0 |
| Links examined by the filters | 30,196 |
|   dropped: allowlist | 6,352 |
|   dropped: known non-game service | 291 |
|   dropped: bare hosting-platform domain | 1 |
|   dropped: README link with no game/bypass hint | 13,916 |
|   dropped: CDN file that isn't a page (js/css/img) | 1 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 0 |
| Links with a CDN path shape on unknown hosts | 1 |
| Unknown hosts tested for being a new CDN/mirror | 1 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 0 |
| Discovered sites held for review: established site, only a sub-page is a game | 0 |
| Live checks performed this run | 18 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| host | alive | 10 |
| host | dead | 3 |
| host | game | 5 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,702 |
| `domains-priority.txt` entries | 24,583 |
| `urls.txt` entries | 3,131 |
| CDN owners blocked at owner level | 34 |
| CDN repos blocked at repo level | 15 |
| npm packages blocked | 6 |
| CDN mirror hosts covered | 19 |
| Waiting for a human decision (`review/held.txt`) | 0 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 754 |
| cdn | pending | 949 |
| host | confirmed | 843 |
| host | dismissed | 26 |
| host | pending | 6,597 |
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
| josuha-games | 12,828 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,552 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
