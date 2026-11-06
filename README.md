# Linkbreakers examples

Small, working examples for the [Linkbreakers](https://linkbreakers.com/developers?utm_source=github&utm_content=examples-index) API, SDKs and MCP server: dynamic QR codes, short links and scan tracking. Each directory is one task, self-contained, with its own README, dependencies, `.env.example` and `AGENTS.md`. Every example is run against the live API before it is published.

## Examples by task

| Task | Language | Directory |
|---|---|---|
| One QR code for an app download: App Store on iPhone, Google Play on Android, a web page on everything else | Python | [`app-download-qr-code-iphone-android-python`](app-download-qr-code-iphone-android-python) |
| Bulk-create dynamic QR codes and short links from a CSV, then export scan counts to a CSV | Python | [`bulk-dynamic-qr-codes-from-csv-python`](bulk-dynamic-qr-codes-from-csv-python) |
| Bulk-create dynamic QR codes and short links from a CSV, then export scan counts to a CSV | TypeScript | [`bulk-dynamic-qr-codes-from-csv-typescript`](bulk-dynamic-qr-codes-from-csv-typescript) |
| Bulk-create dynamic QR codes and short links from a CSV, then export scan counts to a CSV | Go | [`bulk-dynamic-qr-codes-from-csv-go`](bulk-dynamic-qr-codes-from-csv-go) |
| QR code scans by product line and by country: tag each code with its product line, then read scans filtered by tag and country | Python | [`qr-code-scans-by-product-and-country-python`](qr-code-scans-by-product-and-country-python) |
| Retargeting pixels on every QR code and short link: set a Meta Pixel, Google tag, TikTok Pixel, LinkedIn Insight Tag or GTM container once, check which fire on a code | Python | [`retargeting-pixels-on-every-qr-code-python`](retargeting-pixels-on-every-qr-code-python) |

## Run one

```bash
git clone https://github.com/linkbreakers-com/examples.git
cd examples/<directory>
```

Then follow that directory's README. You need a workspace API token: [create one](https://app.linkbreakers.com/workspace/dashboard/api-tokens), and read [what tokens and scopes are](https://linkbreakers.com/help/article/what-are-api-tokens?utm_source=github&utm_content=examples-index).

## SDKs and tools

[TypeScript](https://github.com/linkbreakers-com/linkbreakers-typescript) · [Python](https://github.com/linkbreakers-com/linkbreakers-python) · [Go](https://github.com/linkbreakers-com/linkbreakers-go) · [Java](https://github.com/linkbreakers-com/linkbreakers-java) · [Rust](https://github.com/linkbreakers-com/linkbreakers-rust) · [CLI](https://github.com/linkbreakers-com/linkbreakers-cli) · [MCP server](https://github.com/linkbreakers-com/linkbreakers-mcp)

## License

MIT, see [LICENSE](LICENSE).
