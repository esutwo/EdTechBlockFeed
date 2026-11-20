# Latest collector run

Run: 2026-11-20 23:21 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,001 |
| GitHub repository searches | 30 |
| GitHub repositories examined | 1,713 |
| README files scanned for links | 165 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,639 |
| Certificate Transparency queries | 9 |
| Certificates examined | 0 |
| CDN owners expanded (repo listings) | 2 |
| CDN owner repositories listed | 0 |
| CDN entry files found in owner repos | 0 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 588 |
|   code searches that failed (check CODE_SEARCH_TOKEN) | 0 |
| Links examined by the filters | 10,091 |
|   dropped: allowlist | 2,238 |
|   dropped: known non-game service | 159 |
|   dropped: bare hosting-platform domain | 3 |
|   dropped: README link with no game/bypass hint | 217 |
|   dropped: CDN file that isn't a page (js/css/img) | 8 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 10 |
| urlscan.io searches (proxy framework files, page titles) | 5 |
|   urlscan.io results examined | 266 |
|   skipped as wildcard-DNS noise | 227 |
| Repositories listed from watched GitHub orgs | 135 |
| Script URLs from confirmed pages re-queued for mirror detection | 0 |
| Game engines (GitHub owners) newly confirmed from page scripts | 0 |
| Sites with domain-shadowing DNS signals | 117 |
| Sites re-queued after a fingerprint upgrade | 7,553 |
| Links with a CDN path shape on unknown hosts | 3 |
| Unknown hosts tested for being a new CDN/mirror | 2 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 0 |
| Discovered sites held for review: established site, only a sub-page is a game | 0 |
| Discovered sites held for review: possible domain shadowing | 0 |
| Live checks performed this run | 2,696 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 768 |
| cdn | dead | 232 |
| cdn | game | 38 |
| cdn | loader | 150 |
| cdn | proxy | 8 |
| host | alive | 724 |
| host | dead | 751 |
| host | game | 10 |
| host | proxy | 14 |
| url | alive | 1 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,730 |
| `domains-priority.txt` entries | 24,611 |
| `urls.txt` entries | 8,017 |
| CDN owners blocked at owner level | 40 |
| CDN repos blocked at repo level | 48 |
| npm packages blocked | 6 |
| Game engines blocked at owner level (learned + seeded) | 1 |
| CDN mirror hosts covered | 21 |
| Waiting for a human decision (`review/held.txt`) | 0 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 950 |
| cdn | pending | 1,000 |
| host | confirmed | 868 |
| host | dismissed | 26 |
| host | new | 5,169 |
| host | pending | 1,475 |
| url | confirmed | 56 |
| url | new | 7 |
| url | pending | 1 |

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
