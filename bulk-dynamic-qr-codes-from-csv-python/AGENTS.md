# AGENTS.md

- Python 3.9+. Setup: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
- Env: `LINKBREAKERS_TOKEN` (workspace API token, scopes `links:read` and `links:write`), read from `.env`. Never commit it.
- Create: `python bulk_qr.py create links.csv` writes `links_out.csv` and `qr/<shortlink>.svg`. Each run creates real links and uses platform credits.
- Report: `python bulk_qr.py report` reads `links_out.csv`, writes `scan_report.csv`.
- No test suite yet. Check syntax with `python -m py_compile bulk_qr.py`.
- SDK calls used: `LinksApi.links_service_create_bulk`, `links_service_resolve_qrcode_images`, `links_service_get`. Max 250 links per bulk request.
