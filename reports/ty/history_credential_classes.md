# Credential-shaped history: localhost/fixture vs real host

1,715 commits across 189 refs, every added line read.
Counts only. No user, password, token, address or line is printed. The only strings recorded are hostnames, and only for a credential URL that reaches a real host — a rotation action that does not name the host is not actionable.

## Credential URLs (88 expected)

| class | occurrences |
|---|---|
| `doc_placeholder` | 28 |
| `fixture` | 42 |
| `localhost` | 15 |
| `real_host` | 2 |
| `unparsed` | 1 |

### Real hosts carrying a user:pass URL

| host | occurrences |
|---|---|
| `assignment-line:api.scrape.do` | 1 |
| `assignment-line:github.com` | 10 |
| `assignment-line:www.aboutamazon.com` | 3 |
| `assignment-line:www.packify.ai` | 2 |
| `assignment-line:www.w3.org` | 1 |
| `github.com` | 1 |
| `www.packify.ai` | 1 |

## Credential assignments (535 expected)

| class | occurrences |
|---|---|
| `no_host_code_reference` | 274 |
| `no_host_literal` | 188 |
| `no_host_placeholder` | 57 |
| `with_fixture` | 1 |
| `with_real_host` | 17 |

## Non-machine emails (674 expected)

| class | occurrences |
|---|---|
| `business` | 44 |
| `business_or_vendor` | 452 |
| `machine` | 261 |
| `owner` | 93 |
| `third_party_personal` | 85 |

## Phones (319 expected)

| class | occurrences |
|---|---|
| `business` | 266 |
| `owner` | 2 |
| `us_ca_unattributed` | 51 |

`unattributed` is deliberate: a phone number carries no owner. It is only attributed when the same line names a brand (`business`) or the owner's own handle (`owner`). Anything else stays unattributed rather than guessed.

