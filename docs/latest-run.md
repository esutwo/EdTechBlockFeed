# Latest collector run

Run: 2026-11-21 07:51 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,001 |
| GitHub repository searches | 30 |
| GitHub repositories examined | 1,715 |
| README files scanned for links | 44 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,639 |
| Certificate Transparency queries | 9 |
| Certificates examined | 8 |
|   certificate-log source unreachable this run (skipped) | 0 |
| CDN owners expanded (repo listings) | 40 |
| CDN owner repositories listed | 997 |
| CDN entry files found in owner repos | 1,103 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 571 |
|   code searches that failed (check CODE_SEARCH_TOKEN) | 0 |
| Links examined by the filters | 21,843 |
|   dropped: allowlist | 12,187 |
|   dropped: known non-game service | 260 |
|   dropped: bare hosting-platform domain | 1 |
|   dropped: README link with no game/bypass hint | 266 |
|   dropped: CDN file that isn't a page (js/css/img) | 2 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 10 |
| urlscan.io searches (proxy framework files, page titles) | 5 |
|   urlscan.io results examined | 266 |
|   skipped as wildcard-DNS noise | 217 |
| Repositories listed from watched GitHub orgs | 135 |
| Script URLs from confirmed pages re-queued for mirror detection | 0 |
| Game engines (GitHub owners) newly confirmed from page scripts | 0 |
| Sites with domain-shadowing DNS signals | 247 |
| Sites re-queued after a fingerprint upgrade | 0 |
| Links with a CDN path shape on unknown hosts | 1 |
| Unknown hosts tested for being a new CDN/mirror | 1 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 1 |
| Discovered sites held for review: established site, only a sub-page is a game | 2 |
| Discovered sites held for review: possible domain shadowing | 0 |
| Stalled bypass-list sites blocked as clones of known bypass pages | 21 |
| Stalled bypass-list sites blocked for impersonating a known service | 1 |
| Stalled bypass-list sites held for review (second signal) | 0 |
| Live checks performed this run | 1,863 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 359 |
| cdn | dead | 2 |
| cdn | game | 2 |
| host | alive | 1,097 |
| host | dead | 386 |
| host | game | 15 |
| host | loader | 1 |
| host | proxy | 1 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,946 |
| `domains-priority.txt` entries | 24,840 |
| `urls.txt` entries | 5,847 |
| CDN owners blocked at owner level | 65 |
| CDN repos blocked at repo level | 24 |
| npm packages blocked | 6 |
| Game engines blocked at owner level (learned + seeded) | 4 |
| CDN mirror hosts covered | 21 |
| Waiting for a human decision (`review/held.txt`) | 8 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 1,562 |
| cdn | pending | 1,851 |
| host | confirmed | 1,086 |
| host | dismissed | 37 |
| host | new | 2,200 |
| host | pending | 4,271 |
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
