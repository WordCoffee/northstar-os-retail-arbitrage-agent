# Gitleaks triage - unblocking the `reports/` freeze

Generated: 2026-11-07 07:41  
Lane: SECRET-SCAN TRIAGE (read-only analysis; writes limited to `.gitleaks.toml`, this file and `reports/ty/gitleaks_triage.json`)  
Scanner: `gitleaks 8.30.1` (installed natively, no binary vendored)  
Machine inventory: `reports/ty/gitleaks_triage.json`

**No secret value appears in this report or in the JSON inventory.** Every finding was
produced with `--redact` (100 %), so the scanner emitted `REDACTED` in place of each
secret. Values were never read, printed or written; no `.env`, key file or credential
store was opened for inspection.

---

## 1. Verdict

| Item | Value |
|---|---|
| Total findings | 326 |
| `test_fixture` | 250 |
| `likely_real` | 67 |
| `unknown` | 9 |
| `placeholder` | 0 |
| Allowlisted by this pass | 170 |
| Findings still reported after allowlist | 156 |
| Findings already in git history | 5 |
| **Credentials the owner must rotate** | **3** |

**`reports/` is unblocked.** Before this pass, the only findings under `reports/` that
were neither gitignored nor allowlisted were 170 hits in two scraped Walmart capture
files. Those are now narrowly allowlisted (section 3). The single remaining `reports/`
hit lives in `reports/video_scan/huggingface.jsonl`, which git ignores, so it can never
reach a commit.

A second, more important result: the scan found **5 real-looking credentials that are
already committed** in two root-level chat exports. Those files are tracked, and all 5
hits reproduce in a git-history scan. Rotating them is the only urgent action here.

## 2. What was scanned

Working tree, redacted, non-git mode:

```
gitleaks detect --no-git --redact --report-format json \
  --report-path %TEMP%\gitleaks_triage\repo_scan.json \
  --log-level error --no-banner --max-target-megabytes 20
```

Git history, redacted (completed in 24 s, well under the 5-minute cap):

```
gitleaks detect --redact --report-format json \
  --report-path %TEMP%\gitleaks_triage\history_scan.json \
  --log-level error --no-banner
```

The existing `.gitleaks.toml` was in force for both runs (`extend.useDefault = true`),
so the 326 findings are what survives the allowlists that were already present.

### Findings by rule

| Rule | Count |
|---|---|
| `generic-api-key` | 299 |
| `rapidapi-access-token` | 2 |
| `stripe-access-token` | 1 |
| `github-pat` | 2 |
| `huggingface-access-token` | 4 |
| `gcp-api-key` | 18 |

### Findings by exposure

| Exposure | Count | Meaning |
|---|---|---|
| `tracked-committed` | 5 | File is in git. The value is already in history. |
| `untracked-committable` | 170 | Untracked but not ignored: a `git add -A` would commit it. This was the `reports/` blocker. |
| `gitignored` | 151 | Never committed. Local at-rest only. |

## 3. `.gitleaks.toml` changes

The existing file was **extended, not replaced**. Two allowlist blocks were appended,
both scoped to `reports/_wm_beeswax.html` and `reports/_wm_unpaper.html` only, and both
requiring a path match **and** a regex match (`condition = "AND"`), so neither can mask a
differently shaped secret if one ever lands in those files. This follows the precedent
already set by the `fixtures/brightdata_costco/` entry for scraped third-party HTML.

| Allowlist | Matches | Findings covered | Why it is a false positive |
|---|---|---|---|
| Scraped Walmart page config keys | `modularStackKey`, `endpointReviewImageUploadApiKey` | 152 | The two files are saved Walmart product pages. These are Walmart's own front-end config keys in inline page JS, not Northstar credentials. |
| Walmart's Google API keys | `AIza[0-9A-Za-z_-]{35}` | 18 | Google keys published by Walmart in its own public page source (head `preconnect` / maps bootstrap). Third-party, not ours, not rotatable by us. |

Result: `gitleaks detect --no-git --redact` drops from **326 to 156** findings, the 170
Walmart-capture hits disappear, and **no `likely_real` or `unknown` finding was masked**
(re-verified after the change: all 5 chat-export hits still report).

