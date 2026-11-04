# AGENTS.md

- Node.js 22+. Setup: `npm install`
- Env: `LINKBREAKERS_TOKEN` (workspace API token, scopes `links:read` and `links:write`), read from `.env`. Never commit it.
- Create: `npx tsx bulk-qr.ts create links.csv` writes `links_out.csv` and `qr/<shortlink>.svg`. Each run creates real links and uses platform credits.
- Report: `npx tsx bulk-qr.ts report` reads `links_out.csv`, writes `scan_report.csv`.
- No test suite yet. Type-check with `npm run typecheck`.
- SDK calls used (`linkbreakers` on npm, `LinksApi`): `linksServiceCreateBulk`, `linksServiceResolveQrcodeImages`, `linksServiceGet`. Max 250 links per bulk request.
