# AGENTS.md

- Python 3.9+. Setup: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
- Env: `LINKBREAKERS_TOKEN` (workspace API token, scopes `links:read`, `links:write`, `workflows:read`, `workflows:write`), read from `.env`. Never commit it.
- Run: `python app_qr.py --app-store <url> --google-play <url> --fallback <url>` creates one real link (uses platform credits) and writes `app-download-qr.svg`. Without flags it uses the Wikipedia app's store pages as placeholders.
- Check routing: `curl -s -o /dev/null -w "%{redirect_url}\n" -A "<user agent>" <short link>`, once with an iPhone UA, once with an Android UA, once with a desktop UA.
- No test suite yet. Check syntax with `python -m py_compile app_qr.py`.
- SDK calls used: `LinksApi.links_service_create`, `links_service_resolve_qrcode_images`; `WorkflowStepsApi.workflow_steps_service_create` (with `insert_before`), `workflow_steps_service_connect_step`, `workflow_steps_service_auto_layout_workflow`, `workflow_steps_service_validate_workflow`.
- Platform values: `DevicePlatformConditionValue` (`IOS`, `ANDROID`, `WINDOWS`, `MACOS`, `LINUX`, `CHROMEOS`). Branch ids of the condition are the option ids plus `else`.
