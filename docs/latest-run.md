# Latest collector run

Run: 2026-11-19 20:40 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 86,937 |
| GitHub repository searches | 28 |
| GitHub repositories examined | 1,537 |
| README files scanned for links | 300 |
| Student link-list pages scanned | 9 |
| Links harvested from link lists | 6,930 |
| Certificate Transparency queries | 9 |
| Certificates examined | 6 |
| CDN owners expanded (repo listings) | 29 |
| CDN owner repositories listed | 608 |
| CDN entry files found in owner repos | 845 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 0 |
| Links examined by the filters | 30,101 |
|   dropped: allowlist | 7,257 |
|   dropped: known non-game service | 714 |
|   dropped: bare hosting-platform domain | 4 |
|   dropped: README link with no game/bypass hint | 10,379 |
|   dropped: CDN file that isn't a page (js/css/img) | 30 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 0 |
| Links with a CDN path shape on unknown hosts | 19 |
| Unknown hosts tested for being a new CDN/mirror | 3 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Live checks performed this run | 2,322 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 410 |
| cdn | dead | 3 |
| cdn | game | 110 |
| cdn | loader | 189 |
| cdn | proxy | 110 |
| host | alive | 1,216 |
| host | dead | 203 |
| host | game | 71 |
| host | loader | 4 |
| host | proxy | 6 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,370 |
| `domains-priority.txt` entries | 24,248 |
| `urls.txt` entries | 1,786 |
| CDN owners blocked at owner level | 20 |
| CDN repos blocked at repo level | 10 |
| npm packages blocked | 6 |
| CDN mirror hosts covered | 16 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 523 |
| cdn | pending | 645 |
| host | confirmed | 680 |
| host | new | 1,049 |
| host | pending | 5,292 |
| url | confirmed | 45 |
| url | new | 10 |
| url | pending | 5 |

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