### Deliberately NOT allowlisted

Findings in `.env`, `Northstar_backend/.env`, `northstar-os-retail-arbitrage-agent/.env`,
`.playwright-mcp/`, `venv-crew/`, `exports/` and `reports/video_scan/huggingface.jsonl`
were left un-allowlisted even though most are harmless. `git check-ignore` confirms every
one of those paths is ignored, so they never reach a commit, and allowlisting an ignored
tree would hide a future real secret dropped there. Excluding them by directory would also
have violated the narrow-allowlist rule.

## 4. Rotate now - 3 credentials

These are the only findings that are both credential-shaped and already committed. The
git-history scan reproduces 5 hits across 3 distinct credentials, in commits
`a299d6e9` (2026-08-11) and `21aed4e3` (2026-09-11).

| Credential | Where | Exposure | Action |
|---|---|---|---|
| SCAVIO_API_KEY | `FirstNorthstarautomationchat.md:1143,1291` | git-tracked, present in history | ROTATE key, then purge history |
| BRIGHTDATA_API_KEY | `FirstNorthstarautomationchat.md:1148,1296` | git-tracked, present in history | ROTATE key, then purge history |
| GitHub personal access token | `autothink-ui-chat-export.md:7852` | git-tracked, present in history | REVOKE token, then purge history |

Why these are judged real rather than fixtures:

- `FirstNorthstarautomationchat.md` embeds two fenced file blocks, one labelled
  `.env.example` and one labelled `.env`. Values in those blocks trip the
  `generic-api-key` rule, while the tracked `.env.example` on disk does not trip it, so
  the transcript holds values that differ from the committed placeholder. Entropy 3.99
  and 3.61 is consistent with a 32-character hex provider key, which is the shape of a
  Bright Data key.
- `autothink-ui-chat-export.md` contains assistant text identifying the value as "a live
  GitHub Personal Access Token exposed on screen". The match is `github-pat` at entropy
  4.85, and a `ghp_` token is 40 characters pasted into a tracked file.

Rotation itself is an operator action. Nothing was rotated, revoked or edited here.
Because both files are tracked, deleting the lines does not remove the value from history:
purge history (for example with `git filter-repo`) *after* rotating, or the old value
stays readable in the old commits.

## 5. Findings already in git history

| `path:line` | Rule | Class |
|---|---|---|
| `autothink-ui-chat-export.md:7852` | `github-pat` | likely_real |
| `FirstNorthstarautomationchat.md:1143` | `generic-api-key` | likely_real |
| `FirstNorthstarautomationchat.md:1148` | `generic-api-key` | likely_real |
| `FirstNorthstarautomationchat.md:1291` | `generic-api-key` | likely_real |
| `FirstNorthstarautomationchat.md:1296` | `generic-api-key` | likely_real |

## 6. Every `likely_real` finding (67)

Values redacted. `gitignored` means the credential is live on disk but was never
committed and is not part of the freeze.

