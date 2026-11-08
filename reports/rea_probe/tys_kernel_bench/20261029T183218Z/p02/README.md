# Ledger service

Read-only reporting service for the finance team. Today the service is a stub:
it starts, loads its configuration and registers no routes at all.

## Constraints

1. Storage is read-only. No schema migration is ever added to this service.
2. One route per increment, each with its own test.
3. JSON responses only; no HTML templates.

## Next increment

Add a single **GET** route that returns the current ledger period, plus a test
that exercises it. The route name, method and response shape are agreed in
`endpoint.md` before the code is written.
