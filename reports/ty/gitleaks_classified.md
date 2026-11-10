# gitleaks findings: classified, values never read

312 findings over 140 files. Scanned with `--redact`; `Secret` and `Match` were dropped when the report was read, so no value is in this file, the tool's output, or the JSON it wrote.

## Summary

| class | findings | files |
|---|---|---|
| **fixture-or-capture** | 69 | 57 |
| **real-committed** | 5 | 2 |
| **real-local-only** | 43 | 3 |
| **review-untracked** | 151 | 58 |
| **vendor-false-positive** | 44 | 20 |

## Every finding with a committed file

| file | line | rule | class |
|---|---|---|---|
| `FirstNorthstarautomationchat.md` | 1143 | `generic-api-key` | **real-committed** |
| `FirstNorthstarautomationchat.md` | 1148 | `generic-api-key` | **real-committed** |
| `FirstNorthstarautomationchat.md` | 1291 | `generic-api-key` | **real-committed** |
| `FirstNorthstarautomationchat.md` | 1296 | `generic-api-key` | **real-committed** |
| `autothink-ui-chat-export.md` | 7852 | `github-pat` | **real-committed** |

## Real but local only (`.env`)

| file | line | rule |
|---|---|---|
| `.env` | 2 | `generic-api-key` |
| `.env` | 7 | `generic-api-key` |
| `.env` | 10 | `generic-api-key` |
| `.env` | 12 | `generic-api-key` |
| `.env` | 16 | `generic-api-key` |
| `.env` | 17 | `generic-api-key` |
| `.env` | 38 | `generic-api-key` |
| `.env` | 40 | `generic-api-key` |
| `.env` | 59 | `rapidapi-access-token` |
| `.env` | 72 | `generic-api-key` |
| `.env` | 73 | `generic-api-key` |
| `.env` | 74 | `generic-api-key` |
| `.env` | 75 | `generic-api-key` |
| `.env` | 76 | `generic-api-key` |
| `.env` | 80 | `generic-api-key` |
| `.env` | 81 | `generic-api-key` |
| `.env` | 82 | `generic-api-key` |
| `.env` | 83 | `generic-api-key` |
| `.env` | 84 | `generic-api-key` |
| `.env` | 89 | `generic-api-key` |
| `.env` | 95 | `generic-api-key` |
| `.env` | 98 | `stripe-access-token` |
| `.env` | 100 | `generic-api-key` |
| `.env` | 103 | `generic-api-key` |
| `.env` | 109 | `generic-api-key` |
| `Northstar_backend/.env` | 11 | `generic-api-key` |
| `Northstar_backend/.env` | 17 | `generic-api-key` |
| `Northstar_backend/.env` | 21 | `generic-api-key` |
| `Northstar_backend/.env` | 26 | `generic-api-key` |
| `Northstar_backend/.env` | 29 | `generic-api-key` |
| `Northstar_backend/.env` | 33 | `generic-api-key` |
| `Northstar_backend/.env` | 36 | `generic-api-key` |
| `Northstar_backend/.env` | 39 | `generic-api-key` |
| `Northstar_backend/.env` | 44 | `generic-api-key` |
| `Northstar_backend/.env` | 66 | `rapidapi-access-token` |
| `Northstar_backend/.env` | 77 | `generic-api-key` |
| `Northstar_backend/.env` | 78 | `generic-api-key` |
| `Northstar_backend/.env` | 79 | `generic-api-key` |
| `Northstar_backend/.env` | 80 | `generic-api-key` |
| `Northstar_backend/.env` | 81 | `generic-api-key` |