| `path:line` | Rule | Class | Entropy | Exposure |
|---|---|---|---|---|
| `.env:2` | `generic-api-key` | likely_real | 4.03 | gitignored |
| `.env:7` | `generic-api-key` | likely_real | 3.52 | gitignored |
| `.env:10` | `generic-api-key` | likely_real | 3.83 | gitignored |
| `.env:12` | `generic-api-key` | likely_real | 3.94 | gitignored |
| `.env:16` | `generic-api-key` | likely_real | 4.31 | gitignored |
| `.env:17` | `generic-api-key` | likely_real | 3.66 | gitignored |
| `.env:38` | `generic-api-key` | likely_real | 3.52 | gitignored |
| `.env:40` | `generic-api-key` | likely_real | 4.85 | gitignored |
| `.env:59` | `rapidapi-access-token` | likely_real | 4.13 | gitignored |
| `.env:72` | `generic-api-key` | likely_real | 4.71 | gitignored |
| `.env:73` | `generic-api-key` | likely_real | 3.68 | gitignored |
| `.env:74` | `generic-api-key` | likely_real | 3.73 | gitignored |
| `.env:75` | `generic-api-key` | likely_real | 4.79 | gitignored |
| `.env:76` | `generic-api-key` | likely_real | 4.14 | gitignored |
| `.env:80` | `generic-api-key` | likely_real | 4.76 | gitignored |
| `.env:81` | `generic-api-key` | likely_real | 5.09 | gitignored |
| `.env:82` | `generic-api-key` | likely_real | 4.57 | gitignored |
| `.env:83` | `generic-api-key` | likely_real | 4.32 | gitignored |
| `.env:84` | `generic-api-key` | likely_real | 4.61 | gitignored |
| `.env:89` | `generic-api-key` | likely_real | 4.56 | gitignored |
| `.env:95` | `generic-api-key` | likely_real | 4.21 | gitignored |
| `.env:98` | `stripe-access-token` | likely_real | 4.09 | gitignored |
| `.env:100` | `generic-api-key` | likely_real | 3.7 | gitignored |
| `.env:103` | `generic-api-key` | likely_real | 4.85 | gitignored |
| `.env:109` | `generic-api-key` | likely_real | 4.77 | gitignored |
| `.playwright-mcp/console-2026-09-30T21-27-17-603Z.log:3192` | `generic-api-key` | likely_real | 4.12 | gitignored |
| `.playwright-mcp/console-2026-09-30T21-27-17-603Z.log:3201` | `generic-api-key` | likely_real | 4.12 | gitignored |
| `.playwright-mcp/console-2026-09-30T21-47-01-126Z.log:4` | `generic-api-key` | likely_real | 4.12 | gitignored |
| `.playwright-mcp/console-2026-09-30T21-47-01-126Z.log:12` | `generic-api-key` | likely_real | 4.12 | gitignored |
| `.playwright-mcp/console-2026-09-30T21-47-01-126Z.log:28` | `generic-api-key` | likely_real | 4.12 | gitignored |
| `.playwright-mcp/console-2026-09-30T21-47-01-126Z.log:40` | `generic-api-key` | likely_real | 4.12 | gitignored |
| `.playwright-mcp/page-2026-09-30T07-59-28-867Z.yml:19` | `generic-api-key` | likely_real | 4.77 | gitignored |
| `.playwright-mcp/page-2026-10-04T22-58-06-176Z.yml:88` | `generic-api-key` | likely_real | 5.32 | gitignored |
| `.playwright-mcp/page-2026-10-04T22-59-10-633Z.yml:88` | `generic-api-key` | likely_real | 5.33 | gitignored |
| `.playwright-mcp/page-2026-10-04T22-59-25-154Z.yml:88` | `generic-api-key` | likely_real | 5.3 | gitignored |
| `.playwright-mcp/page-2026-10-04T22-59-33-461Z.yml:88` | `generic-api-key` | likely_real | 5.33 | gitignored |
| `.playwright-mcp/page-2026-10-04T23-01-29-616Z.yml:88` | `generic-api-key` | likely_real | 5.33 | gitignored |
| `.playwright-mcp/page-2026-10-04T23-23-38-289Z.yml:104` | `generic-api-key` | likely_real | 5.31 | gitignored |
| `.playwright-mcp/page-2026-10-04T23-27-21-065Z.yml:108` | `generic-api-key` | likely_real | 5.3 | gitignored |
| `autothink-ui-chat-export.md:7852` | `github-pat` | likely_real | 4.85 | tracked-committed |
| `exports/northstar_full_build_20261024/autothink-ui-chat-export.md:7852` | `github-pat` | likely_real | 4.85 | gitignored |
| `exports/northstar_full_build_20261024/FirstNorthstarautomationchat.md:1143` | `generic-api-key` | likely_real | 3.99 | gitignored |
| `exports/northstar_full_build_20261024/FirstNorthstarautomationchat.md:1148` | `generic-api-key` | likely_real | 3.61 | gitignored |
| `exports/northstar_full_build_20261024/FirstNorthstarautomationchat.md:1291` | `generic-api-key` | likely_real | 3.99 | gitignored |
| `exports/northstar_full_build_20261024/FirstNorthstarautomationchat.md:1296` | `generic-api-key` | likely_real | 3.61 | gitignored |
| `FirstNorthstarautomationchat.md:1143` | `generic-api-key` | likely_real | 3.99 | tracked-committed |
| `FirstNorthstarautomationchat.md:1148` | `generic-api-key` | likely_real | 3.61 | tracked-committed |
| `FirstNorthstarautomationchat.md:1291` | `generic-api-key` | likely_real | 3.99 | tracked-committed |
| `FirstNorthstarautomationchat.md:1296` | `generic-api-key` | likely_real | 3.61 | tracked-committed |
| `Northstar_backend/.env:11` | `generic-api-key` | likely_real | 3.99 | gitignored |
| `Northstar_backend/.env:17` | `generic-api-key` | likely_real | 3.73 | gitignored |
| `Northstar_backend/.env:21` | `generic-api-key` | likely_real | 3.73 | gitignored |
| `Northstar_backend/.env:26` | `generic-api-key` | likely_real | 3.83 | gitignored |
| `Northstar_backend/.env:29` | `generic-api-key` | likely_real | 3.94 | gitignored |
| `Northstar_backend/.env:33` | `generic-api-key` | likely_real | 3.73 | gitignored |
| `Northstar_backend/.env:36` | `generic-api-key` | likely_real | 4.75 | gitignored |
| `Northstar_backend/.env:39` | `generic-api-key` | likely_real | 4.31 | gitignored |
| `Northstar_backend/.env:44` | `generic-api-key` | likely_real | 3.66 | gitignored |
| `Northstar_backend/.env:66` | `rapidapi-access-token` | likely_real | 4.13 | gitignored |
| `Northstar_backend/.env:77` | `generic-api-key` | likely_real | 4.76 | gitignored |
| `Northstar_backend/.env:78` | `generic-api-key` | likely_real | 5.09 | gitignored |
| `Northstar_backend/.env:79` | `generic-api-key` | likely_real | 4.57 | gitignored |
| `Northstar_backend/.env:80` | `generic-api-key` | likely_real | 4.32 | gitignored |
| `Northstar_backend/.env:81` | `generic-api-key` | likely_real | 4.61 | gitignored |
| `Northstar_backend/.env:84` | `generic-api-key` | likely_real | 4.21 | gitignored |
| `northstar-os-retail-arbitrage-agent/.env:2` | `generic-api-key` | likely_real | 3.99 | gitignored |
| `northstar-os-retail-arbitrage-agent/.env:7` | `generic-api-key` | likely_real | 3.61 | gitignored |

