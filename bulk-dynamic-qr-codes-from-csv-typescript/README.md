# Bulk dynamic QR codes from a CSV (TypeScript)

Turn a CSV of names and URLs into dynamic QR codes and short links in one API call, with the official [Linkbreakers](https://linkbreakers.com/developers?utm_source=github&utm_content=bulk-dynamic-qr-codes-from-csv-typescript) TypeScript SDK, then pull each code's scan count back into a CSV. The same example in Python: [`bulk-dynamic-qr-codes-from-csv-python`](../bulk-dynamic-qr-codes-from-csv-python).

- **In:** `links.csv` with `name,destination`
- **Out:** `links_out.csv` (short link and id per row) and one SVG QR code per row in `qr/`
- **Report:** `scan_report.csv` with the scan count of every link

The codes are dynamic: each one points at a short link, so you can change where it goes later without reprinting it.

<img src="sample-qr.png" width="160" alt="A QR code created by this example. It opens https://linkbreak.ing/nLPFAKycp, which redirects to a restaurant's lunch menu.">

*Created by the run below: it opens `https://linkbreak.ing/nLPFAKycp`, which redirects to a restaurant's lunch menu.*

## Quickstart

You need Node.js 22+ and a Linkbreakers workspace API token with the `links:read` and `links:write` scopes ([create one here](https://app.linkbreakers.com/workspace/dashboard/api-tokens); [what tokens and scopes are](https://linkbreakers.com/help/article/what-are-api-tokens?utm_source=github&utm_content=bulk-dynamic-qr-codes-from-csv-typescript)).

```bash
git clone https://github.com/linkbreakers-com/examples.git
cd examples/bulk-dynamic-qr-codes-from-csv-typescript

npm install

cp .env.example .env          # then paste your token after LINKBREAKERS_TOKEN=
npx tsx bulk-qr.ts create links.csv
npx tsx bulk-qr.ts report
```

Replace `links.csv` with your own file. The only columns read are `name` and `destination`. `npm run create -- links.csv` and `npm run report` do the same.

## Sample output

A real run against the Linkbreakers API on 2026-11-04, with the `links.csv` in this directory:

```text
$ npx tsx bulk-qr.ts create links.csv
https://linkbreak.ing/nLPFAKycp  Lunch menu
https://linkbreak.ing/pyPFAdmnp  Store locator
https://linkbreak.ing/byP3Adycp  Conference schedule
https://linkbreak.ing/pkgFAdynM  Cookie recipe

4 dynamic QR codes created. Links: links_out.csv  Images: qr/
```

`links_out.csv`:

```csv
name,destination,short_link,link_id,qr_code_file
Lunch menu,https://www.bjsrestaurants.com/menu,https://linkbreak.ing/nLPFAKycp,7398a0cc-7d77-4dae-a046-a944d9d59c37,qr/nLPFAKycp.svg
Store locator,https://www.ikea.com/us/en/stores/,https://linkbreak.ing/pyPFAdmnp,f4f19302-1659-4515-906f-cabcc02e5ac8,qr/pyPFAdmnp.svg
Conference schedule,https://www.websummit.com/schedule/,https://linkbreak.ing/byP3Adycp,e79e03d9-4fb7-455c-b112-b917fcb83147,qr/byP3Adycp.svg
Cookie recipe,https://www.kingarthurbaking.com/recipes/chocolate-chip-cookies-recipe,https://linkbreak.ing/pkgFAdynM,6068df95-bee8-427d-ac1a-551417662032,qr/pkgFAdynM.svg
```

After a few test scans:

```text
$ npx tsx bulk-qr.ts report
     3  https://linkbreak.ing/nLPFAKycp  Lunch menu
     1  https://linkbreak.ing/pyPFAdmnp  Store locator
     2  https://linkbreak.ing/byP3Adycp  Conference schedule
     1  https://linkbreak.ing/pkgFAdynM  Cookie recipe

Scan report: scan_report.csv
```

## How it works

`bulk-qr.ts` is about 170 lines and makes three SDK calls, all on `LinksApi`:

1. **`linksServiceCreateBulk`** creates up to 250 links per request (the API's limit; larger files are sent in batches of 250). A batch is transactional: if one row is invalid, none of that batch is created. Each link gets the tag `csv-import`.

   ```ts
   const res = await api.linksServiceCreateBulk({
     createBulkLinksRequest: { links },
     idempotencyKey,
   });
   ```

2. **`linksServiceResolveQrcodeImages`** returns a signed URL for each link's QR code. The codes are drawn in the background right after the call, so the script asks every 2 seconds (for up to 30 seconds) until every link has one. The URLs expire, so it downloads the SVGs right away into `qr/<shortlink>.svg`.
3. **`linksServiceGet`** (in `report`) reads each link's `eventCount`, the number of scans and clicks. It is not instant: in the run above, the counts caught up within about two minutes of the scans.

Each batch is sent with an `Idempotency-Key` derived from its contents. If a run fails after a batch was answered (a failed download, a crash), running it again with the same CSV within 24 hours gets the first response back instead of creating the links twice.

Scanning a code opens `https://linkbreak.ing/<shortlink>?lbsrc=qrcode`, which redirects to the destination; the `lbsrc` parameter is how Linkbreakers tells a scan from a click on the short link.

## Good to know

- Every created link uses your plan's platform credits. When a batch needs more than you have left, the API answers `INSUFFICIENT_PLATFORM_CREDITS` and creates nothing.
- The SVGs have a transparent background. Put them on a light background when you print them.
- To send a code somewhere else later, change the link's destination in the dashboard or with `linksServiceUpdate`; the printed code stays the same.
- The SDK is the [`linkbreakers`](https://www.npmjs.com/package/linkbreakers) package on npm, generated from the API's OpenAPI document, so every endpoint has a typed method.
- Going further: [TypeScript SDK quickstart](https://linkbreakers.com/help/article/typescript-sdk-quickstart?utm_source=github&utm_content=bulk-dynamic-qr-codes-from-csv-typescript), [bulk QR codes without code](https://linkbreakers.com/help/article/how-to-bulk-create-qr-codes-in-linkbreakers?utm_source=github&utm_content=bulk-dynamic-qr-codes-from-csv-typescript), [all developer docs](https://linkbreakers.com/developers?utm_source=github&utm_content=bulk-dynamic-qr-codes-from-csv-typescript).

## License

MIT, see [LICENSE](../LICENSE).
