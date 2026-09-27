package config

import (
	"os"
	"path/filepath"
	"testing"
)

const fixtureDocument = `{
  "asystem": {
    "version": "10.200.1725",
    "host": "macmini-mad",
    "schema": [
      {
        "index": 1,
        "host": "macmini-mad",
        "label": "mad",
        "form_factor": "server",
        "os": "linux",
        "arch": "arm64",
        "shares": [
          {"mount": "/share/10", "label": "share_08", "served_by": "macmini-mad", "smb": "share-10"},
          {"mount": "/share/20", "label": "share_06", "served_by": "macmini-max", "smb": "share-20"}
        ],
        "backup": {"mount": "/backup", "label": "backup_06"}
      },
      {
        "host": "macmini-max",
        "label": "max",
        "form_factor": "server",
        "shares": [
          {"mount": "/share/20", "label": "share_06", "served_by": "macmini-max", "smb": "share-20"}
        ]
      }
    ]
  }
}`

func TestConfig_Load(t *testing.T) {
	path := writeFixture(t, fixtureDocument)
	t.Setenv("STORAGE_HOST", "")
	t.Setenv("SERVICE_VERSION_ABSOLUTE", "")
	cfg := Load(path)

	if got := cfg.Version(); got != "10.200.1725" {
		t.Errorf("Version: got %v want 10.200.1725", got)
	}
	if got := cfg.Name(); got != "macmini-mad" {
		t.Errorf("Name: got %v want macmini-mad", got)
	}
	if got := cfg.Label(); got != "mad" {
		t.Errorf("Label: got %v want mad", got)
	}
	if got := cfg.Index(); got == nil || *got != 1 {
		t.Errorf("Index: got %v want 1", got)
	}
	if got := cfg.MountLabel("/share/10"); got != "share_08" {
		t.Errorf("MountLabel(/share/10): got %v want share_08", got)
	}
	if got := cfg.MountLabel("/"); got != "" {
		t.Errorf("MountLabel(/): got %v want empty (UUID spec)", got)
	}
	if got := cfg.Backup(); got == nil || got.Mount != "/backup" {
		t.Errorf("Backup: got %+v", got)
	}
	if got := len(cfg.Hosts()); got != 2 {
		t.Errorf("Hosts: got %d want 2", got)
	}
	if cfg.ServedElsewhere("/share/10") {
		t.Errorf("ServedElsewhere(/share/10): got true want false, this host serves it")
	}
	if !cfg.ServedElsewhere("/share/20") {
		t.Errorf("ServedElsewhere(/share/20): got false want true, another host serves it")
	}
	if cfg.ServedElsewhere("/share/99") {
		t.Errorf("ServedElsewhere(/share/99): got true want false, it is undeclared")
	}
	estate := cfg.EstateShares()
	if len(estate) != 2 {
		t.Fatalf("EstateShares: got %d want 2, got %+v", len(estate), estate)
	}
	if estate[0].Mount != "/share/10" || estate[1].Mount != "/share/20" {
		t.Errorf("EstateShares not sorted/self-owned only: got %+v", estate)
	}
}

func TestConfig_Load_UnknownAndMissingFields(t *testing.T) {
	path := writeFixture(t, `{"asystem": {"version": "10.200.1725", "host": "macmini-mad", "unexpected_field": true, "schema": [{"host": "macmini-mad", "label": "mad"}]}}`)
	t.Setenv("STORAGE_HOST", "")
	t.Setenv("SERVICE_VERSION_ABSOLUTE", "")
	cfg := Load(path)
	if got := cfg.Label(); got != "mad" {
		t.Errorf("Label: got %v want mad", got)
	}
	if got := cfg.Backup(); got != nil {
		t.Errorf("Backup: got %+v want nil", got)
	}
	if got := cfg.Shares(); got != nil {
		t.Errorf("Shares: got %+v want nil", got)
	}
}

func TestConfig_Load_EnvOverridesFile(t *testing.T) {
	path := writeFixture(t, fixtureDocument)
	t.Setenv("STORAGE_HOST", "macmini-max")
	t.Setenv("SERVICE_VERSION_ABSOLUTE", "10.200.9999")
	cfg := Load(path)
	if got := cfg.Version(); got != "10.200.9999" {
		t.Errorf("Version: got %v want env override 10.200.9999", got)
	}
	if got := cfg.Label(); got != "max" {
		t.Errorf("Label: got %v want max (env-selected host)", got)
	}
}

func TestConfig_Load_UnresolvedHostFallsBackToHostname(t *testing.T) {
	path := writeFixture(t, `{"asystem": {"version": "10.200.1725", "host": "$STORAGE_HOST", "schema": []}}`)
	t.Setenv("STORAGE_HOST", "")
	t.Setenv("SERVICE_VERSION_ABSOLUTE", "")
	cfg := Load(path)
	wantHostname, err := os.Hostname()
	if err != nil {
		t.Fatalf("os.Hostname failed [%v]", err)
	}
	if got := cfg.Name(); got != wantHostname {
		t.Errorf("Name: got %v want os.Hostname() %v", got, wantHostname)
	}
}

func TestConfig_Label_FallsBackToTheHostnameSuffix(t *testing.T) {
	cases := []struct {
		name          string
		host          string
		want          string
		expectedError bool
	}{
		{name: "a host the schema declares", host: "macmini-mad", want: "mad"},
		{name: "a host the schema does not declare", host: "macbook-rue", want: "rue"},
		{name: "a hostname carrying no estate suffix", host: "localhost", want: "localhost"},
	}
	path := writeFixture(t, fixtureDocument)
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			t.Setenv("STORAGE_HOST", c.host)
			t.Setenv("SERVICE_VERSION_ABSOLUTE", "")
			if got := Load(path).Label(); got != c.want {
				t.Errorf("Label: got %v want %v", got, c.want)
			}
		})
	}
}

func writeFixture(t *testing.T, contents string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(path, []byte(contents), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}
