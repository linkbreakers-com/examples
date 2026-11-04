/**
 * Bulk-create dynamic QR codes from a CSV with the Linkbreakers TypeScript SDK.
 *
 *   npx tsx bulk-qr.ts create links.csv   # CSV in, short links + QR images out
 *   npx tsx bulk-qr.ts report             # scan counts back to a CSV
 */
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import { parseArgs } from "node:util";
import { parse } from "csv-parse/sync";
import { stringify } from "csv-stringify/sync";
import { Configuration, LinksApi, ResponseError } from "linkbreakers";

// The API accepts at most 250 links per bulk request.
const BATCH_SIZE = 250;
const TAG = "csv-import";
const QR_WAIT_ATTEMPTS = 15;

const USAGE = `Usage:
  npx tsx bulk-qr.ts create <links.csv> [--out links_out.csv] [--qr-dir qr]
  npx tsx bulk-qr.ts report [--links links_out.csv] [--out scan_report.csv]`;

type Row = { name: string; destination: string };

function client(): LinksApi {
  try {
    process.loadEnvFile();
  } catch {
    // No .env file: the token may already be in the environment.
  }
  const token = process.env.LINKBREAKERS_TOKEN;
  if (!token) {
    die("LINKBREAKERS_TOKEN is not set. Copy .env.example to .env and add your workspace token.");
  }
  return new LinksApi(new Configuration({ accessToken: token, basePath: "https://api.linkbreakers.com" }));
}

function readCsv<T>(path: string): T[] {
  return parse(readFileSync(path, "utf8"), { columns: true, skip_empty_lines: true, bom: true });
}

function readRows(path: string): Row[] {
  const rows = readCsv<Row>(path);
  rows.forEach((row, i) => {
    if (!/^https?:\/\//.test(row.destination ?? "")) {
      die(`${path}:${i + 2}: destination must be an http(s) URL, got ${JSON.stringify(row.destination)}`);
    }
  });
  return rows;
}

async function create(inputCsv: string, outputCsv: string, qrDir: string): Promise<void> {
  const rows = readRows(inputCsv);
  const api = client();
  mkdirSync(qrDir, { recursive: true });
  const out: Record<string, string>[] = [];

  for (let start = 0; start < rows.length; start += BATCH_SIZE) {
    const batch = rows.slice(start, start + BATCH_SIZE);
    const links = batch.map((row) => ({
      name: row.name,
      destination: row.destination,
      tags: [TAG],
    }));
    // Same batch, same key: a retry after a timeout cannot create duplicates.
    const idempotencyKey = createHash("sha256").update(JSON.stringify(links)).digest("hex");
    const res = await api.linksServiceCreateBulk({
      createBulkLinksRequest: { links },
      idempotencyKey,
    });
    const created = res.links ?? [];
    const images = await qrImages(api, created.map((link) => link.id!));

    // Links come back in request order.
    for (const [i, link] of created.entries()) {
      const url = images[link.id!];
      const qrFile = url ? join(qrDir, `${link.shortlink}.svg`) : "";
      if (url) await download(url, qrFile);
      out.push({
        name: link.name ?? "",
        destination: batch[i].destination,
        short_link: link.entrypoint ?? "",
        link_id: link.id ?? "",
        qr_code_file: qrFile,
      });
      console.log(`${link.entrypoint}  ${link.name}`);
    }
  }

  writeCsv(outputCsv, out);
  console.log(`\n${out.length} dynamic QR codes created. Links: ${outputCsv}  Images: ${qrDir}/`);
}

// Each QR code is drawn in the background right after the call. Ask for the
// images until every link has one; signed URLs expire, so download them now.
async function qrImages(api: LinksApi, linkIds: string[]): Promise<Record<string, string>> {
  let images: Record<string, string> = {};
  for (let attempt = 0; attempt < QR_WAIT_ATTEMPTS; attempt++) {
    await sleep(2_000);
    const res = await api.linksServiceResolveQrcodeImages({ resolveQrcodeImagesRequest: { linkIds } });
    images = res.qrcodeSignedUrls ?? {};
    if (linkIds.every((id) => id in images)) break;
  }
  const missing = linkIds.length - Object.keys(images).length;
  if (missing > 0) console.warn(`${missing} QR codes were not ready yet; run the report later or download them from the dashboard.`);
  return images;
}

async function report(linksCsv: string, reportCsv: string): Promise<void> {
  const rows = readCsv<{ link_id: string }>(linksCsv);
  const api = client();
  const out: Record<string, string | number>[] = [];

  for (const row of rows) {
    const { link } = await api.linksServiceGet({ id: row.link_id });
    const scans = Number(link?.eventCount ?? 0);
    out.push({ name: link?.name ?? "", short_link: link?.entrypoint ?? "", scans });
    console.log(`${String(scans).padStart(6)}  ${link?.entrypoint}  ${link?.name}`);
  }

  writeCsv(reportCsv, out);
  console.log(`\nScan report: ${reportCsv}`);
}

async function download(url: string, path: string): Promise<void> {
  const response = await fetch(url, { signal: AbortSignal.timeout(30_000) });
  if (!response.ok) {
    throw new Error(`QR image download failed with HTTP ${response.status}: ${url}`);
  }
  writeFileSync(path, Buffer.from(await response.arrayBuffer()));
}

function writeCsv(path: string, rows: Record<string, unknown>[]): void {
  if (rows.length > 0) writeFileSync(path, stringify(rows, { header: true }));
}

function die(message: string): never {
  console.error(message);
  process.exit(1);
}

const { positionals, values } = parseArgs({
  allowPositionals: true,
  options: {
    out: { type: "string" },
    "qr-dir": { type: "string", default: "qr" },
    links: { type: "string", default: "links_out.csv" },
  },
});
const [command, inputCsv] = positionals;

try {
  if (command === "create" && inputCsv) {
    await create(inputCsv, values.out ?? "links_out.csv", values["qr-dir"]);
  } else if (command === "report") {
    await report(values.links, values.out ?? "scan_report.csv");
  } else {
    die(USAGE);
  }
} catch (err) {
  if (err instanceof ResponseError) {
    die(`Linkbreakers API error ${err.response.status}: ${await err.response.text()}`);
  }
  throw err;
}
