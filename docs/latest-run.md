# Latest collector run

Run: 2026-11-25 05:37 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,132 |
| GitHub repository searches | 30 |
| GitHub repositories examined | 1,770 |
| README files scanned for links | 15 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,655 |
| Certificate Transparency queries | 9 |
| Certificates examined | 8 |
|   certificate-log source unreachable this run (skipped) | 0 |
| CDN owners expanded (repo listings) | 17 |
| CDN owner repositories listed | 409 |
| CDN entry files found in owner repos | 598 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 569 |
|   code searches that failed (check CODE_SEARCH_TOKEN) | 0 |
| Links examined by the filters | 18,928 |
|   dropped: allowlist | 4,505 |
|   dropped: known non-game service | 65 |
|   dropped: bare hosting-platform domain | 1 |
|   dropped: README link with no game/bypass hint | 5,581 |
|   dropped: CDN file that isn't a page (js/css/img) | 1 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 10 |
| urlscan.io searches (proxy framework files, page titles) | 0 |
|   urlscan.io results examined | 0 |
|   skipped as wildcard-DNS noise | 0 |
| Repositories listed from watched GitHub orgs | 135 |
| Script URLs from confirmed pages re-queued for mirror detection | 0 |
| Game engines (GitHub owners) newly confirmed from page scripts | 0 |
| Sites with domain-shadowing DNS signals | 0 |
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
| List domains checked in DNS for dead-domain maintenance | 805 |
|   no answer / inconclusive (re-checked later) | 805 |
|   answered 'does not exist' (NXDOMAIN) | 0 |
|   DNS check skipped (resolvers unreachable) | 0 |
| Dead list domains kept out of the feed | 0 |
|   failing, not yet dropped (need 3 checks over 14 days) | 4,727 |
|   came back to life and returned to the feed | 0 |
| Hostnames resolved for proxy-server detection | 0 |
|   servers excluded as shared hosting | 3 |
|   servers excluded by network owner (cloud, CDN, parking, shared) | 1 |
|   proxy server IPs held for review | 1 |
| Live checks performed this run | 0 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 85,263 |
| `domains-priority.txt` entries | 25,162 |
| `urls.txt` entries | 6,202 |
| `proxyips.txt` entries (proxy server IPs) | 20 |
| CDN owners blocked at owner level | 67 |
| CDN repos blocked at repo level | 26 |
| npm packages blocked | 6 |
| Game engines blocked at owner level (learned + seeded) | 8 |
| CDN mirror hosts covered | 21 |
| Waiting for a human decision (`review/held.txt`) | 1 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 1,624 |
| cdn | pending | 19 |
| cdn | rejected | 1,946 |
| host | confirmed | 1,203 |
| host | dismissed | 49 |
| host | pending | 43 |
| host | rejected | 6,647 |
| url | confirmed | 57 |
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
| josuha-games | 12,959 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,552 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
