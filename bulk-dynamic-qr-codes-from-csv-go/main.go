// Bulk-create dynamic QR codes from a CSV with the Linkbreakers Go SDK.
//
//	go run . create links.csv   # CSV in, short links + QR images out
//	go run . report             # scan counts back to a CSV
package main

import (
	"context"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/joho/godotenv"
	linkbreakers "github.com/linkbreakers-com/linkbreakers-go"
)

const (
	// The API accepts at most 250 links per bulk request.
	batchSize = 250
	tag       = "csv-import"
	usage     = `Usage:
  go run . create [-out links_out.csv] [-qr-dir qr] <links.csv>
  go run . report [-links links_out.csv] [-out scan_report.csv]`
)

// Variables so the tests do not have to wait.
var (
	qrPollInterval = 2 * time.Second
	qrPollAttempts = 15
)

type client struct {
	links *linkbreakers.LinksAPIService
	http  *http.Client
}

func newClient(serverURL string) client {
	cfg := linkbreakers.NewConfiguration()
	cfg.Servers = linkbreakers.ServerConfigurations{{URL: serverURL}}
	cfg.HTTPClient = &http.Client{Timeout: 60 * time.Second}
	return client{links: linkbreakers.NewAPIClient(cfg).LinksAPI, http: cfg.HTTPClient}
}

type row struct {
	name, destination string
}

// readCSV returns the rows of a CSV with a header line, as maps keyed by column.
func readCSV(path string) ([]map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	records, err := csv.NewReader(f).ReadAll()
	if err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	if len(records) == 0 {
		return nil, fmt.Errorf("%s: the file is empty", path)
	}
	// Spreadsheet exports often start with a byte order mark.
	records[0][0] = strings.TrimPrefix(records[0][0], "\xef\xbb\xbf")

	rows := make([]map[string]string, 0, len(records)-1)
	for _, record := range records[1:] {
		values := make(map[string]string, len(record))
		for i, column := range records[0] {
			values[column] = record[i]
		}
		rows = append(rows, values)
	}
	return rows, nil
}

func readLinks(path string) ([]row, error) {
	records, err := readCSV(path)
	if err != nil {
		return nil, err
	}
	rows := make([]row, 0, len(records))
	for i, record := range records {
		destination := record["destination"]
		u, err := url.Parse(destination)
		if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
			return nil, fmt.Errorf("%s:%d: destination must be an http(s) URL, got %q", path, i+2, destination)
		}
		rows = append(rows, row{name: record["name"], destination: destination})
	}
	return rows, nil
}

func writeCSV(path string, header []string, rows [][]string) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()

	w := csv.NewWriter(f)
	w.Write(header)
	w.WriteAll(rows) // WriteAll flushes.
	if err := w.Error(); err != nil {
		return err
	}
	return f.Close()
}

func (c client) create(ctx context.Context, inputCSV, outputCSV, qrDir string) error {
	rows, err := readLinks(inputCSV)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(qrDir, 0o755); err != nil {
		return err
	}

	var out [][]string
	for batch := range slices.Chunk(rows, batchSize) {
		requests := make([]linkbreakers.CreateLinkRequest, len(batch))
		for i, r := range batch {
			request := linkbreakers.NewCreateLinkRequest(r.destination)
			request.SetName(r.name)
			request.SetTags([]string{tag})
			requests[i] = *request
		}
		key, err := idempotencyKey(requests)
		if err != nil {
			return err
		}
		res, _, err := c.links.LinksServiceCreateBulk(ctx).
			CreateBulkLinksRequest(*linkbreakers.NewCreateBulkLinksRequest(requests)).
			IdempotencyKey(key).
			Execute()
		if err != nil {
			return err
		}

		created := res.GetLinks()
		ids := make([]string, len(created))
		for i := range created {
			ids[i] = created[i].GetId()
		}
		images, err := c.qrImages(ctx, ids)
		if err != nil {
			return err
		}

		// Links come back in request order.
		for i := range created {
			link := &created[i]
			qrFile := ""
			if signedURL, ok := images[link.GetId()]; ok {
				qrFile = filepath.Join(qrDir, link.GetShortlink()+".svg")
				if err := c.download(ctx, signedURL, qrFile); err != nil {
					return err
				}
			}
			out = append(out, []string{link.GetName(), batch[i].destination, link.GetEntrypoint(), link.GetId(), qrFile})
			fmt.Printf("%s  %s\n", link.GetEntrypoint(), link.GetName())
		}
	}

	header := []string{"name", "destination", "short_link", "link_id", "qr_code_file"}
	if err := writeCSV(outputCSV, header, out); err != nil {
		return err
	}
	fmt.Printf("\n%d dynamic QR codes created. Links: %s  Images: %s/\n", len(out), outputCSV, qrDir)
	return nil
}

