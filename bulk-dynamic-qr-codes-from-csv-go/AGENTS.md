# AGENTS.md

- Go 1.23+. Dependencies download on the first `go run`.
- Env: `LINKBREAKERS_TOKEN` (workspace API token, scopes `links:read` and `links:write`), read from `.env` or the environment. Never commit it.
- Create: `go run . create links.csv` writes `links_out.csv` and `qr/<shortlink>.svg`. Each run creates real links and uses platform credits.
- Report: `go run . report` reads `links_out.csv`, writes `scan_report.csv`.
- Test: `go test ./...` (mocked API, no token, no credits). Also `go vet ./...`.
- SDK calls used (`github.com/linkbreakers-com/linkbreakers-go`, `client.LinksAPI`): `LinksServiceCreateBulk`, `LinksServiceResolveQrcodeImages`, `LinksServiceGet`. Max 250 links per bulk request.
