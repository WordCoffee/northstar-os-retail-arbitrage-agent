# History scan: sensitive content beyond keys, counts only

**1,711 commits** across **189 refs**. Every added line was scanned. No value, line or filename is printed here — only how many were found and in how many commits.

| category | occurrences | commits containing it |
|---|---|---|
| `dev_credential_assignment` | 535 | 80 |
| `dev_credential_url` | 88 | 26 |
| `email` | 935 | 130 |
| `email_machine_generated` | 261 | 130 |
| `phone` | 319 | 4 |
| `vendor:amazon` | 193,972 | 579 |
| `vendor:anthropic` | 1,602 | 55 |
| `vendor:bright data` | 870 | 106 |
| `vendor:brightdata` | 12,295 | 184 |
| `vendor:canopy` | 599 | 59 |
| `vendor:chocodata` | 81,988 | 75 |
| `vendor:comfyui` | 44,586 | 326 |
| `vendor:costco` | 191,579 | 312 |
| `vendor:dataforseo` | 118,089 | 124 |
| `vendor:easyparser` | 6,719 | 89 |
| `vendor:faire` | 4,996 | 39 |
| `vendor:keepa` | 352 | 50 |
| `vendor:openai` | 6,001 | 84 |
| `vendor:openwebninja` | 1,176 | 66 |
| `vendor:pacdora` | 701 | 54 |
| `vendor:packify` | 14,910 | 109 |
| `vendor:rapidapi` | 25,252 | 68 |
| `vendor:scavio` | 1,172 | 80 |
| `vendor:ultralytics` | 245 | 13 |
| `vendor:unwrangle` | 1,615 | 87 |

Reading the table: `vendor:*` counts **mentions of the name**, which is commercial information density, not a secret. `dev_credential_assignment` counts lines that assign something to a password/token-shaped name — much of that is code, so it is the noisiest row; `dev_credential_url` (a URL carrying user:pass) and `dev_credential_basic_header` are the high-signal ones. `phone` requires a leading `+` or human separators, because bare digit runs are ids, not numbers.

