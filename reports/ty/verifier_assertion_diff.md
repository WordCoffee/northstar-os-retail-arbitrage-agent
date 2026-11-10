# Independent verifier — every assertion changed for D-006 and D-007

Candidate: `staging-candidate/20261109-1811` (`3f002e0c`), lineage `b372544f` → `1e4c63d0` → `3f002e0c` → `438213b7` → `52f09593`.
Read-only lane: no repo file was modified except this report. Probes and sample `.jsx` files were written under `%TEMP%`.

**Exact ranges used**

- Code fixes: `git diff 1e4c63d0^..1e4c63d0` (all code changes are in `1e4c63d0`; `3f002e0c` adds only `reports/ty/defects.md`, the digest and a 0-byte suite log).
- Defect write-ups: `git show 3f002e0c -- reports/ty/defects.md` → `defects.md:120` (D-006), `defects.md:134` (D-007).

**Assertion accounting, measured, not asserted** (assert lines extracted from `git show 1e4c63d0^:<file>` vs the working tree):

| File | old assert lines | new assert lines | removed | added |
|---|---|---|---|---|
| `Northstar_backend/test_shell_role_contract.py` | 16 | 19 | **0** | **3** |
| `Northstar_backend/test_contract_check.py` | 33 | 33 | **0** | **0** |

`git diff 1e4c63d0^..3f002e0c` over both test files contains exactly **one** deletion line, and it is a signature, not an assertion:

```
-def test_end_to_end_contract_run_on_a_fresh_backend(tmp_path):
+def test_end_to_end_contract_run_on_a_fresh_backend(tmp_path, monkeypatch):
```

No existing assertion in either file was deleted, loosened or re-ordered. Detail per defect below.

---

## D-006 — checker read component names out of comments

### 1. Files and functions touched

- `tools/check-jsx-imports.py` — new module-level regexes `BLOCK_COMMENT`, `LINE_COMMENT` (lines 51–52), new function `strip_comments()` (lines 55–62), and one changed line inside `main()` (line 138).
- `Northstar_backend/test_shell_role_contract.py` — new test `test_the_checker_ignores_a_component_name_inside_a_comment` (lines 82–93), which calls `_checker.strip_comments` from the module loaded at lines 30–33.
- Unchanged in that file: `test_no_undefined_jsx_components` (lines 96–103) still runs the real checker as a subprocess and still asserts `result.returncode == 0`.

### 2. Every assertion / predicate that changed

| file:line (current) | old form | new form | what it proves now vs before |
|---|---|---|---|
| `tools/check-jsx-imports.py:138` | `used = set(JSX_TAG.findall(source)) - REACT_BUILTINS` (was line 124) | `used = set(JSX_TAG.findall(strip_comments(source))) - REACT_BUILTINS` | Before: any capitalised `<Tag` **anywhere in raw text**, including `//` and `/* */` prose, counted as a use. Now: only tags outside comments count. This is the whole fix; it is a relaxation of the *predicate*, not of a test assertion. |
| `tools/check-jsx-imports.py:51` | absent | `BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)` | new predicate input |
| `tools/check-jsx-imports.py:52` | absent | `LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*")` | new predicate input; the look-behind protects only the `://` sequence |
| `tools/check-jsx-imports.py:55–62` | absent | `def strip_comments(source) -> str: return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", source))` | the stripping is unconditional on strings; see residual risk below |
| `Northstar_backend/test_shell_role_contract.py:91` | (test did not exist) | `assert "<Outlet" not in cleaned` | proves a `//` comment naming `<Outlet/>` no longer reaches the tag scan. Proved nothing before. |
| `Northstar_backend/test_shell_role_contract.py:92` | (test did not exist) | `assert "<Ghost" not in cleaned` | same for a `/* … */` comment. Proved nothing before. |
| `Northstar_backend/test_shell_role_contract.py:93` | (test did not exist) | `assert "https://example.com/path" in cleaned, "a URL in a string must survive"` | proves over-stripping does not eat a URL string. Proved nothing before. |

`available = names_from(source)` at `check-jsx-imports.py:137` is **unchanged** and still reads raw source, so the two sides of the comparison are now asymmetric (see residual risk 2).

### 3. Evidence that the checker still catches a genuinely unimported component

Sample tree in `%TEMP%\vfy_d006\run2` laid out as `<root>/tools/check-jsx-imports.py` + `<root>/northstar-os-ui/src/shell/{Bad,CommentOnly}.jsx`, so the **unmodified script** resolved `SRC` to the sample. Real output:

```
checked 2 .jsx files

1 undefined component reference(s):
  shell/Bad.jsx: <PhantomThing>
no unguarded length-then-map renders found
EXIT=1
```

