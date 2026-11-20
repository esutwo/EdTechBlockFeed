# Latest collector run

Run: 2026-11-20 23:37 UTC  
Generated automatically by `collector/collect.py`. See [how-it-works.md](how-it-works.md) for what each check does.

## Checks performed

| Check | Count |
|---|---:|
| Curated lists downloaded | 14 |
| List entries parsed and normalized | 87,001 |
| GitHub repository searches | 30 |
| GitHub repositories examined | 1,713 |
| README files scanned for links | 9 |
| Student link-list pages scanned | 8 |
| Links harvested from link lists | 6,639 |
| Certificate Transparency queries | 9 |
| Certificates examined | 6 |
|   certificate-log source unreachable this run (skipped) | 0 |
| CDN owners expanded (repo listings) | 40 |
| CDN owner repositories listed | 1,317 |
| CDN entry files found in owner repos | 1,487 |
| GitHub code searches for loader files | 6 |
| Loader-candidate files from code search | 588 |
|   code searches that failed (check CODE_SEARCH_TOKEN) | 0 |
| Links examined by the filters | 10,637 |
|   dropped: allowlist | 1,758 |
|   dropped: known non-game service | 43 |
|   dropped: bare hosting-platform domain | 1 |
|   dropped: README link with no game/bypass hint | 15 |
|   dropped: CDN file that isn't a page (js/css/img) | 1 |
|   dropped: CDN owner on allowlist | 0 |
|   dropped: CDN file in a test/fixture folder | 11 |
| urlscan.io searches (proxy framework files, page titles) | 0 |
|   urlscan.io results examined | 0 |
|   skipped as wildcard-DNS noise | 0 |
| Repositories listed from watched GitHub orgs | 135 |
| Script URLs from confirmed pages re-queued for mirror detection | 0 |
| Game engines (GitHub owners) newly confirmed from page scripts | 3 |
| Sites with domain-shadowing DNS signals | 116 |
| Sites re-queued after a fingerprint upgrade | 2,476 |
| Links with a CDN path shape on unknown hosts | 1 |
| Unknown hosts tested for being a new CDN/mirror | 1 |
|   live checks on those hosts | 1 |
|   new CDNs/mirrors confirmed this run | 0 |
| Discovered sites held for review: top-ranked domain | 0 |
| Discovered sites held for review: established site, only a sub-page is a game | 0 |
| Discovered sites held for review: possible domain shadowing | 0 |
| Stalled bypass-list sites blocked as clones of known bypass pages | 122 |
| Stalled bypass-list sites blocked for impersonating a known service | 6 |
| Stalled bypass-list sites held for review (second signal) | 0 |
| Live checks performed this run | 3,000 |

## Live check results

| Entry type | Result | Count |
|---|---|---:|
| cdn | alive | 887 |
| cdn | dead | 13 |
| cdn | game | 211 |
| cdn | loader | 276 |
| cdn | proxy | 113 |
| host | alive | 730 |
| host | dead | 769 |
| host | game | 1 |

## Feed output

| Item | Count |
|---|---:|
| `domains.txt` entries | 84,857 |
| `domains-priority.txt` entries | 24,740 |
| `urls.txt` entries | 5,785 |
| CDN owners blocked at owner level | 65 |
| CDN repos blocked at repo level | 23 |
| npm packages blocked | 6 |
| Game engines blocked at owner level (learned + seeded) | 4 |
| CDN mirror hosts covered | 21 |
| Waiting for a human decision (`review/held.txt`) | 0 |

## Tracked discoveries

| Entry type | Status | Count |
|---|---|---:|
| cdn | confirmed | 1,550 |
| cdn | new | 946 |
| cdn | pending | 900 |
| host | confirmed | 990 |
| host | dismissed | 34 |
| host | new | 5,143 |
| host | pending | 1,371 |
| url | confirmed | 56 |
| url | new | 8 |

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
