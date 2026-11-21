# Latest collector run

Run: 2026-11-21 16:34 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,032 |
| GitHub repository searches | 30 |
| GitHub repositories examined | 1,717 |
| README files scanned for links | 70 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,644 |
| Certificate Transparency queries | 9 |
| Certificates examined | 8 |
|   certificate-log source unreachable this run (skipped) | 0 |
| CDN owners expanded (repo listings) | 13 |
| CDN owner repositories listed | 290 |
| CDN entry files found in owner repos | 482 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 571 |
|   code searches that failed (check CODE_SEARCH_TOKEN) | 0 |
| Links examined by the filters | 37,932 |
|   dropped: allowlist | 10,045 |
|   dropped: known non-game service | 531 |
|   dropped: bare hosting-platform domain | 1 |
|   dropped: README link with no game/bypass hint | 15,700 |
|   dropped: CDN file that isn't a page (js/css/img) | 1 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 10 |
| urlscan.io searches (proxy framework files, page titles) | 5 |
|   urlscan.io results examined | 266 |
|   skipped as wildcard-DNS noise | 219 |
| Repositories listed from watched GitHub orgs | 135 |
| Script URLs from confirmed pages re-queued for mirror detection | 0 |
| Game engines (GitHub owners) newly confirmed from page scripts | 0 |
| Sites with domain-shadowing DNS signals | 91 |
| Sites re-queued after a fingerprint upgrade | 0 |
| Links with a CDN path shape on unknown hosts | 1 |
| Unknown hosts tested for being a new CDN/mirror | 1 |
|   live checks on those hosts | 0 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 1 |
| Discovered sites held for review: established site, only a sub-page is a game | 0 |
| Discovered sites held for review: possible domain shadowing | 0 |
| Stalled bypass-list sites blocked as clones of known bypass pages | 0 |
| Stalled bypass-list sites blocked for impersonating a known service | 0 |
| Stalled bypass-list sites held for review (second signal) | 0 |
| Live checks performed this run | 1,612 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 79 |
| cdn | dead | 2 |
| cdn | game | 10 |
| cdn | loader | 3 |
| cdn | proxy | 18 |
| host | alive | 1,290 |
| host | dead | 204 |
| host | game | 6 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,980 |
| `domains-priority.txt` entries | 24,876 |
| `urls.txt` entries | 5,847 |
| CDN owners blocked at owner level | 65 |
| CDN repos blocked at repo level | 24 |
| npm packages blocked | 6 |
| Game engines blocked at owner level (learned + seeded) | 4 |
| CDN mirror hosts covered | 21 |
| Waiting for a human decision (`review/held.txt`) | 9 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 1,593 |
| cdn | pending | 1,932 |
| host | confirmed | 1,091 |
| host | dismissed | 37 |
| host | new | 724 |
| host | pending | 5,766 |
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
| josuha-games | 12,859 |
| marcuccione-browser-games | 91 |
| mmcohen-online-games | 65 |
| nuneze54-games | 2,552 |
| panamastem-minigames | 164 |
| ut1-games | 33,652 |
