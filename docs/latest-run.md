# Latest collector run

Run: 2026-11-24 00:58 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,098 |
| GitHub repository searches | 30 |
| GitHub repositories examined | 1,746 |
| README files scanned for links | 17 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,654 |
| Certificate Transparency queries | 9 |
| Certificates examined | 6 |
|   certificate-log source unreachable this run (skipped) | 0 |
| CDN owners expanded (repo listings) | 40 |
| CDN owner repositories listed | 1,084 |
| CDN entry files found in owner repos | 1,094 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 569 |
|   code searches that failed (check CODE_SEARCH_TOKEN) | 0 |
| Links examined by the filters | 10,652 |
|   dropped: allowlist | 1,879 |
|   dropped: known non-game service | 40 |
|   dropped: bare hosting-platform domain | 1 |
|   dropped: README link with no game/bypass hint | 70 |
|   dropped: CDN file that isn't a page (js/css/img) | 1 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 10 |
| urlscan.io searches (proxy framework files, page titles) | 0 |
|   urlscan.io results examined | 0 |
|   skipped as wildcard-DNS noise | 0 |
| Repositories listed from watched GitHub orgs | 135 |
| Script URLs from confirmed pages re-queued for mirror detection | 0 |
| Game engines (GitHub owners) newly confirmed from page scripts | 0 |
| Sites with domain-shadowing DNS signals | 44 |
| Sites re-queued after a fingerprint upgrade | 0 |
| Links with a CDN path shape on unknown hosts | 0 |
| Unknown hosts tested for being a new CDN/mirror | 0 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 0 |
| Discovered sites held for review: established site, only a sub-page is a game | 0 |
| Discovered sites held for review: possible domain shadowing | 0 |
| Stalled bypass-list sites blocked as clones of known bypass pages | 0 |
| Stalled bypass-list sites blocked for impersonating a known service | 0 |
| Stalled bypass-list sites held for review (second signal) | 0 |
| Hostnames resolved for proxy-server detection | 1 |
|   servers excluded as shared hosting | 1 |
|   servers excluded by network owner (cloud, CDN, parking, shared) | 1 |
|   proxy server IPs held for review | 2 |
| Live checks performed this run | 1,501 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 1 |
| host | alive | 337 |
| host | dead | 1,161 |
| host | game | 1 |
| url | alive | 1 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 85,148 |
| `domains-priority.txt` entries | 25,044 |
| `urls.txt` entries | 5,972 |
| `proxyips.txt` entries (proxy server IPs) | 19 |
| CDN owners blocked at owner level | 65 |
| CDN repos blocked at repo level | 26 |
| npm packages blocked | 6 |
| Game engines blocked at owner level (learned + seeded) | 4 |
| CDN mirror hosts covered | 21 |
| Waiting for a human decision (`review/held.txt`) | 4 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 1,606 |
| cdn | pending | 18 |
| cdn | rejected | 1,929 |
| host | confirmed | 1,169 |
| host | dismissed | 47 |
| host | pending | 3,688 |
| host | rejected | 2,966 |
| url | confirmed | 57 |
| url | pending | 7 |
| url | rejected | 1 |

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
| josuha-games | 12,925 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,552 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
