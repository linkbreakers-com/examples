# AGENTS.md

- Python 3.9+. Setup: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
- Env: `LINKBREAKERS_TOKEN` (workspace API token, scopes `links:read`, `links:write`, `analytics:read`), read from `.env`. Never commit it.
- Run: `python scans_by_product.py --countries FR,DE --days 30`. Creates one real link per `codes.csv` row that does not exist yet (uses platform credits), saves `qr/<shortlink>.svg`, prints scans per product line and country.
- No test suite yet. Check syntax with `python -m py_compile scans_by_product.py`.