Grouped summary:

| Path | Findings | Classification basis |
|---|---|---|
| `.env` | 25 | Live provider keys (scraper providers, LLM routing, Stripe, RapidAPI, Playwright MCP token). Gitignored. |
| `Northstar_backend/.env` | 16 | Same provider set for the backend. Gitignored. |
| `northstar-os-retail-arbitrage-agent/.env` | 2 | Nested legacy project env. Gitignored. The leaked transcript values match this file's entropies. |
| `FirstNorthstarautomationchat.md` | 4 | Tracked chat export: `.env` and `.env.example` pasted inline. **Rotate.** |
| `exports/northstar_full_build_20261024/FirstNorthstarautomationchat.md` | 4 | Copy of the same transcript inside an ignored export. |
| `autothink-ui-chat-export.md` | 1 | Tracked chat export quoting a GitHub PAT from a screenshot. **Rotate.** |
| `exports/northstar_full_build_20261024/autothink-ui-chat-export.md` | 1 | Copy of the same transcript inside an ignored export. |
| `.playwright-mcp/*` | 14 | Session tokens captured from live browsing (`chatToken`, `PLAYWRIGHT_MCP_EXTENSION_TOKEN`, console `apiKey`). Gitignored, session-scoped. |

None of the `.env` credentials require rotation for leak reasons - they were never
committed. Rotate them only if you suspect host compromise or an exported copy left the
machine.

## 7. Every `unknown` finding (9)

