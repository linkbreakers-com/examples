# Retargeting pixels on every QR code and short link (Python)

Set your Meta Pixel, Google tag (GA4 or Google Ads), TikTok Pixel, LinkedIn Insight Tag or Google Tag Manager container once on a [Linkbreakers](https://linkbreakers.com/developers?utm_source=github&utm_content=retargeting-pixels-on-every-qr-code-python) workspace, and every link and QR code of that workspace fires them when a person opens it, so you can retarget the people who scanned. One script with the official Python SDK, about 170 lines: it sets the pixels, reads them back, and checks which pixels fire on a given QR code.

- **Set:** `--meta`, `--google-tag`, `--tiktok`, `--linkedin`, `--gtm`. Pixels you do not pass stay as they are. `--remove meta,gtm` removes some.
- **Read back:** each pixel's ID, and whether it fires on every link or only on a selection.
- **Check a QR code:** `--link URL` creates one (or `--shortlink` picks one you already printed), lists the pixels that fire on it, saves `qr/<shortlink>.svg`, and with `--probe` opens it once as a phone and once as a link preview bot.

**Pixels run in the browser.** A person who scans goes through a short browser page that loads each platform's standard base code and its page view, then redirects: it leaves 300 ms after the scripts have loaded and never later than 1.2 seconds, usually well under a second. A link no pixel fires on redirects instantly, as before. **Only a person's browser gets that page:** bots, link previews (Facebook, Slack...), AI agents and automated or headless browsers keep the instant redirect, so they never fire a pixel and never enter your audiences. The run below shows both.

Written guides: [retargeting pixels for QR codes and links](https://linkbreakers.com/help/article/retargeting-pixels-meta-google-tiktok-linkedin-and-google-tag-manager?utm_source=github&utm_content=retargeting-pixels-on-every-qr-code-python), [how to retarget people who scanned your QR code](https://linkbreakers.com/help/article/how-to-retarget-people-who-scanned-your-qr-code-with-ads?utm_source=github&utm_content=retargeting-pixels-on-every-qr-code-python).

## Quickstart

You need Python 3.9+ and a Linkbreakers workspace API token with the `integrations:read` and `integrations:write` scopes, plus `links:read` and `links:write` for `--link` and `--shortlink` ([create one here](https://app.linkbreakers.com/workspace/dashboard/api-tokens); [what tokens and scopes are](https://linkbreakers.com/help/article/what-are-api-tokens?utm_source=github&utm_content=retargeting-pixels-on-every-qr-code-python)).

```bash
git clone https://github.com/linkbreakers-com/examples.git
cd examples/retargeting-pixels-on-every-qr-code-python

python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then paste your token after LINKBREAKERS_TOKEN=
python retargeting_pixels.py  # read what is set, changes nothing
python retargeting_pixels.py --meta <your pixel id> --google-tag <G- or AW- id>
python retargeting_pixels.py --link https://example.com/spring-menu --probe
```

Setting a pixel changes the whole workspace at once: from then on, every link and QR code in it fires that pixel, the ones already printed included. Nothing changes on the codes themselves.

## Sample output

A real run against the Linkbreakers API on 2026-11-03, in a workspace kept for these examples. **The pixel IDs are made up for the test** (`000000000000000`, `G-EXAMPLE000`...), in the shape each platform uses, and were removed at the end. The workspace had no pixels before:

```text
$ python retargeting_pixels.py
The workspace's retargeting pixels:
  Meta Pixel             -
  Google tag             -
  TikTok Pixel           -
  LinkedIn Insight Tag   -
  Google Tag Manager     -
```

Set all five. The Google tag was typed in lower case; the API stores IDs in upper case:

```text
$ python retargeting_pixels.py --meta 000000000000000 --google-tag g-example000 \
    --tiktok EXAMPLE0PIXEL0000000 --linkedin 0000000 --gtm GTM-EXAMPLE0
Updated. The workspace's retargeting pixels now:
  Meta Pixel             000000000000000          every link and QR code
  Google tag             G-EXAMPLE000             every link and QR code
  TikTok Pixel           EXAMPLE0PIXEL0000000     every link and QR code
  LinkedIn Insight Tag   0000000                  every link and QR code
  Google Tag Manager     GTM-EXAMPLE0             every link and QR code
  last changed 2026-11-03 16:21 UTC
```

Check a QR code. This run used a code created in an earlier example, so it took `--shortlink`; `--link URL` does the same on a new code:

```text
$ python retargeting_pixels.py --shortlink 3aOqKlmnp --probe
The workspace's retargeting pixels:
  ...
found    https://linkbreak.ing/3aOqKlmnp  Cold brew bottle  ->  qr/3aOqKlmnp.svg
  fires META        000000000000000          (every link)
  fires GOOGLE_TAG  G-EXAMPLE000             (every link)
  fires TIKTOK      EXAMPLE0PIXEL0000000     (every link)
  fires LINKEDIN    0000000                  (every link)
  fires GTM         GTM-EXAMPLE0             (every link)

Opening https://linkbreak.ing/3aOqKlmnp?lbsrc=qrcode, the URL the QR code encodes:
  phone browser     HTTP 200 browser page with 5 of 5 pixels: fires them, then redirects
  link preview bot  HTTP 303 straight to https://www.lavazzausa.com/en/recipes-and-coffee-hacks/homemade-cold-brew?lbsrc=qrcode  (no pixels)
```

The phone is an iPhone Safari user agent, the bot is Facebook's link preview crawler (`facebookexternalhit`). In the same run, the user agents of ChatGPT's browsing agent (`ChatGPT-User`), headless Chrome and Slack's link unfurler also got the instant `303`.

Remove them all, and the same code redirects instantly again, for everyone:

```text
$ python retargeting_pixels.py --remove meta,google-tag,tiktok,linkedin,gtm
Updated. The workspace's retargeting pixels now:
  Meta Pixel             -
  ...
$ python retargeting_pixels.py --shortlink 3aOqKlmnp --probe
  ...
  no pixel fires on this link: it redirects instantly
  phone browser     HTTP 303 straight to https://www.lavazzausa.com/...  (no pixels)
  link preview bot  HTTP 303 straight to https://www.lavazzausa.com/...  (no pixels)
```

## How it works

`retargeting_pixels.py` makes three calls to `RetargetingPixelsApi`:

1. **`retargeting_pixels_service_get()`** returns the pixels: `meta_pixel_id`, `google_tag_id`, `tiktok_pixel_id`, `linkedin_partner_id`, `gtm_container_id`, `updated_at`, and one scope per pixel that is set.
2. **`retargeting_pixels_service_update(UpdateRetargetingPixelsRequest(...))`** changes them. Send only the pixels to change: an omitted field keeps its value, an empty string removes that pixel.

   ```python
   UpdateRetargetingPixelsRequest(meta_pixel_id="123456789012345", gtm_container_id="")  # set Meta, remove GTM
   ```

3. **`retargeting_pixels_service_list_for_link(link_id)`** answers which pixels fire on one link. Empty means the link redirects instantly.

For `--link` it also uses `LinksApi.links_service_create` (with `wait_for_qrcode=True`) and `links_service_resolve_qrcode_images`, which returns a signed URL for the QR image; the URLs expire, so the script downloads the SVG right away. `--probe` makes two plain GET requests without following the redirect.

The same calls in REST:

```bash
curl -s https://api.linkbreakers.com/v1/retargeting-pixels \
  -H "Authorization: Bearer $LINKBREAKERS_TOKEN"

curl -s -X PUT https://api.linkbreakers.com/v1/retargeting-pixels \
  -H "Authorization: Bearer $LINKBREAKERS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"metaPixelId": "123456789012345", "googleTagId": "G-ABC123XYZ"}'

curl -s https://api.linkbreakers.com/v1/retargeting-pixels/links/<link id> \
  -H "Authorization: Bearer $LINKBREAKERS_TOKEN"
```

What the last one answered for the Cold brew bottle code in this run, abridged:

```json
{"pixels": [{"pixel": "RETARGETING_PIXEL_META", "id": "000000000000000", "scope": "RETARGETING_PIXEL_SCOPE_TYPE_ALL_LINKS"},
            {"pixel": "RETARGETING_PIXEL_GOOGLE_TAG", "id": "G-EXAMPLE000", "scope": "RETARGETING_PIXEL_SCOPE_TYPE_ALL_LINKS"}, ...]}
```

The same settings are in the dashboard, the CLI, the other SDKs and the MCP server (`retargeting_pixels_get`, `retargeting_pixels_update`, `retargeting_pixels_list_for_link`).

## Only some links

A pixel fires on every link by default. To fire one only on some links, the links of some directories (sub-directories included) or the links carrying some tags, send a scope for it. Tested in the same run with the Meta Pixel on the `granola` tag: the Granola box code then fired Meta, and the Cold brew bottle code fired the four other pixels only.

```python
from linkbreakers import RetargetingPixelScope, RetargetingPixel, RetargetingPixelScopeType

pixels_api.retargeting_pixels_service_update(UpdateRetargetingPixelsRequest(scopes=[
    RetargetingPixelScope(
        pixel=RetargetingPixel.RETARGETING_PIXEL_META,
        scope=RetargetingPixelScopeType.RETARGETING_PIXEL_SCOPE_TYPE_SELECTED_LINKS,
        tag_ids=["<tag id>"],          # and/or link_ids, directory_ids
    ),
]))
```

`RETARGETING_PIXEL_SCOPE_TYPE_ALL_LINKS` puts it back on every link. A pixel left out of `scopes` keeps its scope. More in [retargeting pixels on selected links](https://linkbreakers.com/help/article/retargeting-pixels-on-selected-links?utm_source=github&utm_content=retargeting-pixels-on-every-qr-code-python).

## Limits

- **IDs are checked for their shape.** Meta: 10 to 20 digits. Google tag: `G-`, `AW-`, `GT-` or `DC-` then letters and digits. TikTok: 15 to 30 letters and digits. LinkedIn partner ID: 3 to 12 digits. GTM: `GTM-` then 4 to 12 letters and digits. Anything else answers `400`:

  ```text
  {"code":3,"codeType":"RETARGETING_PIXEL_INVALID","message":"meta_pixel_id does not look like one: expected something like 123456789012345","details":[]}
  ```

  The API does not check that the ID belongs to a real account on the ad platform: a typo of the right shape is saved.
- **A page view, nothing else.** Meta, the Google tag, TikTok and LinkedIn each get their standard page view on the visit; the GTM container loads and runs the tags you put in it. No purchase or conversion events, and no server-side Conversions API.
- **A selection with nothing in it** answers `400 RETARGETING_PIXEL_SCOPE_EMPTY`; scope a pixel only after it is set (`RETARGETING_PIXEL_NOT_SET` otherwise).
- **Command-line clients.** While pixels are set, `curl`, `wget` and other HTTP libraries get the browser page (`200`) rather than the redirect, as the phone does in `--probe`. They do not run JavaScript, so they fire nothing, but `curl -L` stops at that page instead of reaching the destination (seen on 2026-11-03).
- **Consent.** Pixels set marketing cookies; in the EU these usually need the visitor's consent, which is yours to collect.
- **Audiences take time to fill** on the ad platform's side (Meta says 24 to 72 hours).

## Good to know

- To check a pixel really fires, open one of your codes on your phone with the platform's helper running (Meta Pixel Helper, Google Tag Assistant, TikTok Pixel Helper), or watch the platform's test events view.
- Google Tag Manager covers the platforms with no field of their own (Pinterest, Snap, Reddit, X, Microsoft Ads): put their tags in the container.
- `--probe`'s phone visit is recorded as a QR code scan in your analytics, like any visit.
- Going further: [Meta Pixel for QR codes and links](https://linkbreakers.com/help/article/meta-pixel-retargeting-for-qr-codes-and-links?utm_source=github&utm_content=retargeting-pixels-on-every-qr-code-python), [Python SDK quickstart](https://linkbreakers.com/help/article/python-sdk-quickstart?utm_source=github&utm_content=retargeting-pixels-on-every-qr-code-python), [all developer docs](https://linkbreakers.com/developers?utm_source=github&utm_content=retargeting-pixels-on-every-qr-code-python).

## License

MIT, see [LICENSE](../LICENSE).
