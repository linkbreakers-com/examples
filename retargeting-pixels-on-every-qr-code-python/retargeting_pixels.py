"""Retargeting pixels on every QR code and short link, with the Linkbreakers Python SDK.

Sets the workspace's Meta Pixel, Google tag, TikTok Pixel, LinkedIn Insight Tag
and Google Tag Manager container, reads them back, and can create a QR code and
show which pixels fire on it.

    python retargeting_pixels.py                                  # read what is set
    python retargeting_pixels.py --meta 123456789012345 --google-tag G-ABC123XYZ
    python retargeting_pixels.py --remove tiktok,gtm
    python retargeting_pixels.py --link https://example.com/spring-menu --probe
    python retargeting_pixels.py --shortlink d0Pqd2mcM --probe      # a code you already printed
"""

import argparse
import os
import sys
from pathlib import Path

import urllib3
from dotenv import load_dotenv
from linkbreakers import (
    ApiClient,
    Configuration,
    CreateLinkRequest,
    LinksApi,
    ResolveQrcodeImagesRequest,
    RetargetingPixelsApi,
    UpdateRetargetingPixelsRequest,
)
from linkbreakers.exceptions import ApiException

# flag -> (request field, label)
PIXELS = {
    "meta": ("meta_pixel_id", "Meta Pixel"),
    "google-tag": ("google_tag_id", "Google tag"),
    "tiktok": ("tiktok_pixel_id", "TikTok Pixel"),
    "linkedin": ("linkedin_partner_id", "LinkedIn Insight Tag"),
    "gtm": ("gtm_container_id", "Google Tag Manager"),
}
LINK_NAME = "Retargeting pixels example"
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
LINK_PREVIEW = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"


def client() -> ApiClient:
    load_dotenv()
    token = os.environ.get("LINKBREAKERS_TOKEN")
    if not token:
        sys.exit("LINKBREAKERS_TOKEN is not set. Copy .env.example to .env and add your workspace token.")
    return ApiClient(Configuration(access_token=token, host="https://api.linkbreakers.com"))


def print_pixels(pixels) -> None:
    scopes = {s.pixel.value.removeprefix("RETARGETING_PIXEL_"): s for s in (pixels.scopes or [])}
    for flag, (field, label) in PIXELS.items():
        value = getattr(pixels, field)
        if not value:
            print(f"  {label:<22} -")
            continue
        scope = scopes.get(flag.replace("-", "_").upper())
        where = "every link and QR code"
        if scope and scope.scope and scope.scope.value.endswith("SELECTED_LINKS"):
            where = (f"selected: {len(scope.link_ids or [])} links, "
                     f"{len(scope.directory_ids or [])} directories, {len(scope.tag_ids or [])} tags")
        print(f"  {label:<22} {value:<24} {where}")
    if pixels.updated_at:
        print(f"  last changed {pixels.updated_at:%Y-%m-%d %H:%M} UTC")


def find_or_create_link(links_api: LinksApi, destination: str):
    for link in links_api.links_service_list(page_size=100, search=LINK_NAME).links or []:
        if link.name == LINK_NAME:
            return link, "reused "
    link = links_api.links_service_create(CreateLinkRequest(
        name=LINK_NAME, destination=destination, wait_for_qrcode=True,
    )).link
    return link, "created"


def find_by_shortlink(links_api: LinksApi, shortlink: str):
    shortlink = shortlink.rstrip("/").rsplit("/", 1)[-1]
    for link in links_api.links_service_list(page_size=100, search=shortlink).links or []:
        if link.shortlink == shortlink:
            return link, "found  "
    sys.exit(f"--shortlink: no link {shortlink!r} in this workspace")


