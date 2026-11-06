package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	linkbreakers "github.com/linkbreakers-com/linkbreakers-go"
)

func TestReadLinksRejectsBadDestination(t *testing.T) {
	path := filepath.Join(t.TempDir(), "links.csv")
	os.WriteFile(path, []byte("name,destination\nMenu,not-a-url\n"), 0o644)

	_, err := readLinks(path)
	if err == nil || !strings.Contains(err.Error(), ":2:") {
		t.Fatalf("want an error naming line 2, got %v", err)
	}
}

func TestReadLinksStripsByteOrderMark(t *testing.T) {
	path := filepath.Join(t.TempDir(), "links.csv")
	os.WriteFile(path, []byte("\xef\xbb\xbfname,destination\nMenu,https://example.com/menu\n"), 0o644)

	rows, err := readLinks(path)
	if err != nil {
		t.Fatal(err)
	}
	if want := []row{{"Menu", "https://example.com/menu"}}; !reflect.DeepEqual(rows, want) {
		t.Fatalf("got %+v, want %+v", rows, want)
	}
}

// Runs create then report against a mocked API, with the real SDK on top.
func TestCreateThenReport(t *testing.T) {
	qrPollInterval = 0
	var qrPolls int

	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/links/bulk", func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer test-token" {
			t.Errorf("Authorization = %q", got)
		}
		if r.Header.Get("Idempotency-Key") == "" {
			t.Error("no Idempotency-Key on the bulk create")
		}
		var body struct {
			Links []struct {
				Name string   `json:"name"`
				Tags []string `json:"tags"`
			} `json:"links"`
		}
		json.NewDecoder(r.Body).Decode(&body)
		if len(body.Links) != 1 || body.Links[0].Name != "Menu" || body.Links[0].Tags[0] != tag {
			t.Errorf("unexpected request: %+v", body)
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"links":[{"id":"id-1","name":"Menu","shortlink":"abc","entrypoint":"https://linkbreak.ing/abc"}]}`))
	})
	var server *httptest.Server
	mux.HandleFunc("POST /v1/links/qrcode-images:resolve", func(w http.ResponseWriter, r *http.Request) {
		// The first answer has no image yet: the code is still being drawn.
		qrPolls++
		w.Header().Set("Content-Type", "application/json")
		if qrPolls == 1 {
			w.Write([]byte(`{}`))
			return
		}
		json.NewEncoder(w).Encode(map[string]any{"qrcodeSignedUrls": map[string]string{"id-1": server.URL + "/signed/abc.svg"}})
	})
	mux.HandleFunc("GET /signed/abc.svg", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("<svg/>"))
	})
	mux.HandleFunc("GET /v1/links/id-1", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"link":{"id":"id-1","name":"Menu","entrypoint":"https://linkbreak.ing/abc","eventCount":7}}`))
	})
	server = httptest.NewServer(mux)
	defer server.Close()

	dir := t.TempDir()
	input := filepath.Join(dir, "links.csv")
	os.WriteFile(input, []byte("name,destination\nMenu,https://example.com/menu\n"), 0o644)
	linksOut := filepath.Join(dir, "links_out.csv")
	reportOut := filepath.Join(dir, "scan_report.csv")
	qrDir := filepath.Join(dir, "qr")

	ctx := context.WithValue(context.Background(), linkbreakers.ContextAccessToken, "test-token")
	c := newClient(server.URL)

	if err := c.create(ctx, input, linksOut, qrDir); err != nil {
		t.Fatal(err)
	}
	if svg, _ := os.ReadFile(filepath.Join(qrDir, "abc.svg")); string(svg) != "<svg/>" {
		t.Errorf("QR file = %q", svg)
	}
	if err := c.report(ctx, linksOut, reportOut); err != nil {
		t.Fatal(err)
	}
	report, _ := os.ReadFile(reportOut)
	if want := "name,short_link,scans\nMenu,https://linkbreak.ing/abc,7\n"; string(report) != want {
		t.Errorf("report = %q, want %q", report, want)
	}
}
