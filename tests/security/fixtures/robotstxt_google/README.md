# google/robotstxt fixture cases (Phase-3 unit 4)

`cases.json` holds 28 canonical (robots.txt, user-agent, url, expected) cases
**derived and transformed** from `robots_test.cc` in
[google/robotstxt](https://github.com/google/robotstxt) at commit
`22b355ff855419e6a3ff8ff09c0ad7fdb17116f9` (**Apache-2.0**).

- Not a verbatim file copy: upstream C++ `EXPECT_*` calls were parsed into JSON.
- Cases with empty agent/url were filtered out (they exercise a different code
  path than our `RobotsGate.check(url)` contract).
- 99 resolvable unique cases were found; 28 were sampled evenly across the
  file for breadth.
- **17/28 cases agree with protego; the 11 divergences all come from upstream's
  `GoogleOnly_SystemTest` block** (its own comment: "Google-specific: system
  test"): Google's C++ matcher DENIES there while RFC 9309-style parsers
  (protego and urllib.robotparser alike) ALLOW. Divergent cases are kept in
  the JSON, tagged `protego_matches_google_cpp: false`, and asserted only as a
  pinned divergence list so parser changes make them visible.
- Used by `tests/security/test_robots_protego.py` to pin the protego parser to
  Google's canonical expectations (agreement subset) plus the documented
  divergence list.