def save_qr(links_api: LinksApi, link, qr_dir: Path) -> Path:
    path = qr_dir / f"{link.shortlink}.svg"
    if not path.exists():
        urls = links_api.links_service_resolve_qrcode_images(
            ResolveQrcodeImagesRequest(link_ids=[link.id])
        ).qrcode_signed_urls or {}
        if link.id in urls:
            qr_dir.mkdir(parents=True, exist_ok=True)
            response = urllib3.request("GET", urls[link.id], timeout=30)
            if response.status != 200:
                raise RuntimeError(f"QR image download failed with HTTP {response.status}")
            path.write_bytes(response.data)
    return path


def probe(url: str, pixel_ids: list[str]) -> None:
    """Open the code the way a phone does, then the way a link preview bot does."""
    for who, agent in (("phone browser", IPHONE), ("link preview bot", LINK_PREVIEW)):
        r = urllib3.request("GET", url, headers={"User-Agent": agent}, redirect=False, timeout=30)
        if r.status in (301, 302, 303, 307, 308):
            print(f"  {who:<17} HTTP {r.status} straight to {r.headers.get('Location')}  (no pixels)")
        else:
            body = r.data.decode("utf-8", "replace")
            found = [p for p in pixel_ids if p in body]
            print(f"  {who:<17} HTTP {r.status} browser page with {len(found)} of {len(pixel_ids)} pixels: fires them, then redirects")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for flag, (_, label) in PIXELS.items():
        parser.add_argument(f"--{flag}", metavar="ID", help=f"set the {label} ID")
    parser.add_argument("--remove", default="", help=f"comma separated, any of {','.join(PIXELS)}")
    parser.add_argument("--link", metavar="URL", help=f"create (or reuse) a QR code named {LINK_NAME!r} to this URL and list the pixels that fire on it")
    parser.add_argument("--shortlink", help="instead of --link: an existing link, by shortlink or full URL")
    parser.add_argument("--probe", action="store_true", help="with --link or --shortlink: open the code as a phone and as a link preview bot")
    parser.add_argument("--qr-dir", type=Path, default=Path("qr"))
    args = parser.parse_args()

    change = {}
    for flag, (field, _) in PIXELS.items():
        value = getattr(args, flag.replace("-", "_"))
        if value is not None:
            change[field] = value
    for flag in filter(None, (f.strip() for f in args.remove.split(","))):
        if flag not in PIXELS:
            sys.exit(f"--remove: unknown pixel {flag!r}, use one of {', '.join(PIXELS)}")
        change[PIXELS[flag][0]] = ""  # an empty string removes it; omitted pixels are kept

    with client() as api:
        pixels_api = RetargetingPixelsApi(api)
        try:
            if change:
                pixels = pixels_api.retargeting_pixels_service_update(
                    UpdateRetargetingPixelsRequest(**change)
                ).pixels
                print("Updated. The workspace's retargeting pixels now:")
            else:
                pixels = pixels_api.retargeting_pixels_service_get().pixels
                print("The workspace's retargeting pixels:")
            print_pixels(pixels)

            if args.link or args.shortlink:
                links_api = LinksApi(api)
                if args.shortlink:
                    link, status = find_by_shortlink(links_api, args.shortlink)
                else:
                    link, status = find_or_create_link(links_api, args.link)
                qr = save_qr(links_api, link, args.qr_dir)
                print(f"\n{status}  {link.entrypoint}  {link.name}  ->  {qr}")
                firing = pixels_api.retargeting_pixels_service_list_for_link(link.id).pixels or []
                if not firing:
                    print("  no pixel fires on this link: it redirects instantly")
                for p in firing:
                    scope = "every link" if p.scope.value.endswith("ALL_LINKS") else "in its selection"
                    print(f"  fires {p.pixel.value.removeprefix('RETARGETING_PIXEL_'):<11} {p.id:<24} ({scope})")
                if args.probe:
                    print(f"\nOpening {link.entrypoint}?lbsrc=qrcode, the URL the QR code encodes:")
                    probe(f"{link.entrypoint}?lbsrc=qrcode", [p.id for p in firing])
        except ApiException as e:
            sys.exit(f"Linkbreakers API error {e.status}: {e.body}")


if __name__ == "__main__":
    main()
