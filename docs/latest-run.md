# Latest collector run

Run: 2026-11-22 16:47 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,056 |
| GitHub repository searches | 30 |
| GitHub repositories examined | 1,733 |
| README files scanned for links | 65 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,649 |
| Certificate Transparency queries | 9 |
| Certificates examined | 0 |
|   certificate-log source unreachable this run (skipped) | 0 |
| CDN owners expanded (repo listings) | 40 |
| CDN owner repositories listed | 999 |
| CDN entry files found in owner repos | 1,102 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 571 |
|   code searches that failed (check CODE_SEARCH_TOKEN) | 0 |
| Links examined by the filters | 35,341 |
|   dropped: allowlist | 9,393 |
|   dropped: known non-game service | 687 |
|   dropped: bare hosting-platform domain | 1 |
|   dropped: README link with no game/bypass hint | 13,733 |
|   dropped: CDN file that isn't a page (js/css/img) | 1 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 10 |
| urlscan.io searches (proxy framework files, page titles) | 5 |
|   urlscan.io results examined | 234 |
|   skipped as wildcard-DNS noise | 204 |
| Repositories listed from watched GitHub orgs | 135 |
| Script URLs from confirmed pages re-queued for mirror detection | 0 |
| Game engines (GitHub owners) newly confirmed from page scripts | 0 |
| Sites with domain-shadowing DNS signals | 56 |
| Sites re-queued after a fingerprint upgrade | 0 |
| Links with a CDN path shape on unknown hosts | 1 |
| Unknown hosts tested for being a new CDN/mirror | 1 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 0 |
| Discovered sites held for review: established site, only a sub-page is a game | 1 |
| Discovered sites held for review: possible domain shadowing | 4 |
| Stalled bypass-list sites blocked as clones of known bypass pages | 2 |
| Stalled bypass-list sites blocked for impersonating a known service | 0 |
| Stalled bypass-list sites held for review (second signal) | 0 |
| Live checks performed this run | 1,932 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 220 |
| cdn | dead | 210 |
| cdn | game | 1 |
| cdn | loader | 1 |
| host | alive | 382 |
| host | dead | 1,079 |
| host | game | 37 |
| host | proxy | 1 |
| url | alive | 1 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 85,062 |
| `domains-priority.txt` entries | 24,958 |
| `urls.txt` entries | 5,909 |
| CDN owners blocked at owner level | 65 |
| CDN repos blocked at repo level | 25 |
| npm packages blocked | 6 |
| Game engines blocked at owner level (learned + seeded) | 4 |
| CDN mirror hosts covered | 21 |
| Waiting for a human decision (`review/held.txt`) | 11 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 1,597 |
| cdn | pending | 1,033 |
| cdn | rejected | 895 |
| host | confirmed | 1,137 |
| host | dismissed | 37 |
| host | pending | 5,842 |
| host | rejected | 758 |
| url | confirmed | 56 |
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
| josuha-games | 12,883 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,552 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