// idempotencyKey hashes a batch. Same batch, same key: running the same CSV
// again after a failure cannot create duplicates.
func idempotencyKey(requests []linkbreakers.CreateLinkRequest) (string, error) {
	body, err := json.Marshal(requests)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(body)
	return hex.EncodeToString(sum[:]), nil
}

// qrImages asks for the signed image URLs until every link has one: each QR
// code is drawn in the background right after the create call. A code that is
// still missing after the last attempt is a warning, not a failure.
func (c client) qrImages(ctx context.Context, linkIDs []string) (map[string]string, error) {
	var images map[string]string
	for range qrPollAttempts {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(qrPollInterval):
		}
		res, _, err := c.links.LinksServiceResolveQrcodeImages(ctx).
			ResolveQrcodeImagesRequest(*linkbreakers.NewResolveQrcodeImagesRequest(linkIDs)).
			Execute()
		if err != nil {
			return nil, err
		}
		images = res.GetQrcodeSignedUrls()
		if len(images) >= len(linkIDs) {
			return images, nil
		}
	}
	fmt.Fprintf(os.Stderr, "%d QR codes were not ready yet; download them from the dashboard.\n", len(linkIDs)-len(images))
	return images, nil
}

// download saves a signed URL right away, since signed URLs expire.
func (c client) download(ctx context.Context, signedURL, path string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, signedURL, nil)
	if err != nil {
		return err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("QR image download failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("QR image download failed with HTTP %d for %s", resp.StatusCode, path)
	}

	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	if _, err := io.Copy(f, resp.Body); err != nil {
		return err
	}
	return f.Close()
}

func (c client) report(ctx context.Context, linksCSV, reportCSV string) error {
	records, err := readCSV(linksCSV)
	if err != nil {
		return err
	}

	out := make([][]string, 0, len(records))
	for _, record := range records {
		res, _, err := c.links.LinksServiceGet(ctx, record["link_id"]).Execute()
		if err != nil {
			return err
		}
		link := res.GetLink()
		scans := link.GetEventCount()
		out = append(out, []string{link.GetName(), link.GetEntrypoint(), strconv.FormatInt(scans, 10)})
		fmt.Printf("%6d  %s  %s\n", scans, link.GetEntrypoint(), link.GetName())
	}

	if err := writeCSV(reportCSV, []string{"name", "short_link", "scans"}, out); err != nil {
		return err
	}
	fmt.Printf("\nScan report: %s\n", reportCSV)
	return nil
}

func run(ctx context.Context, args []string) error {
	if len(args) == 0 {
		return errors.New(usage)
	}
	flags := flag.NewFlagSet(args[0], flag.ContinueOnError)
	out := flags.String("out", "", "output CSV")
	qrDir := flags.String("qr-dir", "qr", "where the QR images go (create)")
	links := flags.String("links", "links_out.csv", "the CSV written by create (report)")
	if err := flags.Parse(args[1:]); err != nil {
		return err
	}
	if args[0] != "report" && (args[0] != "create" || flags.NArg() != 1) {
		return errors.New(usage)
	}

	// No .env file is fine: the token may already be in the environment.
	_ = godotenv.Load()
	token := os.Getenv("LINKBREAKERS_TOKEN")
	if token == "" {
		return errors.New("LINKBREAKERS_TOKEN is not set. Copy .env.example to .env and add your workspace token.")
	}
	ctx = context.WithValue(ctx, linkbreakers.ContextAccessToken, token)
	c := newClient("https://api.linkbreakers.com")

	if args[0] == "create" {
		if *out == "" {
			*out = "links_out.csv"
		}
		return c.create(ctx, flags.Arg(0), *out, *qrDir)
	}
	if *out == "" {
		*out = "scan_report.csv"
	}
	return c.report(ctx, *links, *out)
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	if err := run(ctx, os.Args[1:]); err != nil {
		// The SDK keeps the API's explanation in the error's body.
		var apiErr *linkbreakers.GenericOpenAPIError
		if errors.As(err, &apiErr) {
			fmt.Fprintf(os.Stderr, "Linkbreakers API error %s: %s\n", apiErr.Error(), apiErr.Body())
		} else {
			fmt.Fprintln(os.Stderr, err)
		}
		os.Exit(1)
	}
}