`Bad.jsx` is `export default function Bad() { return <PhantomThing /> }` with no import. `CommentOnly.jsx` carries `// …<Outlet/>…` and `/* <Ghost/> … */` and was **not** reported. Same script, same run: true positive kept, false positive gone.

Before/after on the real tree (old checker from `git show 1e4c63d0^:tools/check-jsx-imports.py`, `SRC` forced to the repo):

```
[old] exit=1   checked 155 .jsx files
               1 undefined component reference(s):
                 shell/WorkspacePanels.jsx: <Outlet>
[new] exit=0   checked 155 .jsx files
               no undefined JSX component references found
```

The suppressed report is `northstar-os-ui/src/shell/WorkspacePanels.jsx:6`:
`// itself, from this one map, instead of letting the shared \`<Outlet/>\` swap` — prose, not a reference.

Repo-wide cost measurement (every `.jsx` line where stripping removes a tag):

```
lines_losing_a_tag=11 files=4
  App.jsx:77 lost=['Route']      :: // <Route> entries were missing, so /hub, /ledger and friends fell through to
  App.jsx:130 lost=['Navigate']  :: // … A bare <Navigate> drops the
  App.jsx:271 lost=['MasterBrainShell'] :: // path not on it fell through to <MasterBrainShell/>. Measured with
  App.jsx:278 lost=['Route']     :: // other path renders the page its <Route> declares …
  App.jsx:283 lost=['ShellLayout'] :: // every room both render inside <ShellLayout> (top nav + side nav + outlet).
  shell/ShellLayout.jsx:4  lost=['SuiteRail']
  shell/ShellLayout.jsx:8  lost=['Outlet']
  shell/ShellLayout.jsx:30 lost=['Outlet']
  shell/WorkspacePanels.jsx:6  lost=['Outlet']
  shell/WorkspacePanels.jsx:13 lost=['Routes']
  studio/components/Fields.jsx:2 lost=['Field']
```

All 11 are line comments. Zero code tags were suppressed in the current tree.

### 4. Verdict — D-006: **EQUIVALENT**

- Not WEAKER as shipped: the only report it suppresses is the `WorkspacePanels.jsx` `<Outlet>` prose false positive (old-checker run above); the repo-wide measurement shows 11/11 suppressed tags are comment prose; and a genuine `<PhantomThing/>` with no import is still reported with exit 1.
- Not STRONGER: the predicate can now miss a real tag in two narrow shapes I could reproduce (below), so it buys no new detection.
- The 2 tests that already pinned the checker (`test_no_undefined_jsx_components:103`, `test_product_designer_imports_what_it_renders:109–110`) are untouched, so the repo-wide gate was not relaxed.

**Residual risk introduced (measured, not hypothetical).** The look-behind in `LINE_COMMENT` protects only `://`. Any other `//` earlier on a line truncates the rest of that line before the scan. Probe on a 1-line file:

```
UrlThenTag.jsx: const p = "a//b"; export default function C() { return <Ghost /> }
  [old checker] used=['Ghost'] missing=['Ghost']      ← caught
  [new checker] used=[]        missing=[]              ← missed
```

The same shape occurs with a protocol-relative URL: `<img src="//cdn.example.com/a.png" /> <Ghost />`. The block-comment regex has a sibling gap: a `/*` inside a string opens a comment that closes at the next `*/`, swallowing everything between —

```
two_block_markers_in_strings: used=[] missing=[]   (a real <Ghost/> between the two strings is missed)
```

Today both cost **0** real detections (0/155 files), so they are disclosed edges rather than a reason to reject, but a reviewer should know the checker is now string-blind on `//` and `/*`.

**Residual, pre-existing (not introduced by this commit).** `names_from(source)` still reads raw source, so an import line mentioned only in a comment counts as "available" and can mask a genuinely missing import. That asymmetry predates `1e4c63d0` and is unchanged by it.

---

## D-007 — contract test depended on another module's cache

### 1. Files and functions touched

