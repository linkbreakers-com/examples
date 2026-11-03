# AGENTS.md

- Python 3.9+. Setup: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
- Env: `LINKBREAKERS_TOKEN` (workspace API token, scopes `integrations:read`, `integrations:write`; add `links:read`, `links:write` for `--link`/`--shortlink`), read from `.env`. Never commit it.
- Run: `python retargeting_pixels.py` reads the pixels. `--meta ID --google-tag ID --tiktok ID --linkedin ID --gtm ID` sets them, `--remove meta,gtm` removes them. These change the whole workspace: every link and QR code fires them.
- `--link URL` creates one real link (uses platform credits) or reuses the one named "Retargeting pixels example"; `--shortlink X` checks an existing link instead. `--probe` opens it as a phone and as a link preview bot (the phone visit counts as a scan).
- No test suite yet. Check syntax with `python -m py_compile retargeting_pixels.py`.
