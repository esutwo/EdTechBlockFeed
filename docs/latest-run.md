# Latest collector run

Run: 2026-11-24 00:18 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,098 |
| GitHub repository searches | 30 |
| GitHub repositories examined | 1,746 |
| README files scanned for links | 43 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,654 |
| Certificate Transparency queries | 9 |
| Certificates examined | 6 |
|   certificate-log source unreachable this run (skipped) | 0 |
| CDN owners expanded (repo listings) | 40 |
| CDN owner repositories listed | 1,184 |
| CDN entry files found in owner repos | 1,330 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 569 |
|   code searches that failed (check CODE_SEARCH_TOKEN) | 0 |
| Links examined by the filters | 24,993 |
|   dropped: allowlist | 5,280 |
|   dropped: known non-game service | 388 |
|   dropped: bare hosting-platform domain | 1 |
|   dropped: README link with no game/bypass hint | 8,072 |
|   dropped: CDN file that isn't a page (js/css/img) | 1 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 11 |
| urlscan.io searches (proxy framework files, page titles) | 5 |
|   urlscan.io results examined | 263 |
|   skipped as wildcard-DNS noise | 205 |
| Repositories listed from watched GitHub orgs | 135 |
| Script URLs from confirmed pages re-queued for mirror detection | 0 |
| Game engines (GitHub owners) newly confirmed from page scripts | 0 |
| Sites with domain-shadowing DNS signals | 38 |
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
| Hostnames resolved for proxy-server detection | 849 |
|   servers excluded as shared hosting | 1 |
|   servers excluded by network owner (cloud, CDN, parking, shared) | 8 |
|   proxy server IPs held for review | 3 |
| Live checks performed this run | 2,551 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 821 |
| cdn | dead | 229 |
| cdn | loader | 1 |
| host | alive | 632 |
| host | dead | 859 |
| host | game | 3 |
| host | proxy | 5 |
| url | game | 1 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 85,147 |
| `domains-priority.txt` entries | 25,043 |
| `urls.txt` entries | 5,972 |
| `proxyips.txt` entries (proxy server IPs) | 16 |
| CDN owners blocked at owner level | 65 |
| CDN repos blocked at repo level | 26 |
| npm packages blocked | 6 |
| Game engines blocked at owner level (learned + seeded) | 4 |
| CDN mirror hosts covered | 21 |
| Waiting for a human decision (`review/held.txt`) | 5 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 1,606 |
| cdn | pending | 17 |
| cdn | rejected | 1,929 |
| host | confirmed | 1,168 |
| host | dismissed | 47 |
| host | pending | 5,183 |
| host | rejected | 1,471 |
| url | confirmed | 57 |
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
| josuha-games | 12,925 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,552 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