- `Northstar_backend/test_contract_check.py` — `test_end_to_end_contract_run_on_a_fresh_backend` (lines 98–143): signature gains `monkeypatch`; lines 99–111 seed a one-candidate cache and point `SCANNER_SEARCH_CACHE_PATH` at it; `import json` added at line 19.
- `Northstar_backend/test_coverage_report.py` — same commit, adjacent (not D-007's test): `_WATCHED`/`_PRE_IMPORT_ENV` added (lines 22–25) and `tearDownModule()` now restores `_PRE_IMPORT_ENV` (line 61) instead of the post-import `_ENV`. This is the other half of the order-dependence repair; it changes no assertion (`git diff` shows 8 insertions / 4 deletions, all env bookkeeping).

### 2. Every assertion that changed

| file:line (current) | old form | new form | what it proves now vs before |
|---|---|---|---|
| `test_contract_check.py:98` | `def test_end_to_end_contract_run_on_a_fresh_backend(tmp_path):` | `def test_end_to_end_contract_run_on_a_fresh_backend(tmp_path, monkeypatch):` | signature only — pytest's undo of the env change |
| `test_contract_check.py:102–110` | (absent) | `cache = tmp_path / "scanner-search-cache.json"` … `write_text(json.dumps({... "products": [{"asin": "B0TEST00001", ...}]}))` | fixture only: the test supplies the candidate it measures |
| `test_contract_check.py:111` | (absent) | `monkeypatch.setenv("SCANNER_SEARCH_CACHE_PATH", str(cache))` | fixture only, reverted by `monkeypatch` after the test |
| `test_contract_check.py:115–123` | `assert result["count"] == 29` … `assert "row(s) under 'evaluated'" in rows["product-finder"]["evidence"]` | **byte-identical** | nothing changed: endpoint identity, verdict and the rows-under-`evaluated` evidence requirement are the same strings |

Mechanical confirmation: 33 assert lines old, 33 new, `identical set: True`, `only-in-old: []`, `only-in-new: []`. The whole `git diff` hunk shows the assertions as context lines, not `-`/`+`.

### 3. Evidence that the endpoint is still tested (not stubbed out)

`tools/contract_check.py:277–280` builds the evidence string only from a non-empty list of dicts:

```python
for key, value in payload.items():
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return True, f"{len(value)} row(s) under {key!r}"
```

So `assert "row(s) under 'evaluated'" in …` cannot pass on an empty `evaluated`. I ran `cc.run(mode="in_process", db_dir=<tmp>)` twice, changing only the cache contents:

```
RESULT [seeded] verdict=pass evidence="1 row(s) under 'evaluated'"                        assertion_pass=True
RESULT [empty ] verdict=pass evidence='6 measured field(s) (passed,evaluated,candidate_count,…)' assertion_pass=False
```

The empty-cache case has `evaluated: []`, the endpoint's own verdict is still `"pass"`, and the assertion fails — i.e. the assertion is load-bearing, and the seeding is the only thing that supplies the measurement.

The row is produced by the real filter, not echoed from the fixture. `GET /api/products/finder` in-process with the seeded cache:

```
HTTP 200   evaluated_len 1   asin B0TEST00001
row_keys ['asin','name','price','product_url','universal_filter_passed','universal_filter_reasons']
```

which matches `Northstar_backend/main.py:2908` (`cache = amazon_search.load_cached_candidates()`), `:2912` (merge), `:2924` (`evaluated = filt.filter_all(merged, keep_rejected=True)`). The cached candidate is scored through `UniversalProductFilter`.

The pair that used to fail now passes together:

```
python -m pytest -q Northstar_backend/test_coverage_report.py Northstar_backend/test_contract_check.py
24 passed, 1 warning in 7.95s
```

— the same "24 passed" the defect note claims at `defects.md:141`.

### 4. Verdict — D-007: **STRONGER**

- Identical assertions (33/33, byte-identical), so nothing was loosened to get green.
- The pass no longer depends on which module ran earlier: the input is written by the test into its own `tmp_path` and the env override is reverted by `monkeypatch`.
- The strengthened part is real, not cosmetic: with an empty cache the endpoint still says `verdict=pass`, and only the unchanged evidence assertion catches it; with the seeded cache the same assertion is satisfied by a row that went through `filter_all`.
- What it still does not prove: that the *real* scanner cache shape is what the scanner writes — the cache here is a synthetic fixture. That coverage lives elsewhere (`Northstar_backend/test_product_finder.py:175`, `test_product_finder_api.py:82`), and this test never claimed it.

---

## What I could not establish

1. **A stored suite result for this candidate.** `3f002e0c` adds `reports/ty/_fullsuite_candidate8_20261109.txt`, and `git cat-file -s` reports **0 bytes**. The `52f09593` message claims "suite 7329 passed" for *main*, not for `3f002e0c`, and I did not run the full suite (another lane owns that run). So "candidate 8 is green" is not evidenced by an artefact inside this commit.
2. **The original order-dependent failure reproduced from old code.** I did not check out or run the pre-fix tree, so the defect's "after `test_coverage_report.py` it failed" is established here by mechanism (empty-cache probe + `test_network_guard.py:24–26` setting an empty temp cache via `setdefault`) rather than by an observed red run of the old pair.
3. **The true frequency of the D-006 blind spots in future code.** Measured 0/155 files today; that is a current-tree measurement, not a guarantee.
4. **Whether the new D-006 test would catch an over-stripping `strip_comments`.** It asserts only that two comment names vanish and one URL survives; `export default function A() { return <Real /> }` is in the sample but never asserted. A `strip_comments` that returned nothing but the URL would pass all three asserts. The checker's own subprocess test (`test_no_undefined_jsx_components:103`) and the repo-wide run are what actually hold the line, and they do.
