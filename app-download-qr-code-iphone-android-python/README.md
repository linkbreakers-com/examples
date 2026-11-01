# One QR code for an app download: App Store on iPhone, Google Play on Android (Python)

Create one dynamic QR code that opens the App Store on an iPhone, Google Play on an Android phone, and a web page on everything else, with the official [Linkbreakers](https://linkbreakers.com/developers?utm_source=github&utm_content=app-download-qr-code-iphone-android-python) Python SDK. You print one code; the routing happens on the server when it is scanned.

- **In:** your App Store URL, your Google Play URL and a fallback web page
- **Out:** one short link, its QR code in `app-download-qr.svg`, and a workflow: visit, then a Device Platform condition with three branches

<img src="sample-qr.png" width="160" alt="A QR code created by this example. It opens https://linkbreak.ing/sV360hmcp, which sends iPhones to the Wikipedia app on the App Store, Android phones to it on Google Play, and other devices to wikipedia.org.">

*Created by the run below: it opens `https://linkbreak.ing/sV360hmcp`. Scan it with an iPhone, then with an Android phone.*

Video: [How to make one QR code that opens the App Store on iPhone and Google Play on Android](https://www.youtube.com/watch?v=CjSVFfSPQBM) (3 minutes)

## Quickstart

You need Python 3.9+ and a Linkbreakers workspace API token with the `links:read`, `links:write`, `workflows:read` and `workflows:write` scopes ([create one here](https://app.linkbreakers.com/workspace/dashboard/api-tokens); [what tokens and scopes are](https://linkbreakers.com/help/article/what-are-api-tokens?utm_source=github&utm_content=app-download-qr-code-iphone-android-python)).

```bash
git clone https://github.com/linkbreakers-com/examples.git
cd examples/app-download-qr-code-iphone-android-python

python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then paste your token after LINKBREAKERS_TOKEN=
python app_qr.py \
  --name "My app download" \
  --app-store "https://apps.apple.com/us/app/<your-app>/id<your-id>" \
  --google-play "https://play.google.com/store/apps/details?id=<your.package>" \
  --fallback "https://example.com/app"
```

Without the flags, the script uses the Wikipedia app's public store pages and `https://www.wikipedia.org/` as placeholders, so you can try it before you have your own URLs. Replace them with yours.

## Sample output

A real run against the Linkbreakers API on 2026-11-01, with the default placeholder URLs:

```text
$ python app_qr.py --name "Wikipedia app download (example)"
Link id:     68c2d76c-7f83-4ac3-b566-58e71a8f393f
Short link:  https://linkbreak.ing/sV360hmcp
iOS       -> https://apps.apple.com/us/app/wikipedia/id324715238
Android   -> https://play.google.com/store/apps/details?id=org.wikipedia
Others    -> https://www.wikipedia.org/
QR code:     app-download-qr.svg
```

## Check the routing without a phone

The short link answers with a `303` redirect chosen from the visitor's user agent, so `curl` with a phone's user agent shows where that phone would go:

```bash
LINK=https://linkbreak.ing/sV360hmcp

curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" -A "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1" $LINK
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" -A "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36" $LINK
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36" $LINK
```

What it answered on 2026-11-01:

```text
303 https://apps.apple.com/us/app/wikipedia/id324715238
303 https://play.google.com/store/apps/details?id=org.wikipedia
303 https://www.wikipedia.org/
```

The QR code itself encodes `https://linkbreak.ing/sV360hmcp?lbsrc=qrcode`. The `lbsrc=qrcode` parameter is how Linkbreakers tells a scan from a click, and it is passed on to the destination (`...id324715238?lbsrc=qrcode`).

## How it works

`app_qr.py` is about 150 lines. A new link's journey is "visit, then redirect to the destination", so the script creates the link with the fallback page as its destination and adds the routing in front of that redirect:

1. **`LinksApi.links_service_create`** creates the link with `wait_for_qrcode=True`. The response includes the link's workflow steps, among them the redirect to the fallback page.
2. **`WorkflowStepsApi.workflow_steps_service_create`** twice, with `EVENT_ACTION_CLIENT_REDIRECT`: one redirect to the App Store URL, one to the Google Play URL. They are not connected to anything yet.
3. **`workflow_steps_service_create`** with `EVENT_ACTION_DEVICE_PLATFORM_CONDITION`, two options (`DEVICE_PLATFORM_CONDITION_VALUE_IOS` with id `ios`, `DEVICE_PLATFORM_CONDITION_VALUE_ANDROID` with id `android`) and `insert_before` set to the fallback redirect. The link visit now leads to the condition instead of straight to the fallback.
4. **`workflow_steps_service_connect_step`** three times: branch `ios` to the App Store redirect, `android` to the Google Play redirect, and `else` to the fallback redirect. A condition's branch ids are its option ids plus `else`.
5. **`workflow_steps_service_auto_layout_workflow`** tidies the steps in the dashboard's workflow editor, and **`workflow_steps_service_validate_workflow`** prints any issue it finds (none in the run above).
6. **`LinksApi.links_service_resolve_qrcode_images`** returns a signed URL for the QR code. It expires, so the script downloads the SVG right away.

Open the link in the [dashboard](https://app.linkbreakers.com/workspace/dashboard/links) to see the same workflow in the editor and change it by hand.

## Good to know

- **iPad:** an iPad that sends the iPad user agent goes to the App Store (checked with `curl`). iPadOS Safari asks for desktop sites by default and then sends the same user agent as a Mac, so those visits take the fallback branch. A fallback page with both store buttons covers them.
- **Other platforms:** `DevicePlatformConditionValue` also has `WINDOWS`, `MACOS`, `LINUX` and `CHROMEOS`. Add an option and a redirect for any of them the same way.
- **Change a store URL later** in the dashboard, or with `workflow_steps_service_update` on that redirect step. The printed code stays the same.
- **One link per placement** (flyer, packaging, slide) tells you which one brings installs; run the script once per placement with a different `--name`.
- Each run creates one link and uses your plan's platform credits.
- The SVG has a transparent background. Put it on a light background when you print it.
- Going further: [how to create a QR code for an app download](https://linkbreakers.com/help/article/how-to-create-a-qr-code-for-an-app-download?utm_source=github&utm_content=app-download-qr-code-iphone-android-python), [how to use device conditions](https://linkbreakers.com/help/article/how-to-use-device-conditions?utm_source=github&utm_content=app-download-qr-code-iphone-android-python), [Python SDK quickstart](https://linkbreakers.com/help/article/python-sdk-quickstart?utm_source=github&utm_content=app-download-qr-code-iphone-android-python), [all developer docs](https://linkbreakers.com/developers?utm_source=github&utm_content=app-download-qr-code-iphone-android-python).

## License

MIT, see [LICENSE](../LICENSE).
