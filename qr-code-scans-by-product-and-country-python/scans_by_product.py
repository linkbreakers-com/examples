"""QR code scans by product line and by country, with the Linkbreakers Python SDK.

Creates one dynamic QR code per row of codes.csv, tagged with its product line
(rows that already exist are reused), then prints scans per product line and country.

    python scans_by_product.py
    python scans_by_product.py --countries FR,DE --days 30
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import urllib3
from dotenv import load_dotenv
from linkbreakers import (
    AnalyticsDataApi,
    ApiClient,
    Configuration,
    CreateLinkRequest,
    GetBreakdownRequest,
    LinksApi,
    ResolveQrcodeImagesRequest,
    TagsApi,
)
from linkbreakers.exceptions import ApiException


def client() -> ApiClient:
    load_dotenv()
    token = os.environ.get("LINKBREAKERS_TOKEN")
    if not token:
        sys.exit("LINKBREAKERS_TOKEN is not set. Copy .env.example to .env and add your workspace token.")
    return ApiClient(Configuration(access_token=token, host="https://api.linkbreakers.com"))


def read_codes(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, start=2):
        if not row.get("product_line") or not row.get("name"):
            sys.exit(f"{path}:{i}: product_line and name are required")
        if not (row.get("destination") or "").startswith(("http://", "https://")):
            sys.exit(f"{path}:{i}: destination must be an http(s) URL, got {row.get('destination')!r}")
    return rows


def ensure_codes(links_api: LinksApi, codes: list[dict], qr_dir: Path) -> None:
    """Create the codes that do not exist yet, reuse the others, save every QR image."""
    links = []
    for line in dict.fromkeys(c["product_line"] for c in codes):
        # The tags filter takes tag names. A name already carrying this tag is reused.
        tagged = links_api.links_service_list(page_size=100, tags=[line]).links or []
        existing = {link.name: link for link in tagged}
        for code in (c for c in codes if c["product_line"] == line):
            link, status = existing.get(code["name"]), "reused "
            if link is None:
                # A tag that does not exist yet is created with the link.
                link = links_api.links_service_create(CreateLinkRequest(
                    name=code["name"], destination=code["destination"], tags=[line], wait_for_qrcode=True,
                )).link
                status = "created"
            links.append(link)
            print(f"{status}  {line:<12} {link.entrypoint}  {link.name}")

    # Signed image URLs expire, so download the files now.
    qr_dir.mkdir(parents=True, exist_ok=True)
    missing = [link for link in links if not (qr_dir / f"{link.shortlink}.svg").exists()]
    if missing:
        images = links_api.links_service_resolve_qrcode_images(
            ResolveQrcodeImagesRequest(link_ids=[link.id for link in missing])
        ).qrcode_signed_urls or {}
        for link in missing:
            if link.id in images:
                download(images[link.id], qr_dir / f"{link.shortlink}.svg")
    print(f"QR codes: {qr_dir}/\n")


def tag_id(tags_api: TagsApi, name: str) -> Optional[str]:
    # search matches partial names, so keep the exact one.
    tags = tags_api.tags_service_list(page_size=100, search=name).tags or []
    return next((t.id for t in tags if t.name == name), None)


def scans_by_country(analytics: AnalyticsDataApi, tag: str, countries: list[str], start: datetime, end: datetime) -> dict:
    """Scans and clicks of every link carrying this tag, per country (ISO alpha-2)."""
    response = analytics.analytics_data_service_get_breakdown(GetBreakdownRequest(
        dimension="country",
        tag_id=tag,              # at most one of tag_id, directory_id and link_id
        countries=countries or None,
        start_date=start,
        end_date=end,
        limit=250,
    ))
    return {point.code or point.label: point.event_count for point in response.data or []}


def report(api_client: ApiClient, product_lines: list[str], countries: list[str], days: int) -> None:
    tags_api, analytics = TagsApi(api_client), AnalyticsDataApi(api_client)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    table = {}
    for line in product_lines:
        tid = tag_id(tags_api, line)
        table[line] = scans_by_country(analytics, tid, countries, start, end) if tid else {}

    # Without --countries, the columns are every country seen, most scans first.
    columns = countries or sorted(
        {c for row in table.values() for c in row}, key=lambda c: -sum(row.get(c, 0) for row in table.values())
    )
    print(f"Scans by product line and country, {start:%Y-%m-%d} to {end:%Y-%m-%d} ({days} days)\n")
    width = max(len("product line"), *(len(line) for line in product_lines))
    print(f"{'product line':<{width}}" + "".join(f"{c:>7}" for c in columns) + f"{'total':>8}")
    for line, row in table.items():
        cells = [row.get(c, 0) for c in columns]
        print(f"{line:<{width}}" + "".join(f"{n:>7}" for n in cells) + f"{sum(cells):>8}")
    if not columns:
        print("(no scans in this period yet: scan a code from qr/ and run this again)")


def download(url: str, path: Path) -> None:
    response = urllib3.request("GET", url, timeout=30)
    if response.status != 200:
        raise RuntimeError(f"QR image download failed with HTTP {response.status}: {url}")
    path.write_bytes(response.data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--codes", type=Path, default=Path("codes.csv"), help="product_line,name,destination")
    parser.add_argument("--countries", default="", help="ISO alpha-2 codes, comma separated, e.g. FR,DE")
    parser.add_argument("--days", type=int, default=30, help="how many days back to count")
    parser.add_argument("--qr-dir", type=Path, default=Path("qr"))
    args = parser.parse_args()

    countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    for c in countries:
        # The API answers an unknown code with no rows, not an error, so check here.
        if not re.fullmatch(r"[A-Z]{2}", c):
            sys.exit(f"--countries takes ISO 3166-1 alpha-2 codes such as FR or DE, got {c!r}")

    codes = read_codes(args.codes)
    try:
        with client() as api_client:
            ensure_codes(LinksApi(api_client), codes, args.qr_dir)
            report(api_client, list(dict.fromkeys(c["product_line"] for c in codes)), countries, args.days)
    except ApiException as e:
        sys.exit(f"Linkbreakers API error {e.status}: {e.body}")


if __name__ == "__main__":
    main()
