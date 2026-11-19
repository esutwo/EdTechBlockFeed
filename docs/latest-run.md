# Latest collector run

Run: 2026-11-19 19:31 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 86,915 |
| GitHub repository searches | 28 |
| GitHub repositories examined | 1,535 |
| README files scanned for links | 300 |
| Student link-list pages scanned | 9 |
| Links harvested from link lists | 6,930 |
| Certificate Transparency queries | 9 |
| Certificates examined | 6 |
| CDN owners expanded (repo listings) | 0 |
| CDN owner repositories listed | 0 |
| CDN entry files found in owner repos | 0 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 0 |
| Links examined by the filters | 50,322 |
|   dropped: allowlist | 22,565 |
|   dropped: known non-game service | 677 |
|   dropped: bare hosting-platform domain | 3 |
|   dropped: README link with no game/bypass hint | 14,461 |
|   dropped: CDN file that isn't a page (js/css/img) | 3 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 0 |
| Live checks performed this run | 1,846 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 13 |
| cdn | dead | 219 |
| cdn | game | 5 |
| cdn | loader | 98 |
| cdn | proxy | 11 |
| host | alive | 727 |
| host | dead | 629 |
| host | game | 81 |
| host | loader | 8 |
| host | proxy | 10 |
| url | alive | 31 |
| url | game | 12 |
| url | loader | 2 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,225 |
| `domains-priority.txt` entries | 24,091 |
| `urls.txt` entries | 1,270 |
| CDN owners blocked at owner level | 4 |
| CDN repos blocked at repo level | 25 |
| npm packages blocked | 6 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 114 |
| cdn | pending | 232 |
| host | confirmed | 595 |
| host | new | 2,444 |
| host | pending | 3,873 |
| url | confirmed | 45 |
| url | new | 7 |
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
| josuha-games | 12,742 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,552 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
