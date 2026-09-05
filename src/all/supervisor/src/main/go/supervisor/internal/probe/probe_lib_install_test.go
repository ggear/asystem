package probe

import (
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"supervisor/internal/scribe"
	"testing"
)

func TestProbeLibInstall_Snapshot(t *testing.T) {
	tests := []struct {
		name                   string
		environment            string
		compose                string
		sleepEnabled           bool
		omitEnvironment        bool
		omitCompose            bool
		expectedVersion        string
		expectedSleepEnabled   bool
		expectedMaxMemoryBytes int64
		expectedServiceModule  bool
		expectedError          bool
	}{
		{
			name:                   "happy_version_and_memory",
			environment:            "SERVICE_NAME=myservice\nSERVICE_VERSION_ABSOLUTE=10.100.1234\n",
			compose:                installComposeWith("256M"),
			expectedVersion:        "10.100.1234",
			expectedMaxMemoryBytes: 256 << 20,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:                   "happy_snapshot_version",
			environment:            "SERVICE_VERSION_ABSOLUTE=10.100.1234-SNAPSHOT\n",
			compose:                installComposeWith("16M"),
			expectedVersion:        "10.100.1234-SNAPSHOT",
			expectedMaxMemoryBytes: 16 << 20,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:                   "happy_sleep_enabled",
			environment:            "SERVICE_VERSION_ABSOLUTE=10.100.1234\n",
			compose:                installComposeWith("2G"),
			sleepEnabled:           true,
			expectedVersion:        "10.100.1234",
			expectedSleepEnabled:   true,
			expectedMaxMemoryBytes: 2 << 30,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:        "happy_bootstrap_sidecar_excluded",
			environment: "SERVICE_VERSION_ABSOLUTE=10.100.1234\n",
			compose: "services:\n  myservice:\n    deploy:\n      resources:\n        limits:\n          memory: 256M\n" +
				"  myservice_bootstrap:\n    restart: 'no'\n",
			expectedVersion:        "10.100.1234",
			expectedMaxMemoryBytes: 256 << 20,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:        "happy_merge_key_inherited_limit",
			environment: "SERVICE_VERSION_ABSOLUTE=10.100.1234\n",
			compose: "x-common: &common\n  deploy:\n    resources:\n      limits:\n        memory: 512M\n" +
				"services:\n  myservice:\n    <<: *common\n",
			expectedVersion:        "10.100.1234",
			expectedMaxMemoryBytes: 512 << 20,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:        "happy_several_long_running_services_summed",
			environment: "SERVICE_VERSION_ABSOLUTE=10.100.1234\n",
			compose: "services:\n  one:\n    deploy:\n      resources:\n        limits:\n          memory: 256M\n" +
				"  two:\n    deploy:\n      resources:\n        limits:\n          memory: 768M\n",
			expectedVersion:        "10.100.1234",
			expectedMaxMemoryBytes: 1024 << 20,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:                   "sad_version_not_parseable",
			environment:            "SERVICE_VERSION_ABSOLUTE=v10.100.1234\n",
			compose:                installComposeWith("256M"),
			expectedVersion:        "",
			expectedMaxMemoryBytes: 256 << 20,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:                   "sad_version_not_declared",
			environment:            "SERVICE_NAME=myservice\n",
			compose:                installComposeWith("256M"),
			expectedVersion:        "",
			expectedMaxMemoryBytes: 256 << 20,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:                   "sad_environment_missing",
			omitEnvironment:        true,
			compose:                installComposeWith("256M"),
			expectedVersion:        "",
			expectedMaxMemoryBytes: 256 << 20,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:                   "happy_host_module_no_compose",
			environment:            "SERVICE_VERSION_ABSOLUTE=10.100.1234\n",
			omitCompose:            true,
			expectedVersion:        "10.100.1234",
			expectedMaxMemoryBytes: 0,
			expectedServiceModule:  false,
			expectedError:          false,
		},
		{
			name:                   "sad_compose_declares_no_limit",
			environment:            "SERVICE_VERSION_ABSOLUTE=10.100.1234\n",
			compose:                "services:\n  myservice:\n    container_name: myservice\n",
			expectedVersion:        "10.100.1234",
			expectedMaxMemoryBytes: 0,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:                   "sad_compose_limit_not_parseable",
			environment:            "SERVICE_VERSION_ABSOLUTE=10.100.1234\n",
			compose:                installComposeWith("plenty"),
			expectedVersion:        "10.100.1234",
			expectedMaxMemoryBytes: 0,
			expectedServiceModule:  true,
			expectedError:          false,
		},
		{
			name:                   "sad_compose_not_parseable",
			environment:            "SERVICE_VERSION_ABSOLUTE=10.100.1234\n",
			compose:                "services: [this is not: a mapping\n",
			expectedVersion:        "10.100.1234",
			expectedMaxMemoryBytes: 0,
			expectedServiceModule:  true,
			expectedError:          false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetInstallTrees)
			mount := t.TempDir()
			home := filepath.Join(mount, "var/lib/asystem/install/myservice/latest")
			writeInstallDir(t, home)
			if !testCase.omitEnvironment {
				writeInstallFile(t, filepath.Join(home, ".env"), testCase.environment)
			}
			if !testCase.omitCompose {
				writeInstallFile(t, filepath.Join(home, "docker-compose.yml"), testCase.compose)
			}
			if testCase.sleepEnabled {
				writeInstallFile(t, filepath.Join(mount, "var/lib/asystem/install/myservice/.sleep"), "")
			}
			service, _ := loadInstallTree(mount).snapshot(installTestConfigured).service("myservice")
			if service.version != testCase.expectedVersion {
				t.Errorf("version: got %q want %q", service.version, testCase.expectedVersion)
			}
			if service.sleepEnabled != testCase.expectedSleepEnabled {
				t.Errorf("sleepEnabled: got %v want %v", service.sleepEnabled, testCase.expectedSleepEnabled)
			}
			if service.maxMemoryBytes != testCase.expectedMaxMemoryBytes {
				t.Errorf("allocatedBytes: got %d want %d", service.maxMemoryBytes, testCase.expectedMaxMemoryBytes)
			}
			if service.serviceModule != testCase.expectedServiceModule {
				t.Errorf("serviceModule: got %v want %v", service.serviceModule, testCase.expectedServiceModule)
			}
		})
	}
}

