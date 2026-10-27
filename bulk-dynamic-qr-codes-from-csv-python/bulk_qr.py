"""Bulk-create dynamic QR codes from a CSV with the Linkbreakers Python SDK.

    python bulk_qr.py create links.csv   # CSV in, short links + QR images out
    python bulk_qr.py report             # scan counts back to a CSV
"""

import argparse
import csv
import hashlib
import os
import sys
from pathlib import Path

import urllib3
from dotenv import load_dotenv
from linkbreakers import (
    ApiClient,
    Configuration,
    CreateBulkLinksRequest,
    CreateLinkRequest,
    LinksApi,
    ResolveQrcodeImagesRequest,
)
from linkbreakers.exceptions import ApiException

# The API accepts at most 250 links per bulk request.
BATCH_SIZE = 250
TAG = "csv-import"


def client() -> ApiClient:
    load_dotenv()
    token = os.environ.get("LINKBREAKERS_TOKEN")
    if not token:
        sys.exit("LINKBREAKERS_TOKEN is not set. Copy .env.example to .env and add your workspace token.")
    return ApiClient(Configuration(access_token=token, host="https://api.linkbreakers.com"))


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, start=2):
        if not (row.get("destination") or "").startswith(("http://", "https://")):
            sys.exit(f"{path}:{i}: destination must be an http(s) URL, got {row.get('destination')!r}")
    return rows


def create(input_csv: Path, output_csv: Path, qr_dir: Path) -> None:
    rows = read_rows(input_csv)
    qr_dir.mkdir(parents=True, exist_ok=True)
    out = []

    with client() as api_client:
        links_api = LinksApi(api_client)
        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            request = CreateBulkLinksRequest(links=[
                CreateLinkRequest(
                    name=row["name"],
                    destination=row["destination"],
                    tags=[TAG],
                    wait_for_qrcode=True,
                )
                for row in batch
            ])
            # Same batch, same key: a retry after a timeout cannot create duplicates.
            key = hashlib.sha256(request.to_json().encode()).hexdigest()
            created = links_api.links_service_create_bulk(request, idempotency_key=key).links or []

            # Signed image URLs expire, so download the files now.
            images = links_api.links_service_resolve_qrcode_images(
                ResolveQrcodeImagesRequest(link_ids=[link.id for link in created])
            ).qrcode_signed_urls or {}

            # Links come back in request order.
            for row, link in zip(batch, created):
                qr_file = ""
                if link.id in images:
                    qr_file = str(qr_dir / f"{link.shortlink}.svg")
                    download(images[link.id], qr_file)
                out.append({
                    "name": link.name,
                    "destination": row["destination"],
                    "short_link": link.entrypoint,
                    "link_id": link.id,
                    "qr_code_file": qr_file,
                })
                print(f"{link.entrypoint}  {link.name}")

    write_csv(output_csv, out)
    print(f"\n{len(out)} dynamic QR codes created. Links: {output_csv}  Images: {qr_dir}/")


def report(links_csv: Path, report_csv: Path) -> None:
    with links_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    out = []
    with client() as api_client:
        links_api = LinksApi(api_client)
        for row in rows:
            link = links_api.links_service_get(row["link_id"]).link
            out.append({
                "name": link.name,
                "short_link": link.entrypoint,
                "scans": int(link.event_count or 0),
            })
            print(f"{int(link.event_count or 0):>6}  {link.entrypoint}  {link.name}")

    write_csv(report_csv, out)
    print(f"\nScan report: {report_csv}")


def download(url: str, path: str) -> None:
    response = urllib3.request("GET", url, timeout=30)
    if response.status != 200:
        raise RuntimeError(f"QR image download failed with HTTP {response.status}: {url}")
    Path(path).write_bytes(response.data)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create", help="create one dynamic QR code per CSV row")
    c.add_argument("input_csv", type=Path)
    c.add_argument("--out", type=Path, default=Path("links_out.csv"))
    c.add_argument("--qr-dir", type=Path, default=Path("qr"))

    r = sub.add_parser("report", help="write scan counts for the links you created")
    r.add_argument("--links", type=Path, default=Path("links_out.csv"))
    r.add_argument("--out", type=Path, default=Path("scan_report.csv"))

    args = parser.parse_args()
    try:
        if args.command == "create":
            create(args.input_csv, args.out, args.qr_dir)
        else:
            report(args.links, args.out)
    except ApiException as e:
        sys.exit(f"Linkbreakers API error {e.status}: {e.body}")


if __name__ == "__main__":
    main()