Left un-allowlisted, as required. All are in one gitignored browser capture.

| `path:line` | Rule | Class | Entropy | Exposure |
|---|---|---|---|---|
| `.playwright-mcp/faire-net-requests.txt:64` | `generic-api-key` | unknown | 4.77 | gitignored |
| `.playwright-mcp/faire-net-requests.txt:64` | `generic-api-key` | unknown | 4.03 | gitignored |
| `.playwright-mcp/faire-net-requests.txt:64` | `generic-api-key` | unknown | 4.81 | gitignored |
| `.playwright-mcp/faire-net-requests.txt:66` | `generic-api-key` | unknown | 4.77 | gitignored |
| `.playwright-mcp/faire-net-requests.txt:66` | `generic-api-key` | unknown | 4.81 | gitignored |
| `.playwright-mcp/faire-net-requests.txt:66` | `generic-api-key` | unknown | 4.03 | gitignored |
| `.playwright-mcp/faire-net-requests.txt:82` | `generic-api-key` | unknown | 4.81 | gitignored |
| `.playwright-mcp/faire-net-requests.txt:82` | `generic-api-key` | unknown | 4.77 | gitignored |
| `.playwright-mcp/faire-net-requests.txt:82` | `generic-api-key` | unknown | 4.03 | gitignored |

`pin_unauth` is a Pinterest anonymous-session token lifted from a captured request log.
Whether it is still valid cannot be established without exercising it, and that is not
something this lane may do - hence `unknown` rather than `test_fixture`. The file is
gitignored, so it is not a commit risk. Recommendation: leave it, or delete
`.playwright-mcp/faire-net-requests.txt` if the capture is no longer needed.

## 8. `test_fixture` findings (250)

| Path pattern | Findings | Why not a credential |
|---|---|---|
| `reports/_wm_beeswax.html`, `reports/_wm_unpaper.html` | 170 | Scraped Walmart page captures. Matches are Walmart's page-config field names plus Walmart's own public Google API keys. **Allowlisted.** |
| `venv-crew/**` | 44 | Vendored third-party dependency source. Matches are parameter names, empty-string defaults and protocol constants (OAuth defaults, `Sec-WebSocket-Key`, xxhash constants, numpy `key_sha256` digests, a HF client-id constant). Gitignored. |
| `exports/**/README.json` | 32 | Creative-export metadata. The JSON `key` field holds a design/model identifier, not a credential. Gitignored. |
| `.playwright-mcp/**` | 9 | Page snapshots and console logs from public pages; follow-up rule hits. The live session tokens from the same directory are counted under `likely_real`. |
| `reports/video_scan/huggingface.jsonl` + export copy | 4 | The Hugging Face `access-token` rule matched the `id` field of a scraped public model listing - a model name beginning `hf_`, not a token. Gitignored. |

## 9. Method

1. `gitleaks version` reported 8.30.1, a native install. No binary was vendored or downloaded.
2. No prior gitleaks JSON artefact existed anywhere in the repo, so a fresh redacted scan
   was required rather than classification from an existing report.
3. Classification used path pattern, rule id, Shannon entropy, and the match context that
   gitleaks itself prints with the secret already replaced by `REDACTED`. For the two
   ambiguous chat-export hits, the surrounding line was inspected only after masking every
   run of 16+ token characters, so structure could be read without reading a value.
4. Exposure was resolved per file with `git ls-files` and `git check-ignore` rather than
   assumed, because the distinction between "ignored" and "untracked but committable" is
   the whole reason `reports/` was blocked.

### Confidence

High for the 170 allowlisted Walmart hits, the 44 vendored-dependency hits, the 32 export
metadata hits and the 4 model-id hits: in each case the match context names a
non-credential field.

High for the 3 rotation items: one is identified as a live PAT in surrounding prose, and
the two provider keys differ from their committed placeholders.

Lower for the 14 browser-session tokens: they are real captured session credentials, but
they are gitignored and expire on their own.

Where a judgement call was genuinely unclear, the finding was left un-allowlisted and
marked `unknown`, because allowing a real secret through is worse than leaving a false
positive reported.