func TestProbeLibInstall_SnapshotAbsoluteSymlink(t *testing.T) {
	t.Cleanup(resetInstallTrees)
	mount := t.TempDir()
	home := filepath.Join(mount, "var/lib/asystem/install/myservice/10.100.5678")
	writeInstallDir(t, home)
	writeInstallFile(t, filepath.Join(home, ".env"), "SERVICE_VERSION_ABSOLUTE=10.100.5678\n")
	writeInstallFile(t, filepath.Join(home, "docker-compose.yml"), installComposeWith("64M"))
	if err := os.Symlink("/var/lib/asystem/install/myservice/10.100.5678", filepath.Join(mount, "var/lib/asystem/install/myservice/latest")); err != nil {
		t.Fatalf("symlink failed: %v", err)
	}
	service, _ := loadInstallTree(mount).snapshot(installTestConfigured).service("myservice")
	if service.version != "10.100.5678" {
		t.Errorf("version: got %q want %q", service.version, "10.100.5678")
	}
	if service.maxMemoryBytes != 64<<20 {
		t.Errorf("allocatedBytes: got %d want %d", service.maxMemoryBytes, int64(64<<20))
	}
}

func TestProbeLibInstall_Allocation(t *testing.T) {
	tests := []struct {
		name          string
		names         []string
		expectedBytes int64
		expectedError bool
	}{
		{
			name:          "happy_both_configured",
			names:         []string{"one", "two"},
			expectedBytes: 1024 << 20,
			expectedError: false,
		},
		{
			name:          "happy_filtered_to_configured",
			names:         []string{"one"},
			expectedBytes: 256 << 20,
			expectedError: false,
		},
		{
			name:          "happy_unknown_name_ignored",
			names:         []string{"one", "nowhere"},
			expectedBytes: 256 << 20,
			expectedError: false,
		},
		{
			name:          "happy_undeclared_limit_ignored",
			names:         []string{"three"},
			expectedBytes: 0,
			expectedError: false,
		},
		{
			name:          "happy_host_module_ignored",
			names:         []string{"one", "four"},
			expectedBytes: 256 << 20,
			expectedError: false,
		},
		{
			name:          "sad_only_host_modules_configured",
			names:         []string{"four"},
			expectedBytes: 0,
			expectedError: true,
		},
		{
			name:          "sad_no_names_configured",
			names:         nil,
			expectedBytes: 0,
			expectedError: true,
		},
		{
			name:          "sad_no_configured_names_installed",
			names:         []string{"nowhere"},
			expectedBytes: 0,
			expectedError: true,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Cleanup(resetInstallTrees)
			mount := t.TempDir()
			for name, limit := range map[string]string{"one": "256M", "two": "768M"} {
				home := filepath.Join(mount, "var/lib/asystem/install", name, "latest")
				writeInstallDir(t, home)
				writeInstallFile(t, filepath.Join(home, ".env"), "SERVICE_VERSION_ABSOLUTE=10.100.1234\n")
				writeInstallFile(t, filepath.Join(home, "docker-compose.yml"), installComposeWith(limit))
			}
			home := filepath.Join(mount, "var/lib/asystem/install/three/latest")
			writeInstallDir(t, home)
			writeInstallFile(t, filepath.Join(home, ".env"), "SERVICE_VERSION_ABSOLUTE=10.100.1234\n")
			writeInstallFile(t, filepath.Join(home, "docker-compose.yml"), "services:\n  three:\n    container_name: three\n")
			home = filepath.Join(mount, "var/lib/asystem/install/four/latest")
			writeInstallDir(t, home)
			writeInstallFile(t, filepath.Join(home, ".env"), "SERVICE_VERSION_ABSOLUTE=10.100.1234\n")
			got, _, err := loadInstallTree(mount).snapshot(testCase.names).allocation(testCase.names)
			if testCase.expectedError {
				if err == nil {
					t.Fatalf("expected error but got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != testCase.expectedBytes {
				t.Errorf("allocation: got %d want %d", got, testCase.expectedBytes)
			}
		})
	}
}

func TestProbeLibInstall_Invalidation(t *testing.T) {
	t.Cleanup(resetInstallTrees)
	mount := t.TempDir()
	home := filepath.Join(mount, "var/lib/asystem/install/myservice/latest")
	writeInstallDir(t, home)
	writeInstallFile(t, filepath.Join(home, ".env"), "SERVICE_VERSION_ABSOLUTE=10.100.1234\n")
	writeInstallFile(t, filepath.Join(home, "docker-compose.yml"), installComposeWith("256M"))
	tree := loadInstallTree(mount)
	first := tree.snapshot(installTestConfigured)
	if second := tree.snapshot(installTestConfigured); second != first {
		t.Errorf("snapshot: got a re-parse for an unchanged tree, want the cached snapshot")
	}
	writeInstallFile(t, filepath.Join(mount, "var/lib/asystem/install/myservice/.sleep"), "")
	third := tree.snapshot(installTestConfigured)
	if third == first {
		t.Fatalf("snapshot: got the cached snapshot after the sleep marker appeared, want a re-parse")
	}
	if installed, _ := third.service("myservice"); !installed.sleepEnabled {
		t.Errorf("sleepEnabled: got false want true")
	}
	if err := os.Remove(filepath.Join(mount, "var/lib/asystem/install/myservice/.sleep")); err != nil {
		t.Fatalf("remove .sleep failed: %v", err)
	}
	fourth := tree.snapshot(installTestConfigured)
	if fourth == third {
		t.Fatalf("snapshot: got the cached snapshot after the sleep marker was removed, want a re-parse")
	}
	if installed, _ := fourth.service("myservice"); installed.sleepEnabled {
		t.Errorf("sleepEnabled: got true want false")
	}
}

func TestProbeLibInstall_InvalidationOnVersionChange(t *testing.T) {
	t.Cleanup(resetInstallTrees)
	mount := t.TempDir()
	root := filepath.Join(mount, "var/lib/asystem/install/myservice")
	for _, version := range []string{"10.100.1234", "10.100.5678"} {
		home := filepath.Join(root, version)
		writeInstallDir(t, home)
		writeInstallFile(t, filepath.Join(home, ".env"), "SERVICE_VERSION_ABSOLUTE="+version+"\n")
		writeInstallFile(t, filepath.Join(home, "docker-compose.yml"), installComposeWith("256M"))
	}
	if err := os.Symlink("/var/lib/asystem/install/myservice/10.100.1234", filepath.Join(root, "latest")); err != nil {
		t.Fatalf("symlink failed: %v", err)
	}
	tree := loadInstallTree(mount)
	first := tree.snapshot(installTestConfigured)
	if installed, _ := first.service("myservice"); installed.version != "10.100.1234" {
		t.Fatalf("version: got %q want %q", installed.version, "10.100.1234")
	}
	if err := os.Remove(filepath.Join(root, "latest")); err != nil {
		t.Fatalf("remove latest failed: %v", err)
	}
	if err := os.Symlink("/var/lib/asystem/install/myservice/10.100.5678", filepath.Join(root, "latest")); err != nil {
		t.Fatalf("symlink failed: %v", err)
	}
	second := tree.snapshot(installTestConfigured)
	if second == first {
		t.Fatalf("snapshot: got the cached snapshot after the version was repointed, want a re-parse")
	}
	if installed, _ := second.service("myservice"); installed.version != "10.100.5678" {
		t.Errorf("version: got %q want %q", installed.version, "10.100.5678")
	}
}

func TestProbeLibInstall_LoadIsCachedPerMount(t *testing.T) {
	t.Cleanup(resetInstallTrees)
	mount := t.TempDir()
	if loadInstallTree(mount) != loadInstallTree(mount) {
		t.Errorf("load: got distinct trees for one mount, want the same tree")
	}
	if loadInstallTree(mount) == loadInstallTree(t.TempDir()) {
		t.Errorf("load: got the same tree for two mounts, want distinct trees")
	}
	tree := loadInstallTree(mount)
	resetInstallTrees()
	if loadInstallTree(mount) == tree {
		t.Errorf("load after reset: got the cached tree, want a new tree")
	}
}

func TestProbeLibInstall_ReportScopedToConfigured(t *testing.T) {
	t.Cleanup(resetInstallTrees)
	buffer := scribe.EnableBuffer(slog.LevelDebug, 200)
	t.Cleanup(func() { scribe.EnableStdout(slog.LevelInfo) })
	mount := t.TempDir()
	for _, name := range []string{"myservice", "departed"} {
		home := filepath.Join(mount, "var/lib/asystem/install", name, "latest")
		writeInstallDir(t, home)
		writeInstallFile(t, filepath.Join(home, "docker-compose.yml"), "services:\n  "+name+":\n    container_name: "+name+"\n")
	}
	snapshot := loadInstallTree(mount).snapshot(installTestConfigured)
	if _, found := snapshot.service("departed"); !found {
		t.Fatalf("service: got no entry for an unconfigured install, want it parsed for container lookups")
	}
	for _, line := range buffer.Tail(200) {
		if strings.Contains(line.Detail, "departed") {
			t.Errorf("detail: got a line naming an unconfigured install %q, want none", line.Detail)
		}
	}
	named := false
	for _, line := range buffer.Tail(200) {
		if strings.Contains(line.Detail, "myservice") {
			named = true
		}
	}
	if !named {
		t.Errorf("detail: got no line naming the configured install, want one")
	}
}

func installComposeWith(limit string) string {
	return "services:\n  myservice:\n    container_name: myservice\n    deploy:\n      resources:\n        limits:\n          memory: " + limit + "\n"
}

func writeInstallDir(t *testing.T, dir string) {
	t.Helper()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("mkdir %s failed: %v", dir, err)
	}
}

func writeInstallFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write %s failed: %v", path, err)
	}
}

var installTestConfigured = []string{"myservice"}
