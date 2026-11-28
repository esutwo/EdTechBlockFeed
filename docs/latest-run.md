# Latest collector run

Run: 2026-11-28 01:00 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,239 |
| GitHub repository searches | 30 |
| GitHub repositories examined | 1,787 |
| README files scanned for links | 37 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,659 |
| Certificate Transparency queries | 9 |
| Certificates examined | 8 |
|   certificate-log source unreachable this run (skipped) | 0 |
| CDN owners expanded (repo listings) | 40 |
| CDN owner repositories listed | 1,243 |
| CDN entry files found in owner repos | 1,340 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 569 |
|   code searches that failed (check CODE_SEARCH_TOKEN) | 0 |
| Links examined by the filters | 21,514 |
|   dropped: allowlist | 4,367 |
|   dropped: known non-game service | 280 |
|   dropped: bare hosting-platform domain | 3 |
|   dropped: README link with no game/bypass hint | 6,250 |
|   dropped: CDN file that isn't a page (js/css/img) | 1 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 12 |
| urlscan.io searches (proxy framework files, page titles) | 0 |
|   urlscan.io results examined | 0 |
|   skipped as wildcard-DNS noise | 0 |
| Repositories listed from watched GitHub orgs | 135 |
| Script URLs from confirmed pages re-queued for mirror detection | 0 |
| Game engines (GitHub owners) newly confirmed from page scripts | 0 |
| Sites with domain-shadowing DNS signals | 65 |
| Sites re-queued after a fingerprint upgrade | 0 |
| Links with a CDN path shape on unknown hosts | 0 |
| Unknown hosts tested for being a new CDN/mirror | 0 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 0 |
| Discovered sites held for review: established site, only a sub-page is a game | 4 |
| Discovered sites held for review: possible domain shadowing | 0 |
| Stalled bypass-list sites blocked as clones of known bypass pages | 0 |
| Stalled bypass-list sites blocked for impersonating a known service | 0 |
| Stalled bypass-list sites held for review (second signal) | 0 |
| List domains checked in DNS for dead-domain maintenance | 1,274 |
|   no answer / inconclusive (re-checked later) | 759 |
|   answered 'does not exist' (NXDOMAIN) | 514 |
|   DNS check skipped (resolvers unreachable) | 0 |
| Dead list domains kept out of the feed | 0 |
|   failing, not yet dropped (need 3 checks over 14 days) | 4,726 |
|   came back to life and returned to the feed | 0 |
| Hostnames resolved for proxy-server detection | 720 |
|   servers excluded as shared hosting | 3 |
|   servers excluded by network owner (cloud, CDN, parking, shared) | 1 |
|   proxy server IPs held for review | 0 |
| Live checks performed this run | 206 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 11 |
| cdn | dead | 1 |
| cdn | game | 14 |
| cdn | loader | 8 |
| cdn | proxy | 18 |
| host | alive | 120 |
| host | dead | 7 |
| host | game | 19 |
| host | loader | 2 |
| host | proxy | 2 |
| url | dead | 1 |
| url | game | 3 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 85,413 |
| `domains-priority.txt` entries | 25,360 |
| `urls.txt` entries | 6,236 |
| `proxyips.txt` entries (proxy server IPs) | 21 |
| CDN owners blocked at owner level | 67 |
| CDN repos blocked at repo level | 26 |
| npm packages blocked | 6 |
| Game engines blocked at owner level (learned + seeded) | 12 |
| CDN mirror hosts covered | 21 |
| Waiting for a human decision (`review/held.txt`) | 40 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 1,634 |
| cdn | pending | 2 |
| cdn | rejected | 1,972 |
| host | confirmed | 1,267 |
| host | dismissed | 49 |
| host | pending | 30 |
| host | rejected | 6,705 |
| url | confirmed | 60 |
| url | pending | 1 |
| url | rejected | 8 |

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
| josuha-games | 13,031 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,587 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
